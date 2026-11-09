@echo off
REM Build script for HOTAS Layout Editor
REM This script builds the Python project into a standalone .exe file using PyInstaller

cls
echo.
echo ========================================
echo HOTAS Layout Editor - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
echo Checking for PyInstaller...
pip list | find "pyinstaller" >nul
if errorlevel 1 (
    echo PyInstaller not found. Installing...
    pip install pyinstaller
    if errorlevel 1 (
        echo Failed to install PyInstaller
        pause
        exit /b 1
    )
)
echo PyInstaller is ready
echo.

REM Check if Pillow is installed
echo Checking for Pillow (PIL)...
pip list | find "pillow" >nul
if errorlevel 1 (
    echo Pillow not found. Installing...
    pip install pillow
    if errorlevel 1 (
        echo Failed to install Pillow
        pause
        exit /b 1
    )
)
echo Pillow is ready
echo.

REM Clean old builds
echo Cleaning old build files...
if exist "build" (
    rmdir /s /q "build"
    echo   Removed ./build
)
if exist "dist" (
    rmdir /s /q "dist"
    echo   Removed ./dist
)
del /q "*.spec" 2>nul
echo Clean complete
echo.

REM Build the EXE
echo Building executable...
echo This may take 1-2 minutes...
echo.

python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --name "HOTAS Layout Editor" ^
    --distpath ".\bin" ^
    --hidden-import=PIL ^
    --hidden-import=PIL.Image ^
    editor.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo Build failed!
    echo ========================================
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build successful!
echo ========================================
echo.
echo EXE location:
echo   .\bin\HOTAS Layout Editor.exe
echo.
echo To run the program:
echo   .\bin\HOTAS Layout Editor.exe
echo.
echo To distribute:
echo   Copy ".\bin\HOTAS Layout Editor.exe" to any Windows computer
echo   (Python installation not required)
echo   Copy the adjacent "layouts" folder too if you want to keep your saved layouts.
echo.

REM Cleanup build artifacts
echo Cleaning up temporary files...
if exist "build" (
    rmdir /s /q "build"
    echo   Removed ./build
)
del /q "*.spec" 2>nul
echo Cleanup complete
echo.

echo Done!
pause
