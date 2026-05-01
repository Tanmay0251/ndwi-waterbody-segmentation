@echo off
REM ----------------------------------------------------------------------
REM  run.bat — one-click launcher for the NDWI Water-Body Segmentation app
REM
REM  We tried to ship a single .exe via PyInstaller, but the resulting
REM  binary was blocked by Windows Device Guard on the build machine
REM  (unsigned PyInstaller bootloaders are a known issue on locked-down
REM  Windows installs). A .bat that uses a normal Python venv works on
REM  every Windows machine the team tested.
REM
REM  What this does, in order:
REM    1. cd into the folder this .bat lives in (so relative paths work)
REM    2. if there's no venv yet, build one with `python -m venv venv`
REM    3. ensure pip is current and install requirements.txt
REM    4. launch `streamlit run app.py` — Streamlit opens the browser
REM
REM  Double-click to run; close the console window to stop the app.
REM ----------------------------------------------------------------------

setlocal

REM Always run from the .bat's own directory, no matter where it was launched from
cd /d "%~dp0"

REM ---- 1) make sure Python is available ----
where python >nul 2>&1
if errorlevel 1 (
    echo [run.bat] ERROR: Python is not on PATH.
    echo           Install Python 3.10+ from https://python.org and tick
    echo           "Add Python to PATH" during install, then re-run this file.
    pause
    exit /b 1
)

REM ---- 2) create the venv on first run ----
if not exist "venv\Scripts\python.exe" (
    echo [run.bat] No venv found — creating one in .\venv ...
    python -m venv venv
    if errorlevel 1 (
        echo [run.bat] ERROR: failed to create venv.
        pause
        exit /b 1
    )
)

REM ---- 3) install dependencies (idempotent — pip is fast on the second run) ----
echo [run.bat] Installing/updating requirements ...
"venv\Scripts\python.exe" -m pip install --upgrade pip >nul
"venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [run.bat] ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)

REM ---- 4) launch Streamlit ----
echo.
echo [run.bat] Starting Streamlit. A browser tab should open shortly.
echo            Press Ctrl+C in this window (or just close it) to stop.
echo.
"venv\Scripts\streamlit.exe" run app.py

endlocal
