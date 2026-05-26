"""Pillow-based Lanczos / Bicubic upscaling engine.

This engine is fast, dependency-light, and always available.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PIL import Image, ImageOps

from ..constants import ENGINE_LANCZOS
from ..utils.image import save_image
from .base import EngineError, UpscaleEngine, UpscaleOptions


class LanczosEngine(UpscaleEngine):
    name = "lanczos"
    display_name = ENGINE_LANCZOS

    def upscale(
        self,
        input_path: Path,
        output_path: Path,
        options: UpscaleOptions,
        cancel_event: threading.Event,
    ) -> None:
        if cancel_event.is_set():
            raise EngineError("cancelled")
        try:
            with Image.open(input_path) as img:
                img = ImageOps.exif_transpose(img)
                new_size = (img.width * options.scale, img.height * options.scale)
                if cancel_event.is_set():
                    raise EngineError("cancelled")
                upscaled = img.resize(new_size, Image.Resampling.LANCZOS)
                exif_bytes = img.info.get("exif") if options.preserve_exif else None
            save_image(upscaled, output_path, options, exif_bytes=exif_bytes)
        except EngineError:
            raise
        except (OSError, ValueError) as exc:
            raise EngineError(f"Pillow gagal memproses '{input_path.name}': {exc}") from exc
