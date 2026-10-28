"""Load frozen kernels in isolated module namespaces; never edit their files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = 'ca8fbac4dbdf678074be5fb80bf6aff472d258e6'
LOCK = json.loads(Path(__file__).with_name('dependency_lock.json').read_text())
for name, digest in LOCK.items():
    if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != digest:
        raise RuntimeError('Frozen dependency changed: '+name)


def load(name, path, aliases=None):
    """Legacy absolute imports get temporary aliases, restored after execution."""
    saved = {k: sys.modules.get(k) for k in (aliases or {})}
    try:
        sys.modules.update(aliases or {})
        spec = importlib.util.spec_from_file_location(name, ROOT/path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        for key, value in saved.items():
            if value is None: sys.modules.pop(key, None)
            else: sys.modules[key] = value


two_legacy = load('_two_imu_f0_legacy', 'tools/two_car_fixed_lag_fgo_v1/legacy.py')
f0 = load('_two_imu_f0_graph', 'tools/two_car_fixed_lag_fgo_v1/graph.py', {'legacy': two_legacy})
f0_front = load('_two_imu_f0_front', 'tools/two_car_fixed_lag_fgo_v1/frontend.py', {'legacy': two_legacy, 'graph': f0})
single_legacy = load('_two_imu_single_legacy', 'tools/single_car_imu_fgo/legacy.py')
integration = load('_two_imu_integration', 'tools/single_car_imu_fgo/integration.py')
single = load('_two_imu_single_graph', 'tools/single_car_imu_fgo/graph.py', {'legacy': single_legacy, 'integration': integration})
f0_sim = load('_two_imu_f0_sim', 'tools/two_car_fixed_lag_fgo_v1/simulate.py')
