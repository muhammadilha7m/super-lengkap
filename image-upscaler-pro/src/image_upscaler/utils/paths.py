"""Output path resolution and folder scanning helpers."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from ..constants import (
    OUTPUT_FORMAT_EXT,
    SUFFIX_TEMPLATE,
    SUPPORTED_INPUT_EXTS,
)


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_INPUT_EXTS


def expand_paths(paths: Iterable[Path | str], recursive: bool = True) -> list[Path]:
    """Expand a mix of files and folders into a deduplicated list of image files."""
    seen: set[Path] = set()
    result: list[Path] = []
    for raw in paths:
        p = Path(raw).expanduser()
        if not p.exists():
            continue
        if p.is_file():
            if is_supported_image(p):
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    result.append(rp)
            continue
        if p.is_dir():
            iterator: Iterable[Path]
            iterator = p.rglob("*") if recursive else p.glob("*")
            for child in sorted(iterator):
                if is_supported_image(child):
                    rp = child.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        result.append(rp)
    return result


def resolve_output_path(
    input_path: Path,
    output_dir: str,
    output_format: str,
    scale: int,
    conflict_mode: str,
) -> Path | None:
    """Compute the target output path for ``input_path``.

    Returns ``None`` when ``conflict_mode == "skip"`` and the file already exists.
    """
    ext = OUTPUT_FORMAT_EXT[output_format.upper()]
    suffix = SUFFIX_TEMPLATE.format(scale=scale)
    base = f"{input_path.stem}{suffix}{ext}"
    target_dir = Path(output_dir).expanduser() if output_dir else input_path.parent
    candidate = target_dir / base

    if not candidate.exists():
        return candidate
    if conflict_mode == "overwrite":
        return candidate
    if conflict_mode == "skip":
        return None
    counter = 2
    while True:
        rotated = target_dir / f"{input_path.stem}{suffix}_{counter}{ext}"
        if not rotated.exists():
            return rotated
        counter += 1


def human_size(num_bytes: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    n = float(num_bytes)
    for unit in units:
        if n < 1024 or unit == units[-1]:
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TB"


def safe_file_size(path: Path) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0
