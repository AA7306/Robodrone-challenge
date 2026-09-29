@echo off
cd /d "%~dp0"

echo ========================================
echo Building Drone Flight Training Simulator
echo ========================================

python -m pip install -r requirements.txt

python -m PyInstaller --onefile --windowed --noconfirm --name DroneFlightSimulator --collect-all ursina main.py

echo.
echo ========================================
echo BUILD COMPLETE
echo ========================================
echo.
echo EXE location:
echo dist\DroneFlightSimulator.exe
echo.

pause
