"""Task-A immutable inputs; no estimation or control dependencies."""
import csv,gzip,hashlib,json,subprocess,os
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
HEAD='1cc7713a7e48776474788a07a1b41040f9df9330';EXEC='312180ef51c6ea4ba394bc85618674ec36ff786d'
DOC='docs/field_tests/20261024_25/cooperative_influence_probe_20261028'
ART=Path(os.environ.get('TASK_A_ARTIFACTS','/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts'))
SCENARIOS=('nominal','car1_common_wall_bias');METHODS=('I','J','W025','C004','K004')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def dump(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n')
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return [json.loads(l) for l in f if l.strip()]
def table(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def csvwrite(p,rows):
 with Path(p).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def show(p):return subprocess.check_output(['git','show',HEAD+':'+p],cwd=ROOT)
