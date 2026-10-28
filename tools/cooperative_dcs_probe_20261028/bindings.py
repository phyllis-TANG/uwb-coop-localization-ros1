"""Import unmodified PR68 and its exact frozen F0; no shared module mutation."""
import importlib,json,os,sys
from common import ROOT,HERE,sha
lock=json.loads((HERE/'source_lock.json').read_text())
for p,s in lock['files'].items():
 if sha(ROOT/p)!=s:raise ValueError('Source mismatch '+p)
os.environ['PEER_GATE_FROZEN_ROOT']=str(ROOT)
sys.path.insert(0,str(ROOT/'tools/cooperative_peer_gate_probe_20261028'))
pinned=importlib.import_module('pinned');probe=importlib.import_module('probe');records=importlib.import_module('records')
base=pinned.graph;frontend=pinned.frontend;legacy=pinned.legacy;replay=pinned.replay

# The IRLS adapter deliberately depends on these fixed SciPy internals.
import scipy
from pathlib import Path
solver_lock=json.loads((HERE/'scipy_lock.json').read_text())
if scipy.__version__!=solver_lock['version']:raise ValueError('SciPy version differs from tested adapter')
for p,digest in solver_lock['files'].items():
 if sha(Path(scipy.__file__).parent/p)!=digest:raise ValueError('SciPy IRLS implementation changed '+p)
