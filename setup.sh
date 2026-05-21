#!/usr/bin/env bash
# ============================================================
#   Spectrum AI - Linux/macOS setup script
# ============================================================
set -e

echo "=== Spectrum AI :: setup ==="

if ! command -v python3 >/dev/null 2>&1; then
    echo "[!] Python3 tidak ditemukan. Install Python 3.10+ dulu."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "[*] Membuat virtual environment..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "[*] Upgrade pip..."
python -m pip install --upgrade pip wheel setuptools

echo "[*] Install dependencies..."
pip install -r requirements.txt

mkdir -p projects exports cache logs assets/fonts assets/templates assets/backgrounds

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "[!] FFmpeg tidak terdeteksi. Pakai imageio-ffmpeg fallback,"
    echo "    tapi disarankan install FFmpeg sistem (apt install ffmpeg)."
fi

echo "=== Setup selesai. Jalankan ./run.sh ==="
