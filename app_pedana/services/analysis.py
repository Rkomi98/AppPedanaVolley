from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from pandas import isna

from app_pedana.models.channel_map import FZ_CHANNEL_NAMES, P1_FZ_CHANNELS, P2_FZ_CHANNELS
from app_pedana.services.aggregations import add_force_aggregations

REQUIRED_ANALYSIS_COLUMNS = {
    "timestamp_s",
    "P1_total_FZ",
    "P2_total_FZ",
    "FZ_total",
}


@dataclass
class TestBundle:
    signals_path: Path
    metadata_path: Path | None
    signals: pd.DataFrame
    metadata: dict[str, object]


@dataclass
class AnalysisResult:
    summary: dict[str, object]
    events: dict[str, object]
    warnings: list[str]
    prepared_signals: pd.DataFrame


def resolve_signals_path(path: str | None, output_dir: str | Path) -> Path:
    if path:
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(f"File non trovato: {resolved}")
        return resolved

    base_dir = Path(output_dir)
    candidates = sorted(base_dir.glob("*_signals.csv"))
    if not candidates:
        raise FileNotFoundError(f"Nessun file *_signals.csv trovato in {base_dir}")
    return candidates[-1]


def load_test_bundle(signals_path: str | Path) -> TestBundle:
    signals_path = Path(signals_path)
    if not signals_path.exists():
        raise FileNotFoundError(f"File non trovato: {signals_path}")

    metadata_path = signals_path.with_name(signals_path.name.replace("_signals.csv", "_metadata.csv"))
    signals = pd.read_csv(signals_path)
    metadata: dict[str, object] = {}
    if metadata_path.exists():
        metadata_frame = pd.read_csv(metadata_path)
        if not metadata_frame.empty:
            metadata = {
                key: ("" if isna(value) else value)
                for key, value in metadata_frame.iloc[0].to_dict().items()
            }
    else:
        metadata_path = None

    return TestBundle(
        signals_path=signals_path,
        metadata_path=metadata_path,
        signals=signals,
        metadata=metadata,
    )


def build_inspection(bundle: TestBundle) -> dict[str, object]:
    prepared = prepare_signals(bundle.signals)
    quality = assess_signal_quality(prepared)
    return {
        "signals_path": str(bundle.signals_path),
        "metadata_path": str(bundle.metadata_path) if bundle.metadata_path else "",
        "rows": int(len(prepared)),
        "columns": list(prepared.columns),
        "duration_s": quality["duration_s"],
        "sample_rate_hz": quality["sample_rate_hz"],
        "sample_interval_cv_pct": quality["sample_interval_cv_pct"],
        "quiet_standing_duration_s": quality["quiet_standing_duration_s"],
        "quiet_standing_sufficient": quality["quiet_standing_sufficient"],
        "quiet_standing_cv_pct": quality["quiet_standing_cv_pct"],
        "resolved_test_type": resolve_test_type(bundle.metadata),
        "metadata": bundle.metadata,
        "warnings": quality["warnings"],
    }


