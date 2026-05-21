@echo off
REM ============================================================
REM   Spectrum AI - Windows setup script
REM ============================================================
setlocal ENABLEDELAYEDEXPANSION

echo.
echo === Spectrum AI :: setup ===
echo.

REM --- Detect Python ---
where python >nul 2>&1
if errorlevel 1 (
    echo [!] Python tidak ditemukan. Install Python 3.10+ dulu.
    pause
    exit /b 1
)

REM --- Create venv ---
if not exist ".venv" (
    echo [*] Membuat virtual environment...
    python -m venv .venv
)

REM --- Activate venv ---
call .venv\Scripts\activate.bat

REM --- Upgrade pip ---
echo [*] Upgrade pip...
python -m pip install --upgrade pip wheel setuptools

REM --- Install dependencies ---
echo [*] Install dependencies...
pip install -r requirements.txt
if errorlevel 1 (
    echo [!] Install dependency gagal.
    pause
    exit /b 1
)

REM --- Setup folders ---
echo [*] Setup folder...
if not exist "projects" mkdir projects
if not exist "exports" mkdir exports
if not exist "cache" mkdir cache
if not exist "logs" mkdir logs
if not exist "assets\fonts" mkdir assets\fonts
if not exist "assets\templates" mkdir assets\templates
if not exist "assets\backgrounds" mkdir assets\backgrounds

REM --- FFmpeg note ---
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo.
    echo [!] FFmpeg tidak terdeteksi di PATH.
    echo     Aplikasi memakai imageio-ffmpeg sebagai fallback,
    echo     tapi lebih cepat kalau kamu install FFmpeg sistem:
    echo       https://www.gyan.dev/ffmpeg/builds/
    echo.
)

echo.
echo === Setup selesai. Jalankan run.bat ===
echo.

pause
endlocal
