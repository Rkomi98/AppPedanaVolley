from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd

from app_pedana.config.defaults import AppConfig
from app_pedana.daq.factory import create_reader
from app_pedana.models.test_metadata import AthleteInfo, TestMetadata
from app_pedana.services.acquisition_session import AcquisitionSession
from app_pedana.services.aggregations import add_force_aggregations


logger = logging.getLogger(__name__)


def record_test(
    *,
    config: AppConfig,
    mode: str,
    active_channels: list[str],
    duration_s: float,
    athlete: AthleteInfo,
    test_type: str,
    output_dir: Path,
    progress_callback: callable | None = None,
) -> tuple[AcquisitionSession, dict[str, Path]]:
    metadata = TestMetadata(
        athlete=athlete,
        test_type=test_type,
        duration_s=duration_s,
        sample_rate_hz=config.sample_rate_hz,
        channels=active_channels.copy(),
        acquisition_mode=mode,
    )
    session = AcquisitionSession(metadata=metadata, output_dir=output_dir)
    reader = create_reader(
        mode=mode,
        config=config,
        active_channels=active_channels,
        test_type=test_type,
    )
    block_duration_s = config.block_size / config.sample_rate_hz
    last_progress_mark = -1
    target_samples = int(round(duration_s * config.sample_rate_hz))
    collected_samples = 0

    try:
        reader.open()
        elapsed_s = 0.0
        while collected_samples < target_samples:
            result = reader.read_block()
            frame = add_force_aggregations(result.frame)
            remaining_samples = target_samples - collected_samples
            if len(frame) > remaining_samples:
                frame = frame.iloc[:remaining_samples].copy()
            session.append(frame)
            collected_samples += len(frame)
            elapsed_s = collected_samples / config.sample_rate_hz

            if progress_callback is not None:
                progress_callback(elapsed_s, duration_s, frame)
            else:
                progress_mark = int(elapsed_s)
                if progress_mark != last_progress_mark:
                    last_progress_mark = progress_mark
                    logger.info("Acquisition progress %.2fs / %.2fs", elapsed_s, duration_s)

            if mode == "simulated":
                time.sleep(block_duration_s)
    finally:
        reader.close()

    paths = session.save()
    return session, paths


def build_summary(frame: pd.DataFrame) -> dict[str, float]:
    if frame.empty:
        return {
            "samples": 0,
            "duration_s": 0.0,
            "p1_peak": 0.0,
            "p2_peak": 0.0,
            "total_peak": 0.0,
        }

    return {
        "samples": float(len(frame)),
        "duration_s": float(frame["timestamp_s"].iloc[-1]),
        "p1_peak": float(frame["P1_total_FZ"].abs().max()),
        "p2_peak": float(frame["P2_total_FZ"].abs().max()),
        "total_peak": float(frame["FZ_total"].abs().max()),
    }
