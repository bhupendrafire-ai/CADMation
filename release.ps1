# CADMation Release Automation Script
# Version: 3.6.7

$Version = "3.6.7"
$InstallerName = "CADMation_v$($Version)_Setup.exe"
$InstallersDir = Join-Path $PSScriptRoot "installers"

Write-Host "--- CADMation Professional Release Process v$Version ---" -ForegroundColor Cyan

# 1. Ensure Installers directory exists
if (-not (Test-Path $InstallersDir)) {
    Write-Host "Creating installers directory..."
    New-Item -ItemType Directory -Path $InstallersDir -Force | Out-Null
}

# 2. Build Frontend
Write-Host "`n[1/4] Building Frontend..." -ForegroundColor Yellow
Set-Location -Path (Join-Path $PSScriptRoot "frontend")
npm install
npm run build
Set-Location -Path $PSScriptRoot

# 3. Build Backend EXE (PyInstaller)
Write-Host "`n[2/4] Building Backend Standalone EXE..." -ForegroundColor Yellow
# Ensure requirements are met
py -m pip install -q -r backend\requirements.txt -r requirements-build.txt
py backend\build_gui_exe.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller build failed!" -ForegroundColor Red
    exit 1
}

# 4. Generate Professional Installer (Inno Setup)
Write-Host "`n[3/4] Generating Professional Installer..." -ForegroundColor Yellow
$ISCC = "C:\Program Files (x86)\Inno Setup 6\iscc.exe"
if (-not (Test-Path $ISCC)) {
    Write-Host "ERROR: Inno Setup (ISCC.exe) not found at $ISCC" -ForegroundColor Red
    exit 1
}

& $ISCC "$PSScriptRoot\setup.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installer generation failed!" -ForegroundColor Red
    exit 1
}

# 5. Cleanup and Archive
Write-Host "`n[4/4] Finalizing Release..." -ForegroundColor Yellow
$GeneratedInstaller = Join-Path $InstallersDir "CADMation_v$($Version)_Setup.exe"

if (Test-Path $GeneratedInstaller) {
    Write-Host "`nSUCCESS! Release v$Version is ready." -ForegroundColor Green
    Write-Host "Installer: $GeneratedInstaller" -ForegroundColor Cyan
} else {
    Write-Host "Installer was not found after build!" -ForegroundColor Red
    exit 1
}

Write-Host "`nDone."
