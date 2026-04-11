from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


class DaqError(RuntimeError):
    """Raised for DAQ-related failures."""


@dataclass
class DaqReadResult:
    frame: pd.DataFrame
    elapsed_s: float


class BaseDaqReader(ABC):
    @abstractmethod
    def open(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def read_block(self) -> DaqReadResult:
        raise NotImplementedError
