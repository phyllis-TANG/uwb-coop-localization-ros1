"""Verify and import only the exact fixed algorithm snapshot, in a fresh process."""
import hashlib,importlib,json,os,sys
from pathlib import Path
MANIFEST=json.loads(Path(__file__).with_name('frozen_manifest.json').read_text())
ROOT=Path(os.environ['PEER_GATE_FROZEN_ROOT']).resolve()
for name,value in MANIFEST['files'].items():
 if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value:raise RuntimeError('Frozen source mismatch: '+name)
sys.path.insert(0,str(ROOT/'tools/two_car_fixed_lag_fgo_v1'))
frontend=importlib.import_module('frontend');graph=importlib.import_module('graph');replay=importlib.import_module('replay');simulate=importlib.import_module('simulate');io=importlib.import_module('io_utils');legacy=importlib.import_module('legacy')
for module in (frontend,graph,replay,simulate,io,legacy):
 if not Path(module.__file__).resolve().is_relative_to(ROOT):raise RuntimeError('Module namespace collision: '+module.__name__)
