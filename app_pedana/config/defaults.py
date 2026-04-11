from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import sys

from app_pedana.models.channel_map import DEFAULT_CHANNEL_MAP, FZ_CHANNEL_NAMES


_HAS_DATACLASS_SLOTS = sys.version_info >= (3, 10, 0)


@dataclass(**({"slots": True} if _HAS_DATACLASS_SLOTS else {}))
class AppConfig:
    device_name: str = "Dev1"
    sample_rate_hz: float = 7812.5
    block_size: int = 128
    ui_refresh_interval_ms: int = 25
    voltage_min: float = -5.0
    voltage_max: float = 5.0
    default_duration_s: float = 8.0
    channel_map: dict[str, str] = field(default_factory=lambda: DEFAULT_CHANNEL_MAP.copy())
    default_active_channels: list[str] = field(
        default_factory=lambda: FZ_CHANNEL_NAMES.copy()
    )
    log_path: Path = Path("output/logs/app.log")

    @classmethod
    def default(cls) -> "AppConfig":
        return cls()
