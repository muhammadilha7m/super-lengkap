"""Entry point for running Image Upscaler Pro.

Usage:
    python run.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from image_upscaler.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
