@echo off
setlocal EnableExtensions EnableDelayedExpansion

rem ============================================================================
rem Image Upscaler Pro - Windows setup script
rem
rem - Creates a local virtual environment in .venv
rem - Installs runtime dependencies
rem - Optionally downloads the Real-ESRGAN binary (offer to run scripts\download_realesrgan.py)
rem ============================================================================

cd /d "%~dp0"

echo.
echo === Image Upscaler Pro - Setup ===
echo.

rem -- Pick a Python launcher ---------------------------------------------------
set "PYEXE="
where py >nul 2>nul && set "PYEXE=py -3"
if not defined PYEXE (
    where python >nul 2>nul && set "PYEXE=python"
)
if not defined PYEXE (
    echo [ERROR] Python tidak ditemukan. Install Python 3.10+ dari https://python.org dulu.
    echo         Pastikan opsi "Add python.exe to PATH" dicentang.
    pause
    exit /b 1
)

echo Python: %PYEXE%
%PYEXE% --version
if errorlevel 1 (
    echo [ERROR] Gagal menjalankan Python.
    pause
    exit /b 1
)

rem -- Create or reuse venv -----------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    echo Virtual env sudah ada di .venv  (akan dipakai ulang^).
) else (
    echo Membuat virtual env di .venv ...
    %PYEXE% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Gagal membuat venv.
        pause
        exit /b 1
    )
)

set "VENV_PY=.venv\Scripts\python.exe"

rem -- Upgrade pip & install deps ----------------------------------------------
echo.
echo Upgrade pip ...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARN] Gagal upgrade pip - lanjut tetap pakai versi yang ada.
)

echo.
echo Install dependencies (requirements.txt^) ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Gagal install dependencies. Cek koneksi internet dan log di atas.
    pause
    exit /b 1
)

rem -- Optional: Real-ESRGAN binary --------------------------------------------
echo.
set /p DL_RE=Download Real-ESRGAN AI binary sekarang? (y/N): 
if /i "%DL_RE%"=="y" (
    "%VENV_PY%" scripts\download_realesrgan.py
    if errorlevel 1 (
        echo [WARN] Gagal download Real-ESRGAN. Bisa coba lagi nanti:
        echo         .venv\Scripts\python.exe scripts\download_realesrgan.py
    )
)

echo.
echo === Setup selesai ===
echo Jalankan app dengan: run.bat
echo.
pause
endlocal
