"""Rotating file + rich console logger."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from rich.logging import RichHandler  # type: ignore
    _RICH = True
except Exception:  # pragma: no cover - rich is optional at runtime
    _RICH = False


def get_logger(name: str = "spectrum_ai", log_dir: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    log_dir = log_dir or Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    )
    logger.addHandler(file_handler)

    if _RICH:
        console = RichHandler(rich_tracebacks=True, markup=True, show_path=False)
        console.setLevel(logging.INFO)
        logger.addHandler(console)
    else:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(levelname)-7s | %(message)s"))
        logger.addHandler(console)

    logger.propagate = False
    return logger
