"""Task-only file identities, immutable outputs and plain records."""
import gzip,hashlib,json,subprocess
from pathlib import Path
from datetime import datetime,timezone
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SCENARIOS=('nominal','peer_bias','car1_common_wall_bias');SEEDS=(101,211,307);METHODS=('D0','D1','D2','D3')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return [json.loads(s) for s in f if s.strip()]
def write(p,rows):
 with Path(p).open('xb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z:
  for r in rows:z.write((json.dumps(r,sort_keys=True,allow_nan=False)+'\n').encode())
def external(p):
 p=Path(p).resolve()
 if p==ROOT or ROOT in p.parents:raise ValueError('External task directory required')
 return p
def state():return {'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip())}
def sources():
 lock=json.loads((HERE/'source_lock.json').read_text())['files']
 for p,s in lock.items():
  if sha(ROOT/p)!=s:raise ValueError('Pinned dependency changed '+p)
 return {**lock,**{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.json')}}
def utc():return datetime.now(timezone.utc).isoformat()
