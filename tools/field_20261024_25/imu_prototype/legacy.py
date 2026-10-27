"""Load the frozen pose baseline by a unique module name, without modifying it."""
import ast
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / 'tools/field_20261024_25/causal_baselines'
spec = importlib.util.spec_from_file_location('uwb_imu_frozen_pose_baseline', BASE / 'model.py')
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)
# Read the original column constant without importing a second module called replay.
for node in ast.parse((BASE / 'replay.py').read_text()).body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'ESTIMATE_COLUMNS' for t in node.targets):
        ESTIMATE_COLUMNS = ast.literal_eval(node.value)
        break
else:
    raise RuntimeError('Frozen estimate columns not found')
CARS, TAGS, WALLS = model.CARS, model.TAGS, model.WALLS
