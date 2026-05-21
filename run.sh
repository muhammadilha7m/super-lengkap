#!/usr/bin/env bash
# ============================================================
#   Spectrum AI - Linux/macOS launcher
# ============================================================
set -e

if [ ! -f ".venv/bin/activate" ]; then
    echo "[!] Virtual environment belum ada. Jalankan ./setup.sh dulu."
    exit 1
fi

# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import PySide6, librosa, numpy" 2>/dev/null; then
    echo "[!] Dependency belum lengkap. Jalankan ./setup.sh dulu."
    exit 1
fi

python main.py
