from __future__ import annotations

from app_pedana.config.defaults import AppConfig
from app_pedana.daq.base import BaseDaqReader
from app_pedana.daq.nidaq_adapter import NIDaqReader
from app_pedana.daq.simulated import SimulatedDaqReader


def create_reader(
    *,
    mode: str,
    config: AppConfig,
    active_channels: list[str],
) -> BaseDaqReader:
    if mode == "ni":
        return NIDaqReader(config=config, active_channels=active_channels)
    return SimulatedDaqReader(config=config, active_channels=active_channels)
