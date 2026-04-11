from __future__ import annotations

import pandas as pd

from app_pedana.models.channel_map import P1_FZ_CHANNELS, P2_FZ_CHANNELS


def add_force_aggregations(frame: pd.DataFrame) -> pd.DataFrame:
    enriched = frame.copy()
    enriched["P1_total_FZ"] = enriched[P1_FZ_CHANNELS].sum(axis=1)
    enriched["P2_total_FZ"] = enriched[P2_FZ_CHANNELS].sum(axis=1)
    enriched["FZ_total"] = enriched["P1_total_FZ"] + enriched["P2_total_FZ"]
    return enriched
