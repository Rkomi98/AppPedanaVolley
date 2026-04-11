from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from app_pedana.exports.exporter import TestExporter
from app_pedana.models.test_metadata import TestMetadata


@dataclass
class AcquisitionSession:
    metadata: TestMetadata
    output_dir: Path
    frames: list[pd.DataFrame] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)

    def append(self, frame: pd.DataFrame) -> None:
        self.frames.append(frame)

    def combined_frame(self) -> pd.DataFrame:
        if not self.frames:
            return pd.DataFrame()
        frame = pd.concat(self.frames, ignore_index=True)
        if "sample_index" in frame.columns:
            frame["sample_index"] = range(len(frame))
        return frame

    def save(self) -> dict[str, Path]:
        exporter = TestExporter(self.output_dir)
        return exporter.export(
            metadata=self.metadata,
            signals=self.combined_frame(),
            session_started_at=self.started_at,
        )