def build_analysis(
    bundle: TestBundle,
    *,
    test_type_override: str | None = None,
) -> AnalysisResult:
    signals = prepare_signals(bundle.signals)
    quality = assess_signal_quality(signals)
    warnings = list(quality["warnings"])

    if len(signals) < 200:
        raise ValueError("Segnale troppo corto per l'analisi.")
    if quality["sample_rate_hz"] <= 0:
        raise ValueError("Sample rate non valido o non stimabile.")

    resolved_test_type = normalize_test_type(test_type_override or resolve_test_type(bundle.metadata))
    sample_rate_hz = float(quality["sample_rate_hz"])
    quiet_samples = int(quality["quiet_standing_samples"])
    quiet = signals.iloc[:quiet_samples].copy()

    bodyweight_total = float(quiet["FZ_total"].mean())
    bodyweight_left = float(quiet["P1_total_FZ"].mean())
    bodyweight_right = float(quiet["P2_total_FZ"].mean())
    bodyweight_std = float(quiet["FZ_total"].std(ddof=0))

    prepared = signals.copy()
    prepared["P1_net_FZ"] = prepared["P1_total_FZ"] - bodyweight_left
    prepared["P2_net_FZ"] = prepared["P2_total_FZ"] - bodyweight_right
    prepared["FZ_net_total"] = prepared["FZ_total"] - bodyweight_total

    event_threshold = max(bodyweight_std * 4.0, abs(bodyweight_total) * 0.08, 0.05)
    flight_threshold = max(bodyweight_std * 3.0, abs(bodyweight_total) * 0.18, 0.05)
    sustained_samples = max(int(sample_rate_hz * 0.02), 3)
    min_flight_samples = max(int(sample_rate_hz * 0.08), 5)

    onset_idx = _find_sustained(
        np.abs(prepared["FZ_net_total"].to_numpy()),
        threshold=event_threshold,
        start=quiet_samples,
        sustained=sustained_samples,
        comparator="above",
    )
    if onset_idx is None:
        onset_idx = quiet_samples
        warnings.append("Onset non rilevato in modo robusto: uso fine quiet standing come fallback.")

    takeoff_idx = _find_sustained(
        prepared["FZ_total"].to_numpy(),
        threshold=flight_threshold,
        start=onset_idx,
        sustained=sustained_samples,
        comparator="below",
    )
    if takeoff_idx is None:
        warnings.append("Takeoff non rilevato.")

    landing_idx = None
    if takeoff_idx is not None:
        landing_idx = _find_sustained(
            prepared["FZ_total"].to_numpy(),
            threshold=flight_threshold,
            start=takeoff_idx + min_flight_samples,
            sustained=sustained_samples,
            comparator="above",
        )
        if landing_idx is None:
            warnings.append("Landing non rilevata.")

    propulsion_end_idx = takeoff_idx if takeoff_idx is not None else len(prepared) - 1
    propulsion_slice = prepared.iloc[onset_idx : propulsion_end_idx + 1]

    if propulsion_slice.empty:
        propulsion_slice = prepared.iloc[onset_idx : min(onset_idx + 1, len(prepared))]
        warnings.append("Finestra propulsiva vuota: uso finestra minima di fallback.")

    propulsive_peak_idx = _absolute_index_of_max(propulsion_slice["FZ_total"], offset=onset_idx)
    left_peak_idx = _absolute_index_of_max(propulsion_slice["P1_total_FZ"], offset=onset_idx)
    right_peak_idx = _absolute_index_of_max(propulsion_slice["P2_total_FZ"], offset=onset_idx)

    events: dict[str, object] = {
        "onset_time_s": _time_at(prepared, onset_idx),
        "propulsive_peak_time_s": _time_at(prepared, propulsive_peak_idx),
        "takeoff_time_s": _time_at(prepared, takeoff_idx),
        "landing_time_s": _time_at(prepared, landing_idx),
    }

    if resolved_test_type == "cmj":
        eccentric_slice = prepared.iloc[onset_idx : propulsive_peak_idx + 1]
        if not eccentric_slice.empty:
            cmj_min_idx = _absolute_index_of_min(eccentric_slice["FZ_net_total"], offset=onset_idx)
            events["eccentric_min_time_s"] = _time_at(prepared, cmj_min_idx)
    elif resolved_test_type == "dj":
        impact_window_end = min(len(prepared), quiet_samples + int(sample_rate_hz * 1.2))
        impact_slice = prepared.iloc[quiet_samples:impact_window_end]
        if not impact_slice.empty:
            impact_idx = _absolute_index_of_max(impact_slice["FZ_total"], offset=quiet_samples)
            events["impact_peak_time_s"] = _time_at(prepared, impact_idx)
        if takeoff_idx is not None and impact_slice is not None and not impact_slice.empty:
            rebound_slice = prepared.iloc[impact_idx : takeoff_idx + 1]
            if not rebound_slice.empty:
                rebound_idx = _absolute_index_of_max(rebound_slice["FZ_total"], offset=impact_idx)
                events["rebound_peak_time_s"] = _time_at(prepared, rebound_idx)
        if landing_idx is not None:
            landing_window_end = min(len(prepared), landing_idx + int(sample_rate_hz * 0.30))
            landing_slice = prepared.iloc[landing_idx:landing_window_end]
            if not landing_slice.empty:
                landing_peak_idx = _absolute_index_of_max(landing_slice["FZ_total"], offset=landing_idx)
                events["landing_peak_time_s"] = _time_at(prepared, landing_peak_idx)

    dt = 1.0 / sample_rate_hz
    positive_impulse_total = _positive_impulse(propulsion_slice["FZ_net_total"], dt)
    positive_impulse_left = _positive_impulse(propulsion_slice["P1_net_FZ"], dt)
    positive_impulse_right = _positive_impulse(propulsion_slice["P2_net_FZ"], dt)

    flight_time_s = None
    jump_height_m = None
    if takeoff_idx is not None and landing_idx is not None:
        flight_time_s = float(prepared.iloc[landing_idx]["timestamp_s"] - prepared.iloc[takeoff_idx]["timestamp_s"])
        if flight_time_s > 0:
            jump_height_m = 9.81 * (flight_time_s**2) / 8.0
        else:
            warnings.append("Flight time non positivo.")

    summary = {
        "test_type": resolved_test_type,
        "samples": int(len(prepared)),
        "duration_s": float(prepared["timestamp_s"].iloc[-1]),
        "sample_rate_hz": sample_rate_hz,
        "sample_interval_cv_pct": float(quality["sample_interval_cv_pct"]),
        "quiet_standing_duration_s": float(quality["quiet_standing_duration_s"]),
        "quiet_standing_sufficient": bool(quality["quiet_standing_sufficient"]),
        "quiet_standing_cv_pct": float(quality["quiet_standing_cv_pct"]),
        "bodyweight_total_v": bodyweight_total,
        "bodyweight_left_v": bodyweight_left,
        "bodyweight_right_v": bodyweight_right,
        "takeoff_time_s": events.get("takeoff_time_s"),
        "landing_time_s": events.get("landing_time_s"),
        "flight_time_s": flight_time_s,
        "jump_height_m": jump_height_m,
        "peak_total_fz_v": float(propulsion_slice["FZ_total"].max()),
        "peak_left_fz_v": float(propulsion_slice["P1_total_FZ"].max()),
        "peak_right_fz_v": float(propulsion_slice["P2_total_FZ"].max()),
        "peak_asymmetry_pct": asymmetry_pct(
            float(propulsion_slice["P1_total_FZ"].max()),
            float(propulsion_slice["P2_total_FZ"].max()),
        ),
        "positive_impulse_total_v_s": positive_impulse_total,
        "positive_impulse_left_v_s": positive_impulse_left,
        "positive_impulse_right_v_s": positive_impulse_right,
        "impulse_asymmetry_pct": asymmetry_pct(positive_impulse_left, positive_impulse_right),
        "warning_count": len(warnings),
        "warnings": " | ".join(warnings),
    }

    return AnalysisResult(
        summary=summary,
        events=events,
        warnings=warnings,
        prepared_signals=prepared,
    )


