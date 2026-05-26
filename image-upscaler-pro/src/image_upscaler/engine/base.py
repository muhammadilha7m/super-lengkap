"""Engine base interface."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


class EngineError(RuntimeError):
    """Raised when an engine cannot process an image."""


@dataclass(frozen=True)
class UpscaleOptions:
    scale: int
    output_format: str
    jpeg_quality: int = 95
    webp_quality: int = 95
    preserve_exif: bool = True
    model: str = ""


class UpscaleEngine(ABC):
    """Abstract upscaling engine.

    Implementations must be safe to call from worker threads. They should honor
    ``cancel_event`` and raise :class:`EngineError` on unrecoverable failure.
    """

    name: str = "base"
    display_name: str = "Base"

    @abstractmethod
    def upscale(
        self,
        input_path: Path,
        output_path: Path,
        options: UpscaleOptions,
        cancel_event: threading.Event,
    ) -> None: ...

    def available(self) -> tuple[bool, str]:
        """Return ``(ok, message)``. ``ok=False`` disables the engine in the UI."""
        return True, ""
