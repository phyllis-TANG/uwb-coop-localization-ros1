"""B native-v2 provenance/IO; no A estimator or policy imports."""
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
A_SHA='12a1d94379b58c5a759b1698425fb90d48587609'
A_DELIVERY='c5563df609f52df64727cf2618381abfda3cd3bb'


def require(ok,text):
    if not ok:raise ValueError(text)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda:f.read(1024**2),b''):h.update(part)
    return h.hexdigest()


def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def lines(path):
    with gzip.open(path,'rt') as f:return [json.loads(s) for s in f]


def write_lines(path,rows):
    with Path(path).open('xb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:
        for row in rows:z.write((json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def begin(output,role):
    output=Path(output).resolve();require(not any((p/'.git').exists() for p in [output,*output.parents]),'Git-external output required');output.mkdir(parents=True,exist_ok=False)
    v=dict(role=role,status='IN_PROGRESS',created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command_argv=[sys.executable]+sys.argv,
      code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
      source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.glob('*')) if p.is_file() and p.suffix in ('.py','.json')},inputs=[],estimator_runs=0,started=time.monotonic())
    write(output/'checkpoint.json',{k:x for k,x in v.items() if k!='started'});return v


def finish(output,v,error=None):
    v['elapsed_s']=time.monotonic()-v.pop('started');v['status']='FAILED' if error is not None else 'DONE'
    if error is not None:v['error']=str(error)
    v['outputs']=[dict(relative_path=str(p.relative_to(output)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(Path(output).rglob('*')) if p.is_file() and p.name!='run.json'];write(Path(output)/'run.json',v)
