"""Read-only F0 reuse, refused if any pinned dependency changes."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
LOCK = json.loads(Path(__file__).with_name('dependency_lock.json').read_text())
for name, expected in LOCK['files'].items():
    if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
        raise RuntimeError('Pinned dependency changed: ' + name)
sys.path.insert(0, str(ROOT / 'tools'))
from single_car_fixed_lag import (BoundaryPrior, Objective as PoseObjective,
    WindowGraph as PoseWindowGraph, FixedLagReplay, initial_prior)
from single_car_sequential_replay import Event, antenna, predict, rotation, wrap

CARS = ('car1', 'car2')
