"""Build a one-folder Windows ``.exe`` distribution with PyInstaller.

Run from the project root:

    python scripts/build_exe.py

Result lives in ``dist/ImageUpscalerPro/``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--windowed",
        "--name",
        "ImageUpscalerPro",
        "--add-data",
        f"{ROOT / 'assets'}{';' if sys.platform.startswith('win') else ':'}assets",
        "--collect-all",
        "customtkinter",
        "--collect-all",
        "tkinterdnd2",
        str(ROOT / "run.py"),
    ]
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        return result.returncode

    bin_dir = ROOT / "bin"
    if bin_dir.exists():
        dst = ROOT / "dist" / "ImageUpscalerPro" / "bin"
        print(f"Copying {bin_dir} -> {dst}")
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(bin_dir, dst)
    print("Build complete: dist/ImageUpscalerPro/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
