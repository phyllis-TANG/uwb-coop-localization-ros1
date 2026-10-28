"""Task-owned immutable evidence helpers."""
import gzip,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
CONFIG=json.loads((HERE/'development_config.json').read_text())
METHODS=CONFIG['methods'];SCENARIOS=CONFIG['scenarios'];SEED=101
ART=Path('/home/ubuntu22/uwb-cooperative-influence-minimal-20261028-artifacts')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return [json.loads(l) for l in f if l.strip()]
def write(p,rows):
 with Path(p).open('xb') as f,gzip.GzipFile(fileobj=f,filename='',mode='wb',mtime=0) as z:
  for r in rows:z.write((json.dumps(r,sort_keys=True,allow_nan=False)+'\n').encode())
def state():return dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)))
def sources():
 lock=json.loads((HERE/'source_lock.json').read_text())['files']
 for p,s in lock.items():assert sha(ROOT/p)==s,p
 return {**lock,**{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ['.py','.json']}}
