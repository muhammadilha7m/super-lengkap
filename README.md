# Spectrum AI

Aplikasi desktop Python untuk membuat **video musik lirik spectrum** otomatis
menggunakan AI (Groq) + librosa + FFmpeg. Fokus: penggunaan pribadi, ringan,
cepat, full otomatis.

> **Status:** v0.1 — fondasi lengkap sudah jalan (UI, audio analyzer, spectrum
> visualizer, lirik AI, export MP4, project manager). Beberapa fitur tingkat
> lanjut masih placeholder / extensible — lihat *Roadmap* di bawah.

---

## Fitur yang sudah jalan

- UI modern dark + glassmorphism (PySide6), frameless window, drag-to-move.
- Audio analyzer berbasis librosa: BPM, beat, onset, RMS, mel-spectrogram,
  spectral centroid, deteksi mood / genre / vibe / palet warna otomatis.
- Spectrum visualizer multi-mode: `bar`, `mirror`, `wave`, `circular`, `rgb`,
  `neon`, `dual` — semua reaktif beat + glow + partikel + film grain + vignette
  + RGB split + beat flash.
- Lyric generator via Groq (mock mode tersedia kalau belum ada API key).
- Subtitle / karaoke renderer (per-kata highlight) + import LRC/SRT +
  export LRC/SRT.
- Video exporter via FFmpeg (auto-detect NVENC / AMF / QSV, fallback ke
  `libx264`).
- Project manager: save/load (`*.spxai`), autosave per 60 detik, crash
  recovery.
- One-click generate workflow: pilih audio → AI analisa → AI tulis lirik →
  preview → export.
- Chat AI sederhana untuk ubah style ("buat visualizer EDM neon biru").
- Mode TikTok / Shorts (1080×1920) + thumbnail generator.
- Shortcut keyboard: `Space` (play/pause), `Ctrl+O` (open), `Ctrl+S` (save),
  `Ctrl+R` (render), `Ctrl+G` (one-click generate).

## Struktur folder

```
.
├── main.py                  ← entrypoint Qt
├── renderer.py              ← frame iterator (spectrum + subtitle + bg)
├── spectrum_engine.py       ← visualizer multi-mode + efek
├── lyrics_generator.py      ← Groq → LyricsBundle (timing per kata)
├── ai_engine.py             ← thin Groq wrapper (+ mock fallback)
├── subtitle_engine.py       ← karaoke + LRC/SRT in/out
├── audio_analyzer.py        ← librosa pipeline + heuristik mood
├── export_engine.py         ← FFmpeg pipe (NVENC/AMF/QSV)
├── project_manager.py       ← save/load + autosave + recovery
├── requirements.txt
├── setup.bat / setup.sh
├── run.bat   / run.sh
├── README.md
├── /app
│   ├── core/                ← config, logger
│   └── ui/                  ← Qt widgets, workers, style, preview
├── /assets
│   ├── fonts/
│   ├── templates/           ← default.json
│   └── backgrounds/
├── /projects                ← *.spxai files
├── /exports                 ← MP4 / thumbnail output
├── /cache
├── /logs                    ← app.log (rotating)
└── /config
    └── settings.json
```

## Setup

### Windows

```bat
setup.bat
run.bat
```

### Linux / macOS

```bash
chmod +x setup.sh run.sh
./setup.sh
./run.sh
```

Setup script akan membuat `.venv`, install semua dependency dari
`requirements.txt`, dan menyiapkan folder runtime.

**Catatan FFmpeg:** kalau `ffmpeg` tidak ada di PATH, aplikasi otomatis pakai
`imageio-ffmpeg`. Untuk performa render terbaik, install FFmpeg sistem (di
Windows lewat https://www.gyan.dev/ffmpeg/builds/ atau di Linux:
`sudo apt install ffmpeg`).

## Konfigurasi Groq API

Set environment variable sebelum menjalankan aplikasi:

```bash
export GROQ_API_KEY=gsk_xxx        # Linux/macOS
setx GROQ_API_KEY "gsk_xxx"        # Windows
```

…atau isi field `ai.api_key` di `config/settings.json`. Jika tidak ada key,
aplikasi tetap berjalan dalam *mock mode* (lirik diambil dari template).

## Workflow cepat

1. **Pilih audio** dari sidebar → AI otomatis menganalisa BPM, mood, genre.
2. **Generate lirik** di tab AI (atau klik tombol *ONE-CLICK GENERATE*).
3. **Preview** real-time di tengah, edit lirik langsung di kotak editor.
4. **Atur visual** di tab Visual: mode spectrum, palet, sensitivity, smoothing,
   partikel, karaoke.
5. **Export** di tab Export: pilih resolusi (720p / 1080p / 1440p / 4K) +
   GPU encoder + CRF, lalu *Render & Export*.

## Build single EXE (Windows)

```bat
pip install pyinstaller
pyinstaller --noconfirm --windowed --onefile ^
    --name "Spectrum AI" ^
    --add-data "config;config" ^
    --add-data "assets;assets" ^
    main.py
```

EXE akan ada di `dist/Spectrum AI.exe`. Untuk *portable mode*, copy folder
`assets/` dan `config/` ke samping EXE.

## Roadmap (extensible hooks sudah disiapkan)

- [ ] **Stem separation** (vocal / drum / bass / instrument) via
      `spleeter` / `demucs` — hook tersedia di `audio_analyzer.MusicAnalysis`.
- [ ] **Plugin system** untuk effect / visualizer kustom — lihat
      `spectrum_engine.SpectrumStyle.mode` (drop-in handler).
- [ ] **Live wallpaper export** (Wallpaper Engine / Lively) — gunakan frame
      iterator + format MJPEG.
- [ ] **Auto loop engine** — basis ada di `renderer.iter_frames` (start/end).
- [ ] **Background render queue** + resume — extend `export_engine`.
- [ ] **Animated thumbnail / intro / outro generator** — tinggal pakai
      `render_thumbnail` + composite.
- [ ] **3D spectrum / shader effects** — bisa via `moderngl` / Qt RHI.

PR / patch welcome untuk semua item di atas.

## Logging

`logs/app.log` (rotating, 2 MB × 3) — semua error & warning ada di sini.

## Lisensi

Untuk penggunaan pribadi pemilik repo. Adapt sesuai kebutuhan.
