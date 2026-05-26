"""Tests for utils.paths."""

from __future__ import annotations

from pathlib import Path

import pytest

from image_upscaler.utils.paths import (
    expand_paths,
    human_size,
    is_supported_image,
    resolve_output_path,
)


def _touch(path: Path, content: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_is_supported_image(tmp_path: Path) -> None:
    img = _touch(tmp_path / "a.PNG")
    not_img = _touch(tmp_path / "b.txt")
    assert is_supported_image(img)
    assert not is_supported_image(not_img)
    assert not is_supported_image(tmp_path / "missing.png")


def test_expand_paths_dedupes_and_handles_folders(tmp_path: Path) -> None:
    a = _touch(tmp_path / "a.jpg")
    _touch(tmp_path / "sub" / "b.png")
    _touch(tmp_path / "ignore.txt")

    result = expand_paths([tmp_path, a], recursive=True)
    assert sorted(p.name for p in result) == ["a.jpg", "b.png"]

    flat = expand_paths([tmp_path], recursive=False)
    assert [p.name for p in flat] == ["a.jpg"]

    # Duplicates collapse.
    again = expand_paths([a, a, tmp_path], recursive=True)
    assert len(again) == 2


def test_resolve_output_path_rename_when_exists(tmp_path: Path) -> None:
    src = _touch(tmp_path / "photo.jpg")
    target = resolve_output_path(src, "", "PNG", 4, "rename")
    assert target == tmp_path / "photo_upscaled_4x.png"

    _touch(target)
    rotated = resolve_output_path(src, "", "PNG", 4, "rename")
    assert rotated == tmp_path / "photo_upscaled_4x_2.png"


def test_resolve_output_path_skip_when_exists(tmp_path: Path) -> None:
    src = _touch(tmp_path / "img.png")
    existing = _touch(tmp_path / "img_upscaled_2x.png")
    assert existing.exists()
    assert resolve_output_path(src, "", "PNG", 2, "skip") is None


def test_resolve_output_path_overwrite_returns_same(tmp_path: Path) -> None:
    src = _touch(tmp_path / "img.png")
    _touch(tmp_path / "img_upscaled_2x.png")
    assert resolve_output_path(src, "", "PNG", 2, "overwrite") == tmp_path / "img_upscaled_2x.png"


def test_resolve_output_path_custom_output_dir(tmp_path: Path) -> None:
    src = _touch(tmp_path / "img.png")
    out_dir = tmp_path / "out"
    target = resolve_output_path(src, str(out_dir), "JPEG", 3, "rename")
    assert target == out_dir / "img_upscaled_3x.jpg"


@pytest.mark.parametrize(
    "value,expected",
    [
        (0, "0 B"),
        (512, "512 B"),
        (2048, "2.0 KB"),
        (5 * 1024 * 1024, "5.0 MB"),
    ],
)
def test_human_size(value: int, expected: str) -> None:
    assert human_size(value) == expected
