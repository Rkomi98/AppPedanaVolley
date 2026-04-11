from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app_pedana.config.defaults import AppConfig
from app_pedana.models.channel_map import FZ_CHANNEL_NAMES
from app_pedana.models.test_metadata import AthleteInfo
from app_pedana.services.analysis import (
    build_inspection,
    export_analysis_csv,
    build_analysis,
    load_test_bundle,
    resolve_signals_path,
)
from app_pedana.services.recorder import build_summary, record_test
from app_pedana.utils.logging_config import configure_logging


def main() -> int:
    args = _parse_args()
    config = AppConfig.default()
    configure_logging(config.log_path)

    try:
        if args.command == "record":
            return _run_record_command(config, args)
        if args.command == "inspect":
            return _run_inspect_command(args)
        if args.command == "analyze":
            return _run_analyze_command(args)
        return _run_gui(config)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Errore: {exc}")
        return 1


def _run_gui(config: AppConfig) -> int:
    from PySide6.QtWidgets import QApplication

    from app_pedana.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("AppPedanaVolley")
    window = MainWindow(config=config, output_dir=Path("output/tests"))
    window.show()
    return app.exec()


def _run_record_command(config: AppConfig, args: argparse.Namespace) -> int:
    athlete = AthleteInfo(
        first_name=args.first_name,
        last_name=args.last_name,
        athlete_id=args.athlete_id,
        notes=args.notes,
    )
    active_channels = FZ_CHANNEL_NAMES.copy()

    def _progress(elapsed_s: float, duration_s: float, frame) -> None:
        last = frame.iloc[-1]
        print(
            f"\r[{elapsed_s:05.2f}/{duration_s:05.2f}s] "
            f"P1={last['P1_total_FZ']:+.3f} V  "
            f"P2={last['P2_total_FZ']:+.3f} V  "
            f"TOTAL={last['FZ_total']:+.3f} V",
            end="",
            flush=True,
        )

    session, paths = record_test(
        config=config,
        mode=args.mode,
        active_channels=active_channels,
        duration_s=args.duration,
        athlete=athlete,
        test_type=args.test_type,
        output_dir=Path(args.output_dir),
        progress_callback=_progress,
    )
    print()
    summary = build_summary(session.combined_frame())
    print("Acquisizione completata")
    print(f"Samples: {int(summary['samples'])}")
    print(f"Durata: {summary['duration_s']:.3f} s")
    print(f"Picco P1_total_FZ: {summary['p1_peak']:.3f} V")
    print(f"Picco P2_total_FZ: {summary['p2_peak']:.3f} V")
    print(f"Picco FZ_total: {summary['total_peak']:.3f} V")
    print(f"CSV segnali: {paths['signals_csv']}")
    print(f"CSV metadata: {paths['metadata_csv']}")
    print(f"Excel: {paths['excel']}")
    return 0


def _run_inspect_command(args: argparse.Namespace) -> int:
    signals_path = resolve_signals_path(args.path, args.output_dir)
    bundle = load_test_bundle(signals_path)
    inspection = build_inspection(bundle)

    print("Inspect test")
    print(f"Signals: {inspection['signals_path']}")
    if inspection["metadata_path"]:
        print(f"Metadata: {inspection['metadata_path']}")
    print(f"Rows: {inspection['rows']}")
    print(f"Columns: {', '.join(inspection['columns'])}")
    print(f"Duration: {inspection['duration_s']:.3f} s")
    print(f"Estimated sample rate: {inspection['sample_rate_hz']:.3f} Hz")
    print(f"Sample interval CV: {inspection['sample_interval_cv_pct']:.3f} %")
    print(f"Resolved test type: {inspection['resolved_test_type']}")
    print(f"Quiet standing window: {inspection['quiet_standing_duration_s']:.3f} s")
    print(f"Quiet standing sufficient: {inspection['quiet_standing_sufficient']}")
    print(f"Quiet standing CV: {inspection['quiet_standing_cv_pct']:.3f} %")

    if inspection["metadata"]:
        print("Metadata fields:")
        for key, value in inspection["metadata"].items():
            print(f"  {key}: {value}")
    if inspection["warnings"]:
        print("Warnings:")
        for warning in inspection["warnings"]:
            print(f"  - {warning}")
    return 0


