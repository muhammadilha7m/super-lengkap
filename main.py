"""Spectrum AI — application entrypoint.

Run with:
    python main.py
"""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.core.config import Config
from app.core.logger import get_logger
from app.ui.main_window import MainWindow


def main() -> int:
    log = get_logger("spectrum_ai")
    log.info("Starting Spectrum AI…")

    config = Config.load()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(config.get("app.name", "Spectrum AI"))
    app.setOrganizationName("SpectrumAI")
    app.setQuitOnLastWindowClosed(True)

    window = MainWindow(config=config)
    window.show()

    # Auto-recover any unsaved session.
    try:
        recovered = window.project_manager.recover()
        if recovered is not None and recovered.audio_path:
            log.info("Crash recovery: restoring %s", recovered.name)
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Recovery failed: %s", exc)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
