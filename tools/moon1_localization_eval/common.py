"""Serialization only; no reference or solver data loading side effects."""
import hashlib,json,subprocess
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/moon1_localization_eval'
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
 if isinstance(x,Path):return str(x)
 return x
def canonical(x):return json.dumps(clean(x),sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def filehash(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,indent=2,allow_nan=False);f.write('\n')
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
def sources():
 paths=list((ROOT/'tools/moon1_localization_eval').glob('*.py'))+[DOC/'CONFIG.json',DOC/'SOLVER.json',DOC/'INPUT_PROTOCOL.md']
 paths += [ROOT/p for p in ['tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py','sim/isaac_lab/moon1/antenna_geometry.py']]
 return {str(p.relative_to(ROOT)):filehash(p) for p in paths}
