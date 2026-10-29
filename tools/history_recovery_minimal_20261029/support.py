"""Task-local evidence I/O; no estimator imports."""
import gzip, hashlib, json, os, subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DOC=ROOT/'docs/research/history_recovery_minimal_20261029'
EVIDENCE=Path(os.environ.get('HISTORY_SOURCE', '/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts/evidence-v1/unpacked/cooperative_influence_probe_20261028/evidence-v1'))
OUT=Path(os.environ.get('HISTORY_OUTPUT','/home/ubuntu22/uwb-history-recovery-minimal-20261029-artifacts'))
SET=json.loads((HERE/'settings.json').read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def digest(o):return hashlib.sha256(json.dumps(o,sort_keys=True,allow_nan=False).encode()).hexdigest()
def dump(p,o):Path(p).write_text(json.dumps(o,indent=2,sort_keys=True,allow_nan=False)+'\n')
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return [json.loads(l) for l in f if l.strip()]
def write(p,rows):
 with Path(p).open('xb') as f,gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as z:
  for r in rows:z.write((json.dumps(r,sort_keys=True,allow_nan=False)+'\n').encode())
def source_lock():return {str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.iterdir()) if p.suffix in ('.py','.json')}
def head():return subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
def config(case):return json.loads((EVIDENCE/'inputs'/case/'config.json').read_text())
def old(case,method):
 idx=json.loads((EVIDENCE/'RUN_INDEX.json').read_text())
 cell=next(c for c in idx['cells'] if c['case']==case and c['method']==method)
 return read(EVIDENCE/cell['path']/'updates.jsonl.gz')
