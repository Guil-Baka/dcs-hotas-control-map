# Build script for HOTAS Layout Editor
# This script builds the Python project into a standalone .exe file using PyInstaller

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "HOTAS Layout Editor - Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if PyInstaller is installed
Write-Host "Checking for PyInstaller..." -ForegroundColor Yellow
$PyInstallerCheck = pip list | Select-String -Pattern "pyinstaller"
if (-not $PyInstallerCheck) {
    Write-Host "PyInstaller not found. Installing..." -ForegroundColor Yellow
    pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install PyInstaller" -ForegroundColor Red
        exit 1
    }
}
Write-Host "PyInstaller is ready" -ForegroundColor Green
Write-Host ""

# Check if Pillow is installed
Write-Host "Checking for Pillow (PIL)..." -ForegroundColor Yellow
$PillowCheck = pip list | Select-String -Pattern "pillow"
if (-not $PillowCheck) {
    Write-Host "Pillow not found. Installing..." -ForegroundColor Yellow
    pip install pillow
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to install Pillow" -ForegroundColor Red
        exit 1
    }
}
Write-Host "Pillow is ready" -ForegroundColor Green
Write-Host ""

# Clean old builds
Write-Host "Cleaning old build files..." -ForegroundColor Yellow
if (Test-Path ".\build") {
    Remove-Item -Path ".\build" -Recurse -Force
    Write-Host "  Removed .\build" -ForegroundColor Gray
}
if (Test-Path ".\dist") {
    Remove-Item -Path ".\dist" -Recurse -Force
    Write-Host "  Removed .\dist" -ForegroundColor Gray
}
if (Test-Path ".\bin") {
    Remove-Item -Path ".\bin" -Recurse -Force
    Write-Host "  Removed .\bin" -ForegroundColor Gray
}
Get-Item -Path "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "Clean complete" -ForegroundColor Green
Write-Host ""

# Build the EXE
Write-Host "Building executable..." -ForegroundColor Yellow
Write-Host "This may take 1-2 minutes..." -ForegroundColor Gray
Write-Host ""

pyinstaller `
    --onefile `
    --windowed `
    --name "HOTAS Layout Editor" `
    --distpath ".\bin" `
    --hidden-import=PIL `
    --hidden-import=PIL.Image `
    editor.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "Build successful!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "EXE location:" -ForegroundColor Cyan
    Write-Host "  .\bin\HOTAS Layout Editor.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "To run the program:" -ForegroundColor Cyan
    Write-Host "  .\bin\HOTAS Layout Editor.exe" -ForegroundColor White
    Write-Host ""
    Write-Host "To distribute:" -ForegroundColor Cyan
    Write-Host "  Copy '.\bin\HOTAS Layout Editor.exe' to any Windows computer" -ForegroundColor White
    Write-Host "  (Python installation not required)" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "Build failed!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    exit 1
}

# Cleanup build artifacts
Write-Host "Cleaning up temporary files..." -ForegroundColor Yellow
if (Test-Path ".\build") {
    Remove-Item -Path ".\build" -Recurse -Force
    Write-Host "  Removed .\build" -ForegroundColor Gray
}
Get-Item -Path "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force
Write-Host "Cleanup complete" -ForegroundColor Green
Write-Host ""

Write-Host "Done!" -ForegroundColor Green
