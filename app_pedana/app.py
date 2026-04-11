from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from app_pedana.config.defaults import AppConfig
from app_pedana.ui.main_window import MainWindow
from app_pedana.utils.logging_config import configure_logging


def main() -> int:
    config = AppConfig.default()
    configure_logging(config.log_path)
    logger = logging.getLogger(__name__)
    logger.info("Starting AppPedanaVolley MVP")

    app = QApplication(sys.argv)
    app.setApplicationName("AppPedanaVolley")
    window = MainWindow(config=config, output_dir=Path("output/tests"))
    window.show()
    return app.exec()
