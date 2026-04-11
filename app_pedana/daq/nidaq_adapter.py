from __future__ import annotations

import logging
import sys
from time import perf_counter

import pandas as pd

from app_pedana.config.defaults import AppConfig
from app_pedana.daq.base import BaseDaqReader, DaqError, DaqReadResult

try:
    import nidaqmx
    from nidaqmx.constants import AcquisitionType, TerminalConfiguration
    from nidaqmx.errors import DaqError as NIDaqException
except ImportError:  # pragma: no cover - depends on OS/runtime
    nidaqmx = None
    AcquisitionType = None
    TerminalConfiguration = None
    NIDaqException = Exception


logger = logging.getLogger(__name__)


class NIDaqReader(BaseDaqReader):
    def __init__(self, *, config: AppConfig, active_channels: list[str]) -> None:
        self.config = config
        self.active_channels = active_channels
        self.task = None
        self.start_ts: float | None = None

    def open(self) -> None:
        if sys.platform == "darwin":
            raise DaqError(
                "NI Hardware non e supportato su macOS. Usa la modalita Simulata sul Mac e la modalita NI Hardware su Windows."
            )

        if nidaqmx is None:
            raise DaqError(
                "Libreria nidaqmx non disponibile. Installa il package Python e verifica NI-DAQmx."
            )

        try:
            self.task = nidaqmx.Task(new_task_name="AppPedanaVolley_MVP")
            for logical_name in self.active_channels:
                physical = self.config.channel_map[logical_name]
                self.task.ai_channels.add_ai_voltage_chan(
                    physical,
                    name_to_assign_to_channel=logical_name,
                    min_val=self.config.voltage_min,
                    max_val=self.config.voltage_max,
                    terminal_config=TerminalConfiguration.RSE,
                )

            self.task.timing.cfg_samp_clk_timing(
                rate=self.config.sample_rate_hz,
                sample_mode=AcquisitionType.CONTINUOUS,
                samps_per_chan=self.config.block_size * 4,
            )
            self.task.start()
            self.start_ts = perf_counter()
            logger.info(
                "NI task started on %s with %s channels",
                self.config.device_name,
                len(self.active_channels),
            )
        except KeyError as exc:
            raise DaqError(f"Canale logico non configurato: {exc}") from exc
        except DaqError:
            raise
        except NIDaqException as exc:
            raise DaqError(_map_nidaq_error(exc)) from exc
        except Exception as exc:
            raise DaqError(f"Errore inizializzazione NI-DAQmx: {exc}") from exc

    def close(self) -> None:
        if self.task is not None:
            try:
                self.task.stop()
            except Exception:
                logger.debug("Task stop failed during close", exc_info=True)
            finally:
                self.task.close()
                self.task = None

    def read_block(self) -> DaqReadResult:
        if self.task is None or self.start_ts is None:
            raise DaqError("Task NI non inizializzato.")

        try:
            data = self.task.read(number_of_samples_per_channel=self.config.block_size)
            elapsed = perf_counter() - self.start_ts
        except NIDaqException as exc:
            raise DaqError(_map_nidaq_error(exc)) from exc

        frame = _to_frame(self.active_channels, data, self.config.sample_rate_hz, elapsed)
        return DaqReadResult(frame=frame, elapsed_s=elapsed)


def _to_frame(
    channels: list[str],
    data: list[list[float]] | list[float],
    sample_rate_hz: float,
    elapsed_s: float,
) -> pd.DataFrame:
    if not data:
        return pd.DataFrame(columns=["sample_index", "timestamp_s", *channels])

    if isinstance(data[0], float):
        data = [data]

    sample_count = len(data[0])
    start_time = elapsed_s - (sample_count / sample_rate_hz)
    timestamps = [start_time + (idx / sample_rate_hz) for idx in range(sample_count)]
    frame = pd.DataFrame({channel: values for channel, values in zip(channels, data, strict=True)})
    frame.insert(0, "timestamp_s", timestamps)
    frame.insert(0, "sample_index", range(sample_count))
    return frame


def _map_nidaq_error(exc: Exception) -> str:
    message = str(exc)
    lowered = message.lower()
    if "device" in lowered and "not found" in lowered:
        return "Device NI non trovato. Verifica collegamento USB e nome dispositivo."
    if "resource" in lowered and "reserved" in lowered:
        return "Uno o piu canali risultano occupati da un altro task o software."
    if "task specified is invalid" in lowered:
        return "Task NI non valido o non disponibile."
    return f"Errore NI-DAQmx: {message}"
