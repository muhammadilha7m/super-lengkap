"""Drag & drop integration.

We wrap ``tkinterdnd2`` so the rest of the app doesn't crash if the library
isn't available (e.g., older systems). Drag & drop is best-effort: if it
can't be enabled, file/folder pickers still work.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def get_dnd_root_class() -> Any:
    """Return a Tk root class with drag & drop support, or ``None``."""
    try:
        from tkinterdnd2 import TkinterDnD  # type: ignore[import-not-found]
    except ImportError as exc:
        log.info("tkinterdnd2 not available, drag & drop disabled: %s", exc)
        return None

    import customtkinter as ctk

    class DnDCTk(ctk.CTk, TkinterDnD.DnDWrapper):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception as init_exc:  # pragma: no cover - depends on env
                log.warning("Failed to init tkdnd: %s", init_exc)

    return DnDCTk


def register_drop_target(widget: Any, on_paths: Callable[[list[Path]], None]) -> bool:
    """Register ``widget`` as a drop target. Returns ``True`` on success."""
    try:
        from tkinterdnd2 import DND_FILES  # type: ignore[import-not-found]
    except ImportError:
        return False

    try:
        widget.drop_target_register(DND_FILES)
    except Exception as exc:  # pragma: no cover - depends on env
        log.warning("Could not register drop target: %s", exc)
        return False

    def _on_drop(event: Any) -> None:
        raw = event.data or ""
        paths = _parse_dnd_paths(raw)
        if paths:
            on_paths(paths)

    widget.dnd_bind("<<Drop>>", _on_drop)
    return True


def _parse_dnd_paths(raw: str) -> list[Path]:
    """Parse Tk's DnD path format (curly-brace quoted for paths with spaces)."""
    out: list[Path] = []
    buf: list[str] = []
    in_brace = False
    for ch in raw:
        if ch == "{":
            in_brace = True
            buf = []
            continue
        if ch == "}":
            in_brace = False
            out.append(Path("".join(buf)))
            buf = []
            continue
        if ch == " " and not in_brace:
            if buf:
                out.append(Path("".join(buf)))
                buf = []
            continue
        buf.append(ch)
    if buf:
        out.append(Path("".join(buf)))
    return [p for p in out if str(p)]
