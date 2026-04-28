# CADMation Installer Script
# This script installs the CADMation Copilot as a regular Windows application.

$Version = "2.3.0"
$AppName = "CADMation Enterprise v$Version"
$ExeName = "CADMation_Enterprise.exe"
$SourceExe = Join-Path $PSScriptRoot "dist\$ExeName"
$InstallDir = Join-Path $env:LOCALAPPDATA "CADMationEnterprise"
$TargetExe = Join-Path $InstallDir $ExeName
$IconPath = Join-Path $InstallDir "app_icon.ico"
$OriginalIcon = Join-Path $PSScriptRoot "backend\resources\app_icon.ico"

Write-Host "--- CADMation Professional Installer ---" -ForegroundColor Cyan

# 0. Terminate running instances and cleanup
Write-Host "Closing running instances..."
Get-Process "CADMation_Enterprise" -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Cleaning up old shortcuts..."
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$StartMenuPath = [Environment]::GetFolderPath("StartMenu")
Get-ChildItem -Path $DesktopPath -Filter "CADMation*.lnk" | Remove-Item -Force
Get-ChildItem -Path $StartMenuPath -Include "CADMation*.lnk" -Recurse | Remove-Item -Force

# 1. Check if the EXE exists
if (-not (Test-Path $SourceExe)) {
    Write-Host "ERROR: Built executable not found at $SourceExe" -ForegroundColor Red
    Write-Host "Please run the PyInstaller build first."
    exit 1
}

# 2. Create Installation Directory
if (-not (Test-Path $InstallDir)) {
    Write-Host "Creating installation directory: $InstallDir"
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# 3. Copy files
Write-Host "Installing application files..."
Copy-Item -Path $SourceExe -Destination $TargetExe -Force
if (Test-Path $OriginalIcon) {
    Copy-Item -Path $OriginalIcon -Destination $IconPath -Force
}

# 4. Create Shortcuts
$WshShell = New-Object -ComObject WScript.Shell

# Desktop Shortcut
Write-Host "Creating Desktop shortcut..."
$DesktopPath = [Environment]::GetFolderPath("Desktop")
$ShortcutFile = Join-Path $DesktopPath "$AppName.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutFile)
$Shortcut.TargetPath = $TargetExe
$Shortcut.WorkingDirectory = $InstallDir
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()

# Start Menu Shortcut
Write-Host "Creating Start Menu shortcut..."
$StartMenuPath = [Environment]::GetFolderPath("Programs")
$StartMenuDir = Join-Path $StartMenuPath "CADMation Enterprise"
if (-not (Test-Path $StartMenuDir)) {
    New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
}
$ShortcutFileStart = Join-Path $StartMenuDir "$AppName.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutFileStart)
$Shortcut.TargetPath = $TargetExe
$Shortcut.WorkingDirectory = $InstallDir
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = $IconPath
}
$Shortcut.Save()

Write-Host "`nInstallation Complete!" -ForegroundColor Green
Write-Host "You can now launch $AppName from your Desktop or Start Menu."