def export_analysis_csv(
    *,
    bundle: TestBundle,
    analysis: AnalysisResult,
    target_path: str | Path | None = None,
) -> Path:
    if target_path is None:
        target_path = bundle.signals_path.with_name(
            bundle.signals_path.name.replace("_signals.csv", "_summary.csv")
        )

    target_path = Path(target_path)
    summary_frame = pd.DataFrame([{**bundle.metadata, **analysis.summary, **analysis.events}])
    summary_frame.to_csv(target_path, index=False)
    return target_path


def prepare_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        raise ValueError("Il file segnali e vuoto.")

    frame = signals.copy()
    if "timestamp_s" not in frame.columns:
        raise ValueError("Colonna timestamp_s mancante.")

    if not REQUIRED_ANALYSIS_COLUMNS.issubset(frame.columns):
        if set(FZ_CHANNEL_NAMES).issubset(frame.columns):
            frame = add_force_aggregations(frame)

    missing = sorted(REQUIRED_ANALYSIS_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"Colonne richieste mancanti: {', '.join(missing)}")

    frame = frame.sort_values("timestamp_s").reset_index(drop=True)
    if frame["timestamp_s"].isna().any():
        raise ValueError("timestamp_s contiene valori mancanti.")
    if not frame["timestamp_s"].is_monotonic_increasing:
        raise ValueError("timestamp_s non e monotono crescente.")
    return frame


