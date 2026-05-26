"""Helper to download Real-ESRGAN ncnn-vulkan binary for Windows.

Run this once with the app's Python interpreter:

    python scripts/download_realesrgan.py

It downloads the latest release zip from
https://github.com/xinntao/Real-ESRGAN/releases (Windows ncnn-vulkan build)
and unpacks it into ``image-upscaler-pro/bin/``. The app auto-discovers the
binary from there.
"""

from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_URL = (
    "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/"
    "realesrgan-ncnn-vulkan-20220424-windows.zip"
)

TARGET_DIR = Path(__file__).resolve().parent.parent / "bin"


def main(url: str = DEFAULT_URL) -> int:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url}")
    with urllib.request.urlopen(url) as resp:
        payload = resp.read()
    print(f"Downloaded {len(payload):,} bytes; extracting to {TARGET_DIR}")
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(TARGET_DIR)
    print("Done. The app will auto-detect realesrgan-ncnn-vulkan(.exe) from this folder.")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
