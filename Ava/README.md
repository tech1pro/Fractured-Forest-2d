# Fractured Forest: Echo of Seasons (Prototype)

Single-file Pygame prototype for a seasonal puzzle-platformer run.

## Requirements

- Python 3.10+
- `pygame` or `pygame-ce`

## Install (WSL Ubuntu)

```bash
cd /workspace/Fractured-Forest-2d/Ava
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pygame
# or: pip install pygame-ce
```

## Run

```bash
cd /workspace/Fractured-Forest-2d/Ava
source .venv/bin/activate
python fractured_forest.py
```

## Controls

- `A/D` or `Left/Right` - move
- `Space` - jump
- `Q` - cycle seasons (Spring -> Summer -> Autumn -> Winter)
- `R` - restart after win/fail

## Gameplay notes

- 960x540 at 60 FPS.
- 5-room run generated from a small template set.
- Seasonal gameplay changes:
  - Seasonal platforms (vines/ice)
  - Water behavior changes by season
  - Season-dependent hazards
  - Autumn wind zones
- Two random Echo Seeds per run modify movement/physics/rules.

## Troubleshooting

If WSL has no display server, run from a Linux desktop session or enable WSLg/X server.
