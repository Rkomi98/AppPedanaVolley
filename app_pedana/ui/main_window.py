from __future__ import annotations

import logging
import sys
from collections import deque
from pathlib import Path

import pyqtgraph as pg
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app_pedana.config.defaults import AppConfig
from app_pedana.models.channel_map import FZ_CHANNEL_NAMES
from app_pedana.models.test_metadata import AthleteInfo, TestMetadata
from app_pedana.services.acquisition_session import AcquisitionSession
from app_pedana.services.recorder import build_summary
from app_pedana.ui.workers import AcquisitionWorker, WorkerSettings


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, *, config: AppConfig, output_dir: Path) -> None:
        super().__init__()
        self.config = config
        self.output_dir = output_dir
        self.worker: AcquisitionWorker | None = None
        self.session: AcquisitionSession | None = None
        self.latest_row = None
        self._live_view_dirty = False
        self.history_seconds = 4.0
        self.plot_cache = {
            "timestamp_s": deque(maxlen=int(self.config.sample_rate_hz * self.history_seconds)),
            "P1_total_FZ": deque(maxlen=int(self.config.sample_rate_hz * self.history_seconds)),
            "P2_total_FZ": deque(maxlen=int(self.config.sample_rate_hz * self.history_seconds)),
            "FZ_total": deque(maxlen=int(self.config.sample_rate_hz * self.history_seconds)),
        }

        self.setWindowTitle("AppPedanaVolley MVP")
        self.resize(1180, 760)
        self._build_ui()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(self.config.ui_refresh_interval_ms)
        self.refresh_timer.timeout.connect(self._flush_live_view)
        self.refresh_timer.start()
        self._set_idle_state()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QHBoxLayout(central)
        root.addWidget(self._build_form_panel(), 0)
        root.addLayout(self._build_visual_panel(), 1)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        athlete_box = QGroupBox("Anagrafica atleta")
        athlete_form = QFormLayout(athlete_box)
        self.first_name_input = QLineEdit()
        self.last_name_input = QLineEdit()
        self.athlete_id_input = QLineEdit()
        self.notes_input = QPlainTextEdit()
        self.notes_input.setMaximumHeight(90)
        athlete_form.addRow("Nome", self.first_name_input)
        athlete_form.addRow("Cognome", self.last_name_input)
        athlete_form.addRow("ID", self.athlete_id_input)
        athlete_form.addRow("Note", self.notes_input)

        test_box = QGroupBox("Setup test")
        test_form = QFormLayout(test_box)
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("NI Hardware", userData="ni")
        self.mode_combo.addItem("Simulata", userData="simulated")
        if sys.platform == "darwin":
            self.mode_combo.setCurrentIndex(1)

        self.test_type_combo = QComboBox()
        self.test_type_combo.addItems(
            ["Squat Jump", "Countermovement Jump", "Drop Jump", "Altro"]
        )
        self.test_type_combo.setEditable(True)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(1.0, 30.0)
        self.duration_spin.setSingleStep(0.5)
        self.duration_spin.setValue(self.config.default_duration_s)
        self.sample_rate_label = QLabel(f"{self.config.sample_rate_hz:.1f} Hz")
        self.channels_label = QLabel(", ".join(FZ_CHANNEL_NAMES))
        self.channels_label.setWordWrap(True)

        test_form.addRow("Sorgente", self.mode_combo)
        if sys.platform == "darwin":
            mac_hint = QLabel("Su macOS la lettura NI reale non e supportata: usa Simulata.")
            mac_hint.setWordWrap(True)
            mac_hint.setStyleSheet("color: #9c6644; font-size: 12px;")
            test_form.addRow("", mac_hint)
        test_form.addRow("Tipo test", self.test_type_combo)
        test_form.addRow("Durata [s]", self.duration_spin)
        test_form.addRow("Sample rate", self.sample_rate_label)
        test_form.addRow("Canali FZ", self.channels_label)

        button_row = QHBoxLayout()
        self.start_button = QPushButton("Avvia prova")
        self.stop_button = QPushButton("Ferma")
        self.start_button.clicked.connect(self.start_acquisition)
        self.stop_button.clicked.connect(self.stop_acquisition)
        button_row.addWidget(self.start_button)
        button_row.addWidget(self.stop_button)

        signal_box = QGroupBox("Segnale")
        signal_grid = QGridLayout(signal_box)
        self.left_signal_label = self._build_indicator("Sinistra")
        self.right_signal_label = self._build_indicator("Destra")
        self.left_value_label = QLabel("0.000 V")
        self.right_value_label = QLabel("0.000 V")
        self.total_value_label = QLabel("0.000 V")
        self.last_save_label = QLabel("Nessun test salvato")
        self.report_label = QLabel("Report finale disponibile a fine test")
        self.last_save_label.setWordWrap(True)
        self.report_label.setWordWrap(True)
        signal_grid.addWidget(self.left_signal_label, 0, 0)
        signal_grid.addWidget(self.right_signal_label, 0, 1)
        signal_grid.addWidget(QLabel("P1_total_FZ"), 1, 0)
        signal_grid.addWidget(self.left_value_label, 1, 1)
        signal_grid.addWidget(QLabel("P2_total_FZ"), 2, 0)
        signal_grid.addWidget(self.right_value_label, 2, 1)
        signal_grid.addWidget(QLabel("FZ_total"), 3, 0)
        signal_grid.addWidget(self.total_value_label, 3, 1)
        signal_grid.addWidget(QLabel("Ultimo salvataggio"), 4, 0)
        signal_grid.addWidget(self.last_save_label, 4, 1)
        signal_grid.addWidget(QLabel("Report finale"), 5, 0)
        signal_grid.addWidget(self.report_label, 5, 1)

        layout.addWidget(athlete_box)
        layout.addWidget(test_box)
        layout.addLayout(button_row)
        layout.addWidget(signal_box)
        layout.addStretch()
        return panel

    def _build_visual_panel(self) -> QVBoxLayout:
        layout = QVBoxLayout()

        pg.setConfigOptions(antialias=True, background="w", foreground="k")

        self.aggregated_plot = pg.PlotWidget(title="Aggregazioni verticali")
        self.aggregated_plot.showGrid(x=True, y=True, alpha=0.2)
        self.aggregated_plot.setLabel("left", "Volt")
        self.aggregated_plot.setLabel("bottom", "Tempo", units="s")
        self.aggregated_plot.setClipToView(True)
        self.aggregated_plot.setDownsampling(mode="peak")
        self.agg_curves = {
            "P1_total_FZ": self.aggregated_plot.plot(pen=pg.mkPen("#0077b6", width=2), name="P1"),
            "P2_total_FZ": self.aggregated_plot.plot(pen=pg.mkPen("#d62828", width=2), name="P2"),
            "FZ_total": self.aggregated_plot.plot(pen=pg.mkPen("#2a9d8f", width=3), name="Total"),
        }

        layout.addWidget(self.aggregated_plot, 1)
        return layout

    def _build_indicator(self, label: str) -> QLabel:
        widget = QLabel(label)
        widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        widget.setStyleSheet(
            "padding: 8px; border-radius: 6px; background: #b0bec5; color: black; font-weight: 600;"
        )
        return widget

    def _set_idle_state(self, *, status_message: str = "Pronto") -> None:
        self.stop_button.setEnabled(False)
        self.statusBar().showMessage(status_message)

    def start_acquisition(self) -> None:
        if self.worker is not None:
            return

        athlete = AthleteInfo(
            first_name=self.first_name_input.text().strip(),
            last_name=self.last_name_input.text().strip(),
            athlete_id=self.athlete_id_input.text().strip(),
            notes=self.notes_input.toPlainText().strip(),
        )
        metadata = TestMetadata(
            athlete=athlete,
            test_type=self.test_type_combo.currentText(),
            duration_s=float(self.duration_spin.value()),
            sample_rate_hz=self.config.sample_rate_hz,
            channels=FZ_CHANNEL_NAMES.copy(),
            acquisition_mode=self.mode_combo.currentText(),
        )
        self.session = AcquisitionSession(metadata=metadata, output_dir=self.output_dir)
        self._reset_plots()
        self.report_label.setText("Acquisizione in corso...")

        settings = WorkerSettings(
            mode=self.mode_combo.currentData(),
            active_channels=FZ_CHANNEL_NAMES.copy(),
            duration_s=metadata.duration_s,
            test_type=metadata.test_type,
        )
        self.worker = AcquisitionWorker(config=self.config, settings=settings)
        self.worker.block_ready.connect(self._on_block_ready)
        self.worker.status_changed.connect(self.statusBar().showMessage)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.finished_ok.connect(self._on_worker_finished)
        self.worker.finished.connect(self._clear_worker_reference)

        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.worker.start()

    def stop_acquisition(self) -> None:
        if self.worker is not None:
            self.worker.stop()
            self.statusBar().showMessage("Arresto acquisizione...")

    def _on_block_ready(self, frame) -> None:
        if self.session is None or frame.empty:
            return

        self.session.append(frame)
        timestamps = frame["timestamp_s"].tolist()
        self.plot_cache["timestamp_s"].extend(timestamps)
        for name in ("P1_total_FZ", "P2_total_FZ", "FZ_total"):
            self.plot_cache[name].extend(frame[name].tolist())
        self.latest_row = frame.iloc[-1]
        self._live_view_dirty = True

    def _on_worker_finished(self) -> None:
        self._finalize_session()

    def _on_worker_failed(self, message: str) -> None:
        self.session = None
        QMessageBox.critical(self, "Errore acquisizione", message)
        self._set_idle_state()

    def _clear_worker_reference(self) -> None:
        self.worker = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def _finalize_session(self) -> None:
        if self.session is None:
            return

        try:
            signals = self.session.combined_frame()
            export_paths = self.session.save()
        except Exception as exc:
            logger.exception("Export failed")
            QMessageBox.critical(self, "Errore export", f"Export non riuscito: {exc}")
            self._set_idle_state()
            return

        summary = build_summary(signals)
        self.last_save_label.setText(str(export_paths["excel"]))
        self.report_label.setText(
            "\n".join(
                [
                    f"Samples: {int(summary['samples'])}",
                    f"Durata: {summary['duration_s']:.3f} s",
                    f"Picco P1_total_FZ: {summary['p1_peak']:.3f} V",
                    f"Picco P2_total_FZ: {summary['p2_peak']:.3f} V",
                    f"Picco FZ_total: {summary['total_peak']:.3f} V",
                ]
            )
        )
        self.session = None
        self._set_idle_state(status_message=f"Test salvato: {export_paths['excel']}")

    def _refresh_plots(self) -> None:
        timestamps = list(self.plot_cache["timestamp_s"])
        for name, curve in self.agg_curves.items():
            curve.setData(timestamps, list(self.plot_cache[name]))

    def _flush_live_view(self) -> None:
        if not self._live_view_dirty or self.latest_row is None:
            return
        self._refresh_plots()
        self._refresh_indicators(self.latest_row)
        self._live_view_dirty = False

    def _refresh_indicators(self, last_row) -> None:
        left = float(last_row["P1_total_FZ"])
        right = float(last_row["P2_total_FZ"])
        total = float(last_row["FZ_total"])
        self.left_value_label.setText(f"{left:.3f} V")
        self.right_value_label.setText(f"{right:.3f} V")
        self.total_value_label.setText(f"{total:.3f} V")
        self._set_indicator_state(self.left_signal_label, abs(left) > 0.1)
        self._set_indicator_state(self.right_signal_label, abs(right) > 0.1)

    def _set_indicator_state(self, widget: QLabel, active: bool) -> None:
        background = "#7bd389" if active else "#b0bec5"
        widget.setStyleSheet(
            f"padding: 8px; border-radius: 6px; background: {background}; color: black; font-weight: 600;"
        )

    def _reset_plots(self) -> None:
        for cache in self.plot_cache.values():
            cache.clear()
        self.latest_row = None
        self._live_view_dirty = True

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.worker is not None:
            self.worker.stop()
            self.worker.wait(2000)
        super().closeEvent(event)
