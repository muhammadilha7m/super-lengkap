"""User-facing completion notifications (sound + desktop)."""

from __future__ import annotations

import logging
import sys

log = logging.getLogger(__name__)


def play_done_sound() -> None:
    """Best-effort short beep on completion."""
    try:
        if sys.platform.startswith("win"):
            import winsound  # type: ignore[import-not-found]

            winsound.MessageBeep(winsound.MB_OK)
            return
        print("\a", end="", flush=True)
    except Exception as exc:  # pragma: no cover - audio is non-critical
        log.debug("Sound notification failed: %s", exc)


def show_desktop_notification(title: str, message: str) -> None:
    """Show an OS desktop notification via ``plyer`` if installed."""
    try:
        from plyer import notification

        notification.notify(title=title, message=message, app_name="Image Upscaler Pro", timeout=5)
    except Exception as exc:  # pragma: no cover - notif is non-critical
        log.debug("Desktop notification failed: %s", exc)
