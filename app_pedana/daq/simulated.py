from __future__ import annotations

from math import exp, pi, sin
from time import perf_counter

import pandas as pd

from app_pedana.config.defaults import AppConfig
from app_pedana.daq.base import BaseDaqReader, DaqReadResult


class SimulatedDaqReader(BaseDaqReader):
    def __init__(
        self,
        *,
        config: AppConfig,
        active_channels: list[str],
        test_type: str = "Altro",
    ) -> None:
        self.config = config
        self.active_channels = active_channels
        self.test_type = test_type
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
            left_total, right_total = _profile_totals(t, self.test_type)
            for channel_idx, channel_name in enumerate(self.active_channels):
                row[channel_name] = _channel_value(
                    channel_name=channel_name,
                    channel_idx=channel_idx,
                    t=t,
                    left_total=left_total,
                    right_total=right_total,
                )
            rows.append(row)

        self.sample_cursor += block
        frame = pd.DataFrame(rows)
        elapsed = self.sample_cursor / sr
        return DaqReadResult(frame=frame, elapsed_s=elapsed)


def _channel_value(
    *,
    channel_name: str,
    channel_idx: int,
    t: float,
    left_total: float,
    right_total: float,
) -> float:
    phase = channel_idx * 0.37
    drift = 0.015 * sin((2 * pi * 0.25 * t) + phase)

    if "P1_" in channel_name:
        side_total = left_total
        weights = {
            "FZ1": 0.26,
            "FZ2": 0.24,
            "FZ3": 0.23,
            "FZ4": 0.27,
        }
    else:
        side_total = right_total
        weights = {
            "FZ1": 0.24,
            "FZ2": 0.26,
            "FZ3": 0.27,
            "FZ4": 0.23,
        }

    for suffix, weight in weights.items():
        if channel_name.endswith(suffix):
            ripple = 0.025 * sin((2 * pi * 3.4 * t) + phase)
            return side_total * weight + ripple + drift

    return drift


def _profile_totals(t: float, test_type: str) -> tuple[float, float]:
    profile = _normalize_test_type(test_type)
    if profile == "squat_jump":
        return _squat_jump_totals(t)
    if profile == "countermovement_jump":
        return _countermovement_totals(t)
    if profile == "drop_jump":
        return _drop_jump_totals(t)
    return _generic_totals(t)


def _normalize_test_type(test_type: str) -> str:
    normalized = test_type.strip().lower().replace("-", " ").replace("_", " ")
    if "squat" in normalized or normalized == "sj":
        return "squat_jump"
    if "countermovement" in normalized or normalized == "cmj":
        return "countermovement_jump"
    if "drop" in normalized or normalized == "dj":
        return "drop_jump"
    return "other"


def _generic_totals(t: float) -> tuple[float, float]:
    envelope = 2.0 * max(0.0, sin((2 * pi * 0.55 * t) - 0.8))
    left = 0.85 + envelope + 0.35 * sin((2 * pi * 1.7 * t) + 0.2)
    right = 0.80 + envelope + 0.33 * sin((2 * pi * 1.7 * t) - 0.5)
    return left, right


def _squat_jump_totals(t: float) -> tuple[float, float]:
    baseline = 1.1 + 0.04 * sin(2 * pi * 0.8 * t)
    push = 4.6 * _gaussian(t, 1.35, 0.16)
    flight_decay = 1.25 * _sigmoid(t, 1.70, 18)
    landing = 2.8 * _gaussian(t, 2.05, 0.06)
    settle = 0.65 * _gaussian(t, 2.22, 0.12)

    left = baseline + push - flight_decay + landing + settle
    right = baseline * 0.98 + push * 1.04 - flight_decay * 0.96 + landing * 0.94 + settle
    return left, right


def _countermovement_totals(t: float) -> tuple[float, float]:
    baseline = 1.2 + 0.04 * sin(2 * pi * 0.9 * t)
    unweight = -0.85 * _gaussian(t, 0.72, 0.08)
    braking = 1.65 * _gaussian(t, 0.96, 0.09)
    push = 4.1 * _gaussian(t, 1.23, 0.13)
    flight_decay = 1.18 * _sigmoid(t, 1.57, 18)
    landing = 3.2 * _gaussian(t, 1.93, 0.06)
    rebound = 0.75 * _gaussian(t, 2.08, 0.10)

    left = baseline + unweight + braking + push - flight_decay + landing + rebound
    right = (
        baseline * 1.01
        + unweight * 0.92
        + braking * 1.08
        + push * 0.97
        - flight_decay
        + landing * 0.95
        + rebound
    )
    return left, right


def _drop_jump_totals(t: float) -> tuple[float, float]:
    baseline = 0.18 + 0.02 * sin(2 * pi * 0.7 * t)
    initial_contact = 4.7 * _gaussian(t, 0.58, 0.05)
    amortization = -0.75 * _gaussian(t, 0.70, 0.05)
    rebound = 4.0 * _gaussian(t, 0.88, 0.09)
    flight_decay = 1.05 * _sigmoid(t, 1.13, 20)
    landing = 3.4 * _gaussian(t, 1.43, 0.06)
    settle = 0.55 * _gaussian(t, 1.62, 0.12)

    left = baseline + initial_contact + amortization + rebound - flight_decay + landing + settle
    right = (
        baseline * 1.03
        + initial_contact * 0.95
        + amortization * 0.90
        + rebound * 1.05
        - flight_decay * 0.98
        + landing * 0.97
        + settle
    )
    return left, right


def _gaussian(t: float, center: float, width: float) -> float:
    return exp(-((t - center) ** 2) / (2 * width * width))


def _sigmoid(t: float, center: float, steepness: float) -> float:
    return 1.0 / (1.0 + exp(-steepness * (t - center)))
