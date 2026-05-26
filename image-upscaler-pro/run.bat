@echo off
setlocal EnableExtensions

rem ============================================================================
rem Image Upscaler Pro - Windows launcher
rem
rem - Activates the .venv created by setup.bat
rem - Runs the app (run.py)
rem ============================================================================

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual env belum dibuat.
    echo         Jalankan setup.bat dulu untuk install dependencies.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "run.py"
if errorlevel 1 (
    echo [ERROR] Gagal menjalankan app. Coba jalankan dengan console untuk lihat error:
    echo         .venv\Scripts\python.exe run.py
    pause
    exit /b 1
)

endlocal
