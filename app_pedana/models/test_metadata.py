from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class AthleteInfo:
    first_name: str
    last_name: str
    athlete_id: str = ""
    notes: str = ""

    def display_name(self) -> str:
        full_name = f"{self.last_name}_{self.first_name}".strip("_")
        return full_name or "unknown_athlete"


@dataclass
class TestMetadata:
    athlete: AthleteInfo
    test_type: str
    duration_s: float
    sample_rate_hz: float
    channels: list[str]
    acquisition_mode: str
    created_at: datetime = field(default_factory=datetime.now)

    def to_flat_dict(self) -> dict[str, str | float]:
        payload = {
            "athlete_first_name": self.athlete.first_name,
            "athlete_last_name": self.athlete.last_name,
            "athlete_id": self.athlete.athlete_id,
            "notes": self.athlete.notes,
            "test_type": self.test_type,
            "duration_s": self.duration_s,
            "sample_rate_hz": self.sample_rate_hz,
            "channels": ", ".join(self.channels),
            "acquisition_mode": self.acquisition_mode,
            "created_at": self.created_at.isoformat(timespec="seconds"),
        }
        return payload

    def asdict(self) -> dict[str, object]:
        return asdict(self)
