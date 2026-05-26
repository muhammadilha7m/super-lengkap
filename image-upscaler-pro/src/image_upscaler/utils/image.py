"""Image I/O helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from ..engine.base import UpscaleOptions


def save_image(
    img: Image.Image,
    output_path: Path,
    options: UpscaleOptions,
    exif_bytes: bytes | None = None,
) -> None:
    """Save ``img`` honoring quality + format settings."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = options.output_format.upper()
    save_kwargs: dict[str, object] = {}

    if fmt == "JPEG":
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            mask = None
            if img.mode == "RGBA" or img.mode == "LA":
                mask = img.split()[-1]
            background.paste(img.convert("RGB"), mask=mask)
            img = background
        save_kwargs["quality"] = int(options.jpeg_quality)
        save_kwargs["optimize"] = True
        save_kwargs["progressive"] = True
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes
    elif fmt == "WEBP":
        save_kwargs["quality"] = int(options.webp_quality)
        save_kwargs["method"] = 6
    elif fmt == "PNG":
        save_kwargs["optimize"] = True

    img.save(output_path, format=fmt, **save_kwargs)


def read_image_size(path: Path) -> tuple[int, int]:
    """Return ``(width, height)`` of an image without loading the pixels."""
    with Image.open(path) as img:
        return img.size