def assess_signal_quality(signals: pd.DataFrame) -> dict[str, object]:
    warnings: list[str] = []
    sample_rate_hz = _estimate_sample_rate(signals)
    duration_s = float(signals["timestamp_s"].iloc[-1]) if not signals.empty else 0.0

    deltas = signals["timestamp_s"].diff().dropna()
    mean_delta = float(deltas.mean()) if not deltas.empty else 0.0
    delta_cv_pct = float((deltas.std(ddof=0) / mean_delta) * 100.0) if mean_delta > 0 else 0.0
    if delta_cv_pct > 1.0:
        warnings.append("Sample rate irregolare: variabilita temporale sopra 1%.")

    quiet_samples = _estimate_quiet_samples(sample_rate_hz, len(signals))
    quiet = signals.iloc[:quiet_samples]
    quiet_mean = float(quiet["FZ_total"].mean()) if not quiet.empty else 0.0
    quiet_std = float(quiet["FZ_total"].std(ddof=0)) if not quiet.empty else 0.0
    quiet_cv_pct = float((quiet_std / abs(quiet_mean)) * 100.0) if abs(quiet_mean) > 1e-9 else 0.0
    quiet_duration_s = quiet_samples / sample_rate_hz if sample_rate_hz > 0 else 0.0
    quiet_sufficient = quiet_samples >= 100 and quiet_cv_pct < 12.0 and quiet_mean > 0

    if not quiet_sufficient:
        warnings.append("Quiet standing iniziale debole o insufficiente per una baseline robusta.")
    if duration_s < 0.8:
        warnings.append("Durata molto breve: alcune metriche potrebbero non essere affidabili.")

    return {
        "sample_rate_hz": sample_rate_hz,
        "duration_s": duration_s,
        "sample_interval_cv_pct": delta_cv_pct,
        "quiet_standing_samples": quiet_samples,
        "quiet_standing_duration_s": quiet_duration_s,
        "quiet_standing_sufficient": quiet_sufficient,
        "quiet_standing_cv_pct": quiet_cv_pct,
        "warnings": warnings,
    }


def resolve_test_type(metadata: dict[str, object]) -> str:
    raw_value = str(metadata.get("test_type", "")).strip()
    return raw_value or "Altro"


def normalize_test_type(value: str) -> str:
    normalized = value.strip().lower().replace("-", " ").replace("_", " ")
    if "squat" in normalized or normalized == "sj":
        return "sj"
    if "countermovement" in normalized or normalized == "cmj":
        return "cmj"
    if "drop" in normalized or normalized == "dj":
        return "dj"
    return "other"


def asymmetry_pct(left_value: float, right_value: float) -> float:
    denominator = max(abs(left_value), abs(right_value), 1e-9)
    return abs(left_value - right_value) / denominator * 100.0


def _estimate_sample_rate(signals: pd.DataFrame) -> float:
    if signals.empty or len(signals) < 2:
        return 0.0
    deltas = signals["timestamp_s"].diff().dropna()
    mean_delta = float(deltas.mean()) if not deltas.empty else 0.0
    if mean_delta <= 0:
        return 0.0
    return 1.0 / mean_delta


def _estimate_quiet_samples(sample_rate_hz: float, total_rows: int) -> int:
    if total_rows <= 0:
        return 0
    if sample_rate_hz <= 0:
        return min(total_rows, 100)
    target = int(sample_rate_hz * 0.50)
    minimum = min(total_rows, 100)
    upper_bound = max(minimum, min(total_rows, total_rows // 5))
    return min(total_rows, max(minimum, min(target, upper_bound)))


def _find_sustained(
    values: np.ndarray,
    *,
    threshold: float,
    start: int,
    sustained: int,
    comparator: str,
) -> int | None:
    run = 0
    for idx in range(start, len(values)):
        value = values[idx]
        condition = value > threshold if comparator == "above" else value < threshold
        if condition:
            run += 1
            if run >= sustained:
                return idx - sustained + 1
        else:
            run = 0
    return None


def _absolute_index_of_max(series: pd.Series, *, offset: int) -> int:
    return offset + int(np.argmax(series.to_numpy()))


def _absolute_index_of_min(series: pd.Series, *, offset: int) -> int:
    return offset + int(np.argmin(series.to_numpy()))


def _time_at(signals: pd.DataFrame, index: int | None) -> float | None:
    if index is None or index < 0 or index >= len(signals):
        return None
    return float(signals.iloc[index]["timestamp_s"])


def _positive_impulse(series: pd.Series, dt: float) -> float:
    clipped = np.clip(series.to_numpy(), a_min=0.0, a_max=None)
    return float(np.trapezoid(clipped, dx=dt))
