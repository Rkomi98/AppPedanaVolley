from __future__ import annotations

import logging
from dataclasses import dataclass

from PySide6.QtCore import QThread, Signal

from app_pedana.config.defaults import AppConfig
from app_pedana.daq.base import DaqError
from app_pedana.daq.factory import create_reader
from app_pedana.services.aggregations import add_force_aggregations


logger = logging.getLogger(__name__)


@dataclass
class WorkerSettings:
    mode: str
    active_channels: list[str]
    duration_s: float
    test_type: str


class AcquisitionWorker(QThread):
    block_ready = Signal(object)
    status_changed = Signal(str)
    finished_ok = Signal()
    failed = Signal(str)

    def __init__(self, *, config: AppConfig, settings: WorkerSettings) -> None:
        super().__init__()
        self.config = config
        self.settings = settings
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self) -> None:
        reader = create_reader(
            mode=self.settings.mode,
            config=self.config,
            active_channels=self.settings.active_channels,
            test_type=self.settings.test_type,
        )
        elapsed_s = 0.0

        try:
            self.status_changed.emit("Connessione al dispositivo...")
            reader.open()
            self.status_changed.emit("Acquisizione in corso")

            while not self._stop_requested and elapsed_s < self.settings.duration_s:
                result = reader.read_block()
                frame = add_force_aggregations(result.frame)
                elapsed_s = result.elapsed_s
                self.block_ready.emit(frame)

            self.status_changed.emit("Acquisizione terminata")
            self.finished_ok.emit()
        except DaqError as exc:
            logger.exception("DAQ failure")
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected acquisition failure")
            self.failed.emit(f"Errore inatteso: {exc}")
        finally:
            reader.close()
