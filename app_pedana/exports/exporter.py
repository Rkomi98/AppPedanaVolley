from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from app_pedana.models.test_metadata import TestMetadata


class TestExporter:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        *,
        metadata: TestMetadata,
        signals: pd.DataFrame,
        session_started_at: datetime,
    ) -> dict[str, Path]:
        stamp = session_started_at.strftime("%Y%m%d_%H%M%S")
        slug = f"{stamp}_{metadata.athlete.display_name()}_{_slugify(metadata.test_type)}"
        base_path = self.output_dir / slug

        metadata_frame = pd.DataFrame([metadata.to_flat_dict()])
        signals_csv = base_path.with_name(f"{base_path.name}_signals.csv")
        metadata_csv = base_path.with_name(f"{base_path.name}_metadata.csv")
        excel_path = base_path.with_suffix(".xlsx")

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


def _slugify(value: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in value.strip().lower())
    return safe.strip("_") or "test"
