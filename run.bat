@echo off
REM ============================================================
REM   Spectrum AI - Windows launcher
REM ============================================================
setlocal

if not exist ".venv\Scripts\activate.bat" (
    echo [!] Virtual environment belum ada. Jalankan setup.bat dulu.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

REM --- Quick dep check ---
python -c "import PySide6, librosa, numpy" 2>nul
if errorlevel 1 (
    echo [!] Dependency belum lengkap. Jalankan setup.bat dulu.
    pause
    exit /b 1
)

REM --- Launch ---
python main.py
if errorlevel 1 (
    echo.
    echo [!] Aplikasi exit dengan error. Cek logs\app.log
    pause
)

endlocal
