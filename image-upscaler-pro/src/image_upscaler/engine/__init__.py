"""Pluggable upscaling engines."""

from __future__ import annotations

from .base import EngineError, UpscaleEngine, UpscaleOptions
from .lanczos import LanczosEngine
from .realesrgan import RealEsrganEngine

__all__ = [
    "EngineError",
    "LanczosEngine",
    "RealEsrganEngine",
    "UpscaleEngine",
    "UpscaleOptions",
]
