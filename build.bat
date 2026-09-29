@echo off
echo === Drone Flight Simulator - EXE builder ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto fail
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DroneFlightSimulator --collect-all ursina --collect-all panda3d --collect-all panda3d_gltf --collect-all panda3d_simplepbr main.py
if errorlevel 1 goto fail
echo.
echo SUCCESS: dist\DroneFlightSimulator.exe
pause
exit /b 0
:fail
echo BUILD FAILED - check Python 3.10+ is installed and on PATH.
pause
exit /b 1
