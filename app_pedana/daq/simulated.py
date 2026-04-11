from __future__ import annotations

from math import pi, sin
from time import perf_counter

import pandas as pd

from app_pedana.config.defaults import AppConfig
from app_pedana.daq.base import BaseDaqReader, DaqReadResult


class SimulatedDaqReader(BaseDaqReader):
    def __init__(self, *, config: AppConfig, active_channels: list[str]) -> None:
        self.config = config
        self.active_channels = active_channels
        self.start_ts: float | None = None
        self.sample_cursor = 0

    def open(self) -> None:
        self.start_ts = perf_counter()
        self.sample_cursor = 0

    def close(self) -> None:
        self.start_ts = None

    def read_block(self) -> DaqReadResult:
        if self.start_ts is None:
            raise RuntimeError("Simulated reader not started.")

        block = self.config.block_size
        sr = self.config.sample_rate_hz
        rows = []
        for local_idx in range(block):
            absolute_idx = self.sample_cursor + local_idx
            t = absolute_idx / sr
            row = {
                "sample_index": absolute_idx,
                "timestamp_s": t,
            }
            for channel_idx, channel_name in enumerate(self.active_channels):
                phase = channel_idx * 0.4
                base = 0.3 * sin((2 * pi * 1.4 * t) + phase)
                impulse = 1.7 * max(0.0, sin((2 * pi * 0.6 * t) - 0.8))
                drift = 0.05 * sin((2 * pi * 0.1 * t) + channel_idx)
                row[channel_name] = base + impulse + drift
            rows.append(row)

        self.sample_cursor += block
        frame = pd.DataFrame(rows)
        elapsed = perf_counter() - self.start_ts
        return DaqReadResult(frame=frame, elapsed_s=elapsed)
