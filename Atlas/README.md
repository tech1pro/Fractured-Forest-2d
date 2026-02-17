# Neon Velocity (Pygame Prototype)

A fast infinite runner / rhythm-ish lane dodger with polarity switching.

## Requirements
- Python 3.10+
- `pygame`

## Run (WSL Ubuntu)
```bash
cd /workspace/Fractured-Forest-2d/Atlas
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pygame
python neon_velocity.py
```

## Controls
- `W` / `Up Arrow`: move up a lane
- `S` / `Down Arrow`: move down a lane
- `Space`: toggle polarity (Neon Cyan ↔ Neon Magenta)
- `R`: restart after game over

## Gameplay Rules
- Obstacles spawn on the right and move left in one of 3 lanes.
- Match obstacle polarity with your player polarity to score.
- Hitting opposite polarity ends the run.
- Speed increases over time.
