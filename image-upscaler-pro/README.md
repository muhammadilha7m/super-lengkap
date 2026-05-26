# Image Upscaler Pro

Aplikasi Python untuk **upscale gambar** (single & batch) dengan tampilan modern, dark/light mode, dan engine **Real-ESRGAN (AI)** + **Lanczos (klasik)**.

> Dibuat untuk Windows (juga jalan di Linux/macOS untuk development).

---

## ✨ Fitur Utama

- 🎯 **Dual engine**
  - **Lanczos** lewat Pillow — cepat, ringan, tanpa dependency tambahan, scale bebas (2x/3x/4x)
  - **Real-ESRGAN** lewat `realesrgan-ncnn-vulkan` — tajam berbasis AI, jalan di GPU NVIDIA / AMD / Intel via Vulkan, fallback CPU
- 📦 **Batch processing** dengan queue management (tambah, hapus, bersihkan)
- 🖱️ **Drag & drop** file / folder (opsional rekursif)
- ⏯️ **Pause / Resume / Cancel** saat batch berjalan
- 🔍 **Preview before / after** dengan slider yang bisa di-drag
- 🎨 **Dark / Light / System mode** + 3 pilihan warna aksen (blue / purple / green)
- 💾 **Format output**: PNG / JPEG / WEBP, kualitas JPEG/WEBP bisa diatur
- 📐 **Pertahankan EXIF** untuk JPEG
- 🔁 **Mode konflik file**: rename otomatis (`_upscaled_4x`, `_upscaled_4x_2`), overwrite, atau skip
- 🔔 **Sound + desktop notification** saat batch selesai
- 💼 **Settings persistent** — tersimpan di `%APPDATA%\ImageUpscalerPro\config.json`

---

## 🚀 Quick Start (Windows)

### Cara cepat — double-click `setup.bat` lalu `run.bat`

1. **Setup** sekali saja (buat venv + install dependencies):
   - Double-click **`setup.bat`** di folder `image-upscaler-pro\`
   - Script akan minta konfirmasi untuk download Real-ESRGAN AI binary (opsional, bisa di-skip)
2. **Jalankan** kapan saja:
   - Double-click **`run.bat`**
   - Splash screen "Image Upscaler Pro By BASIS" muncul ~2 detik, lalu main window terbuka

### Cara manual (PowerShell)

```powershell
git clone https://github.com/muhammadilha7m/super-lengkap.git
cd super-lengkap\image-upscaler-pro

py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Aplikasi langsung jalan dengan engine **Lanczos** (instant, tidak perlu setup tambahan).

### (Opsional) Aktifkan Real-ESRGAN untuk hasil AI yang lebih tajam

```powershell
python scripts\download_realesrgan.py
```

Script ini mengunduh `realesrgan-ncnn-vulkan.exe` + folder `models/` ke `image-upscaler-pro\bin\`. Aplikasi otomatis mendeteksinya.

Alternatif manual:
1. Download release ZIP dari https://github.com/xinntao/Real-ESRGAN/releases
2. Ekstrak ke `image-upscaler-pro\bin\` sehingga ada `bin\realesrgan-ncnn-vulkan.exe`
3. Atau pilih path-nya lewat tombol "Pilih binary…" di sidebar aplikasi

---

## 🖼 Cara Pakai

1. **Tambah gambar** dengan salah satu cara:
   - Drag & drop file/folder ke window
   - Klik **＋ Tambah File** untuk pilih beberapa file
   - Klik **🗀 Tambah Folder** untuk import seluruh folder (rekursif opsional)
2. **Atur setting** di sidebar kiri:
   - Engine, model Real-ESRGAN, skala, format output, kualitas, folder output, dll.
3. Klik **▶ Mulai Upscale**. Progress per-file dan total ditampilkan secara real-time.
4. Selama batch berjalan, Anda bisa:
   - **⏸ Jeda** atau **▶ Lanjutkan**
   - **■ Batal** seluruh batch
   - Klik salah satu item di queue untuk lihat preview before/after-nya
5. Klik **↗ Buka Folder Output** untuk membuka hasil di File Explorer.

---

## 🧱 Build menjadi `.exe` Standalone

```powershell
pip install -r requirements-dev.txt
python scripts\build_exe.py
```

Hasilnya: `dist\ImageUpscalerPro\ImageUpscalerPro.exe`. Folder `bin\` (Real-ESRGAN) akan otomatis ikut di-copy jika ada.

---

## 🛠 Development

```bash
pip install -r requirements-dev.txt

# Lint
ruff check src tests

# Tests
pytest

# Jalankan tanpa install
python run.py
# atau
python -m image_upscaler
```

### Struktur Project

```
image-upscaler-pro/
├── run.py                       # Entry point
├── setup.bat                    # Windows: buat venv + install deps
├── run.bat                      # Windows: launcher (pakai pythonw, tanpa console)
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── src/image_upscaler/
│   ├── app.py                   # Main App controller
│   ├── config.py                # Persisted user settings
│   ├── constants.py
│   ├── engine/
│   │   ├── base.py              # UpscaleEngine interface
│   │   ├── lanczos.py           # Pillow Lanczos engine
│   │   └── realesrgan.py        # Real-ESRGAN binary wrapper
│   ├── core/
│   │   ├── job.py               # Job dataclass
│   │   └── worker.py            # Threaded batch worker
│   ├── ui/
│   │   ├── theme.py             # Color palette + fonts
│   │   ├── sidebar.py           # Left settings panel
│   │   ├── queue_panel.py       # Queue list + toolbar
│   │   ├── preview.py           # Before/after compare slider
│   │   ├── statusbar.py         # Bottom status bar
│   │   ├── splash.py            # Animated intro splash (BASIS branding)
│   │   ├── widgets.py           # Reusable widgets
│   │   └── dnd.py               # tkinterdnd2 wrapper
│   └── utils/
│       ├── image.py             # Pillow save helpers
│       ├── paths.py             # Output path resolution
│       └── notifications.py     # Sound + desktop notif
├── scripts/
│   ├── download_realesrgan.py   # One-shot helper
│   └── build_exe.py             # PyInstaller wrapper
└── tests/
    ├── test_paths.py
    ├── test_config.py
    ├── test_engine_lanczos.py
    └── test_worker.py
```

---

## ❓ FAQ

**T: Saya tidak punya GPU NVIDIA, apakah Real-ESRGAN tetap bisa jalan?**
A: Ya. `realesrgan-ncnn-vulkan` pakai Vulkan, jadi GPU AMD / Intel terintegrasi juga didukung. Tanpa GPU sama sekali, ia akan fallback ke CPU (lebih lambat tapi tetap jalan).

**T: Kenapa Real-ESRGAN hanya support 2x/3x/4x?**
A: Itu batasan dari modelnya. Kalau butuh skala bebas (misal 1.5x atau 6x), pakai engine **Lanczos**.

**T: Outputnya disimpan di mana?**
A: Default: di folder yang sama dengan file sumber, dengan suffix `_upscaled_4x` (mengikuti skala). Bisa diganti ke folder lain via sidebar.

**T: Gambarnya besar banget (50+ MP), aman?**
A: Aman. Preview di UI dibatasi maksimal 1400px (untuk performa), tapi proses upscale tetap full-resolution.

---

## 📄 Lisensi

MIT.
