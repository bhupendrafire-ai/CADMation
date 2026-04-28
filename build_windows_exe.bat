@echo off
setlocal
cd /d "%~dp0"



where node >nul 2>nul
if errorlevel 1 (
  echo Node.js is required to build the frontend. Install from https://nodejs.org/
  exit /b 1
)

set CADMATION_GUI_EXE_NAME=CADMation_Enterprise
py -m pip install -q -r backend\requirements.txt -r requirements-build.txt
py backend\build_gui_exe.py
if errorlevel 1 exit /b 1
echo.
echo Done. Run: dist\CADMation_Enterprise.exe
