from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import perf_counter

import pandas as pd

P1_CHANNEL_INDEX = {
    "P1_FZ1": 0,
    "P1_FZ2": 1,
    "P1_FZ3": 2,
    "P1_FZ4": 3,
    "P1_FY14": 4,
    "P1_FY23": 5,
    "P1_FX12": 6,
    "P1_FX34": 7,
}

P2_CHANNEL_INDEX = {
    "P2_FZ1": 8,
    "P2_FZ2": 9,
    "P2_FZ3": 10,
    "P2_FZ4": 11,
    "P2_FY14": 12,
    "P2_FY23": 13,
    "P2_FX12": 14,
    "P2_FX34": 15,
}

ALL_CHANNELS = {**P1_CHANNEL_INDEX, **P2_CHANNEL_INDEX}
FZ_CHANNELS = [
    "P1_FZ1",
    "P1_FZ2",
    "P1_FZ3",
    "P1_FZ4",
    "P2_FZ1",
    "P2_FZ2",
    "P2_FZ3",
    "P2_FZ4",
]
P1_FZ_CHANNELS = ["P1_FZ1", "P1_FZ2", "P1_FZ3", "P1_FZ4"]
P2_FZ_CHANNELS = ["P2_FZ1", "P2_FZ2", "P2_FZ3", "P2_FZ4"]


@dataclass
class CaptureConfig:
    device_name: str
    duration_s: float
    sample_rate_hz: float
    block_size: int
    min_voltage: float
    max_voltage: float
    channel_set: str
    output_dir: Path
    athlete_first_name: str
    athlete_last_name: str
    athlete_id: str
    test_type: str
    notes: str


def main() -> int:
    args = parse_args()
    config = CaptureConfig(
        device_name=args.device_name,
        duration_s=args.duration,
        sample_rate_hz=args.sample_rate,
        block_size=args.block_size,
        min_voltage=args.min_voltage,
        max_voltage=args.max_voltage,
        channel_set=args.channel_set,
        output_dir=Path(args.output_dir),
        athlete_first_name=args.first_name.strip(),
        athlete_last_name=args.last_name.strip(),
        athlete_id=args.athlete_id.strip(),
        test_type=args.test_type.strip() or "Altro",
        notes=args.notes.strip(),
    )

    try:
        nidaqmx, AcquisitionType, TerminalConfiguration = import_nidaqmx()
    except RuntimeError as exc:
        print(exc)
        return 1

    logical_channels = selected_channels(config.channel_set)
    config.output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "athlete_first_name": config.athlete_first_name,
        "athlete_last_name": config.athlete_last_name,
        "athlete_id": config.athlete_id,
        "test_type": config.test_type,
        "notes": config.notes,
        "device_name": config.device_name,
        "channel_set": config.channel_set,
        "sample_rate_hz": config.sample_rate_hz,
        "duration_s": config.duration_s,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    print("Force plate capture test")
    print(f"Device: {config.device_name}")
    print(f"Channels: {', '.join(logical_channels)}")
    print(f"Duration: {config.duration_s:.2f} s")
    print(f"Sample rate: {config.sample_rate_hz:.2f} Hz")
    print(f"Block size: {config.block_size}")

    target_samples = int(round(config.duration_s * config.sample_rate_hz))
    frames: list[pd.DataFrame] = []
    task = None
    start_ts = None

    try:
        task = nidaqmx.Task(new_task_name="ForcePlateWindowsTest")
        for logical_name in logical_channels:
            physical_name = f"{config.device_name}/ai{ALL_CHANNELS[logical_name]}"
            task.ai_channels.add_ai_voltage_chan(
                physical_name,
                name_to_assign_to_channel=logical_name,
                min_val=config.min_voltage,
                max_val=config.max_voltage,
                terminal_config=TerminalConfiguration.RSE,
            )

        task.timing.cfg_samp_clk_timing(
            rate=config.sample_rate_hz,
            sample_mode=AcquisitionType.CONTINUOUS,
            samps_per_chan=config.block_size * 4,
        )
        task.start()
        start_ts = perf_counter()

        collected_samples = 0
        while collected_samples < target_samples:
            raw = task.read(number_of_samples_per_channel=config.block_size)
            block_frame = build_block_frame(
                logical_channels=logical_channels,
                raw=raw,
                collected_samples=collected_samples,
                sample_rate_hz=config.sample_rate_hz,
            )
            remaining = target_samples - collected_samples
            if len(block_frame) > remaining:
                block_frame = block_frame.iloc[:remaining].copy()

            block_frame = add_aggregations(block_frame)
            frames.append(block_frame)
            collected_samples += len(block_frame)

            last_row = block_frame.iloc[-1]
            print(
                f"\r[{collected_samples:6d}/{target_samples:6d}] "
                f"P1={last_row.get('P1_total_FZ', 0.0):+7.3f} V  "
                f"P2={last_row.get('P2_total_FZ', 0.0):+7.3f} V  "
                f"TOTAL={last_row.get('FZ_total', 0.0):+7.3f} V",
                end="",
                flush=True,
            )
    except Exception as exc:
        print()
        print(map_daq_error(exc))
        return 1
    finally:
        if task is not None:
            try:
                task.stop()
            except Exception:
                pass
            task.close()

    print()
    signals = pd.concat(frames, ignore_index=True)
    export_paths = export_capture(config=config, signals=signals, metadata=metadata)

    elapsed_s = perf_counter() - start_ts if start_ts is not None else 0.0
    print("Acquisizione completata")
    print(f"Elapsed wall time: {elapsed_s:.3f} s")
    print(f"Samples: {len(signals)}")
    print(f"Saved signals CSV: {export_paths['signals_csv']}")
    print(f"Saved metadata CSV: {export_paths['metadata_csv']}")
    print(f"Saved Excel: {export_paths['excel']}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simple NI USB-6211 force plate capture test")
    parser.add_argument("--device-name", default="Dev1", help="Nome device NI, es. Dev1")
    parser.add_argument("--duration", type=float, default=5.0, help="Durata acquisizione in secondi")
    parser.add_argument("--sample-rate", type=float, default=7812.5, help="Frequenza di campionamento")
    parser.add_argument("--block-size", type=int, default=256, help="Numero campioni per blocco")
    parser.add_argument("--min-voltage", type=float, default=-5.0, help="Min voltage")
    parser.add_argument("--max-voltage", type=float, default=5.0, help="Max voltage")
    parser.add_argument(
        "--channel-set",
        choices=["fz", "all"],
        default="fz",
        help="fz = solo verticali, all = tutti i 16 canali",
    )
    parser.add_argument("--output-dir", default="windows_test/output", help="Cartella output")
    parser.add_argument("--first-name", default="", help="Nome atleta")
    parser.add_argument("--last-name", default="", help="Cognome atleta")
    parser.add_argument("--athlete-id", default="", help="ID atleta")
    parser.add_argument("--test-type", default="Altro", help="Tipo test")
    parser.add_argument("--notes", default="", help="Note opzionali")
    return parser.parse_args()


