@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not on PATH. Install Python 3.11+ or use "py -3" instead.
  exit /b 1
)

where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required to build the frontend. Install from https://nodejs.org/
  exit /b 1
)

python -m pip install -q -r backend\requirements.txt -r requirements-build.txt
python backend\build_gui_exe.py
if errorlevel 1 exit /b 1
echo.
echo Done. Run: dist\CADMation_GUI.exe
