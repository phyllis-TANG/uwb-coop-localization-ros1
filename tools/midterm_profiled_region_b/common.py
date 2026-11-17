from pathlib import Path
import sys,json,hashlib,gzip,platform,decimal,os
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_profiled_region_b'
LEGACY=ROOT/'tools/midterm_nonlinear_region_b'
sys.path.insert(0,str(LEGACY))
import interval as I
import invert as OLD
import check as OC
import inputs as OINPUT

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return json.load(f)
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with (gzip.open(p,'xt') if str(p).endswith('.gz') else p.open('x')) as f:json.dump(x,f,separators=(',',':'))
 with p.open('rb') as f:os.fsync(f.fileno())
def config():return read(DOC/'CONFIG.json')
def projected(m):
 return dict(m,domain=m['domain'][:2],bias_interval=m['domain'][2] if m['unknown_bias'] else [m['known_bias']]*2)
def versions():
 import numpy
 return dict(python=platform.python_version(),libmpdec=decimal.__libmpdec_version__,numpy=numpy.__version__)