def _run_analyze_command(args: argparse.Namespace) -> int:
    signals_path = resolve_signals_path(args.path, args.output_dir)
    bundle = load_test_bundle(signals_path)
    analysis = build_analysis(bundle, test_type_override=args.test_type)
    summary_path = export_analysis_csv(
        bundle=bundle,
        analysis=analysis,
        target_path=args.export_summary,
    )

    print("Analyze test")
    print(f"Signals: {bundle.signals_path}")
    print(f"Test type: {analysis.summary['test_type']}")
    print(f"Samples: {analysis.summary['samples']}")
    print(f"Duration: {float(analysis.summary['duration_s']):.3f} s")
    print(f"Sample rate: {float(analysis.summary['sample_rate_hz']):.3f} Hz")
    print(f"Bodyweight total estimate: {float(analysis.summary['bodyweight_total_v']):.3f} V")
    print(f"Peak left: {float(analysis.summary['peak_left_fz_v']):.3f} V")
    print(f"Peak right: {float(analysis.summary['peak_right_fz_v']):.3f} V")
    print(f"Peak total: {float(analysis.summary['peak_total_fz_v']):.3f} V")
    print(f"Peak asymmetry: {float(analysis.summary['peak_asymmetry_pct']):.2f} %")
    print(f"Positive impulse left: {float(analysis.summary['positive_impulse_left_v_s']):.4f} V*s")
    print(f"Positive impulse right: {float(analysis.summary['positive_impulse_right_v_s']):.4f} V*s")
    print(f"Impulse asymmetry: {float(analysis.summary['impulse_asymmetry_pct']):.2f} %")
    print(f"Takeoff time: {_format_optional_float(analysis.events.get('takeoff_time_s'))}")
    print(f"Landing time: {_format_optional_float(analysis.events.get('landing_time_s'))}")
    print(f"Flight time: {_format_optional_float(analysis.summary.get('flight_time_s'))}")
    print(f"Jump height: {_format_optional_float(analysis.summary.get('jump_height_m'), unit='m')}")
    print(f"Summary CSV: {summary_path}")

    extra_event_keys = [
        key for key in analysis.events.keys() if key not in {"takeoff_time_s", "landing_time_s"}
    ]
    if extra_event_keys:
        print("Events:")
        for key in extra_event_keys:
            print(f"  {key}: {_format_optional_float(analysis.events[key])}")
    if analysis.warnings:
        print("Warnings:")
        for warning in analysis.warnings:
            print(f"  - {warning}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AppPedanaVolley MVP")
    subparsers = parser.add_subparsers(dest="command")

    record_parser = subparsers.add_parser(
        "record",
        help="Esegue una registrazione headless e salva CSV/XLSX",
    )
    record_parser.add_argument(
        "--mode",
        choices=["simulated", "ni"],
        default="simulated" if sys.platform == "darwin" else "ni",
        help="Sorgente acquisizione",
    )
    record_parser.add_argument("--duration", type=float, default=5.0, help="Durata test in secondi")
    record_parser.add_argument("--test-type", default="Altro", help="Tipo test")
    record_parser.add_argument("--first-name", default="", help="Nome atleta")
    record_parser.add_argument("--last-name", default="", help="Cognome atleta")
    record_parser.add_argument("--athlete-id", default="", help="ID atleta")
    record_parser.add_argument("--notes", default="", help="Note opzionali")
    record_parser.add_argument("--output-dir", default="output/tests", help="Cartella output")

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Mostra struttura e metadati di un test esportato",
    )
    inspect_parser.add_argument("path", nargs="?", default=None, help="Path al file *_signals.csv")
    inspect_parser.add_argument("--output-dir", default="output/tests", help="Cartella output")

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Calcola un report numerico finale da un test esportato",
    )
    analyze_parser.add_argument("path", nargs="?", default=None, help="Path al file *_signals.csv")
    analyze_parser.add_argument("--output-dir", default="output/tests", help="Cartella output")
    analyze_parser.add_argument("--test-type", default=None, help="Override del tipo test")
    analyze_parser.add_argument(
        "--export-summary",
        default=None,
        help="Salva il riepilogo finale in un CSV",
    )

    return parser.parse_args()


def _format_optional_float(value: object, *, unit: str = "s") -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.4f} {unit}"