def import_nidaqmx():
    import sys

    if not sys.platform.startswith("win"):
        raise RuntimeError("Questo script e pensato per Windows.")

    try:
        import nidaqmx
        from nidaqmx.constants import AcquisitionType, TerminalConfiguration
    except ImportError:
        raise RuntimeError(
            "Package Python 'nidaqmx' non trovato. Installa le dipendenze con:\n"
            r"  python -m pip install -r windows_test\requirements.txt"
        ) from None
    except Exception as exc:
        raise RuntimeError(f"Errore nel caricamento di nidaqmx: {exc}") from exc

    return nidaqmx, AcquisitionType, TerminalConfiguration


def selected_channels(channel_set: str) -> list[str]:
    if channel_set == "all":
        return list(ALL_CHANNELS.keys())
    return FZ_CHANNELS.copy()


def build_block_frame(
    *,
    logical_channels: list[str],
    raw: list[list[float]] | list[float],
    collected_samples: int,
    sample_rate_hz: float,
) -> pd.DataFrame:
    if not raw:
        return pd.DataFrame(columns=["sample_index", "timestamp_s", *logical_channels])

    if isinstance(raw[0], float):
        raw = [raw]

    sample_count = len(raw[0])
    timestamps = [(collected_samples + idx) / sample_rate_hz for idx in range(sample_count)]
    frame = pd.DataFrame(
        {channel: values for channel, values in zip(logical_channels, raw, strict=True)}
    )
    frame.insert(0, "timestamp_s", timestamps)
    frame.insert(0, "sample_index", range(collected_samples, collected_samples + sample_count))
    return frame


def add_aggregations(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    if set(P1_FZ_CHANNELS).issubset(enriched.columns):
        enriched["P1_total_FZ"] = enriched[P1_FZ_CHANNELS].sum(axis=1)
    if set(P2_FZ_CHANNELS).issubset(enriched.columns):
        enriched["P2_total_FZ"] = enriched[P2_FZ_CHANNELS].sum(axis=1)
    if {"P1_total_FZ", "P2_total_FZ"}.issubset(enriched.columns):
        enriched["FZ_total"] = enriched["P1_total_FZ"] + enriched["P2_total_FZ"]
    return enriched


def export_capture(
    *,
    config: CaptureConfig,
    signals: pd.DataFrame,
    metadata: dict[str, object],
) -> dict[str, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    athlete_slug = "_".join(part for part in [config.athlete_last_name, config.athlete_first_name] if part)
    if not athlete_slug:
        athlete_slug = "unknown_athlete"
    test_slug = slugify(config.test_type)
    base_name = f"{timestamp}_{athlete_slug}_{test_slug}"

    signals_csv = config.output_dir / f"{base_name}_signals.csv"
    metadata_csv = config.output_dir / f"{base_name}_metadata.csv"
    excel_path = config.output_dir / f"{base_name}.xlsx"

    metadata_frame = pd.DataFrame([metadata])
    signals.to_csv(signals_csv, index=False)
    metadata_frame.to_csv(metadata_csv, index=False)

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        metadata_frame.to_excel(writer, sheet_name="metadata", index=False)
        signals.to_excel(writer, sheet_name="signals", index=False)

    return {
        "signals_csv": signals_csv,
        "metadata_csv": metadata_csv,
        "excel": excel_path,
    }


def slugify(value: str) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in value.lower().strip())
    return safe.strip("_") or "test"


def map_daq_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "device" in lowered and "not found" in lowered:
        return "Errore: device NI non trovato. Controlla NI MAX e usa il nome corretto in --device-name."
    if "resource" in lowered and "reserved" in lowered:
        return "Errore: canale o device occupato da un altro software. Chiudi DAQExpress, NI MAX o altre app."
    if "daqmx" in lowered:
        return f"Errore NI-DAQmx: {message}"
    return f"Errore acquisizione: {message}"


if __name__ == "__main__":
    raise SystemExit(main())
