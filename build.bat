@echo off

echo ========================================
echo Building Drone Flight Training Simulator
echo ========================================

python -m PyInstaller --onefile --windowed --name DroneFlightSimulator main.py

echo.
echo ========================================
echo BUILD COMPLETE
echo ========================================
echo.
echo EXE location:
echo dist\DroneFlightSimulator.exe
echo.

pause