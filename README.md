# Robodrone-challenge


Guidelines

- Use the help of AI in building the simulator.
- fork this repo... then start the project.
- All team members should contributed alteast one times.
- In every 20 min , one contribution needed from a team.
- judging  criteria will be there 

# Drone Flight Training Simulator

Built with Python + the [Ursina](https://www.ursinaengine.org/) game engine
(which runs on Panda3D for high-performance hardware-accelerated rendering).

## Features

- Full 6-axis quadcopter flight model: throttle, pitch, roll, yaw
- Realistic physics: gravity, lift, tilt-based horizontal thrust, air drag
- Crash detection (hard landings, tilted landings, building collisions)
- 3D world with 30 procedurally placed buildings to navigate around
- 8 orange practice rings — fly through them to score points
- Two landing pads (HOME and PAD B) with precision-landing scoring
- Three camera modes: chase cam, FPV (first person view), high orbit
- Live HUD: altitude, speed, throttle %, score
- Runs at high frame rates with low-latency keyboard controls

## Controls

| Key          | Action                     |
|--------------|----------------------------|
| `SPACE`      | Throttle up                |
| `LEFT SHIFT` | Throttle down              |
| `W` / `S`    | Pitch forward / backward   |
| `A` / `D`    | Roll left / right          |
| `Q` / `E`    | Yaw left / right           |
| `R`          | Reset drone                |
| `C`          | Cycle camera modes         |
| `H`          | Toggle help overlay        |
| `ESC`        | Quit                       |

Tip: hover throttle is ~50%. Hold SPACE until you lift off, then feather it.

## How to build the .exe (Windows)

1. Install **Python 3.10 or newer** from https://python.org
   (check "Add Python to PATH" during install).
2. Create the project based on below given folder structure.
3. Double-click **`build.bat`**.
4. Your standalone executable appears at:

   ```
   dist\DroneFlightSimulator.exe
   ```

That single file can be copied to any Windows 10/11 PC and run directly —
no Python installation needed on the target machine.

## Run from source (optional, for development)

```
pip install -r requirements.txt
python main.py
```

## Project structure

```
drone-sim/
├── main.py           # entire simulator: physics, world, HUD, cameras
├── requirements.txt  # ursina + pyinstaller
├── build.bat         # one-click Windows EXE builder
└── README.md
```

## Flight model notes

- Lift is proportional to throttle; at ~50% throttle lift equals gravity
  (stable hover).
- Tilting (pitch/roll) redirects thrust horizontally, so you drift in the
  direction of tilt — just like a real quad.
- Air drag naturally slows the drone when you level out.
- Descending faster than 4.5 m/s, or touching down while tilted more than
  15°, counts as a crash.

