"""Serialization and repository-local read-only dependencies."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
DOC=ROOT/'docs/research/field_moon1_integration'
SOURCE=ROOT/'docs/field_tests/field_observation_readiness/results'
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,np.ndarray): return clean(x.tolist())
 if isinstance(x,np.generic): return clean(x.item())
 if isinstance(x,dict): return {k:clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)): return [clean(v) for v in x]
 if isinstance(x,float) and not np.isfinite(x): return None
 return x
def read(p): return json.loads(Path(p).read_text())
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f: json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n');f.flush();__import__('os').fsync(f.fileno())
