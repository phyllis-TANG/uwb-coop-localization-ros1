"""Exclusive output and provenance IO only. No estimator or quality policy."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):h.update(chunk)
    return h.hexdigest()


def write(path,obj):
    with Path(path).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def require(ok,reason):
    if not ok:raise ValueError(reason)


def begin(path,role):
    p=Path(path).resolve();require(not any((x/'.git').exists() for x in [p,*p.parents]),'results outside Git only');p.mkdir(parents=True,exist_ok=False)
    v=dict(role=role,status='IN_PROGRESS',created_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),command_argv=[sys.executable]+sys.argv,
      code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
      source_sha256={str(x.relative_to(ROOT)):sha(x) for x in sorted(HERE.glob('*')) if x.is_file() and x.suffix in ('.py','.json')},inputs=[],started=time.monotonic(),estimator_runs=0)
    write(p/'checkpoint.json',{k:x for k,x in v.items() if k!='started'});return v


def finish(path,v,error=None):
    v['elapsed_s']=time.monotonic()-v.pop('started');v['status']='FAILED' if error is not None else 'DONE'
    if error is not None:v['error']=str(error)
    v['outputs']=[dict(relative_path=str(x.relative_to(path)),sha256=sha(x),bytes=x.stat().st_size) for x in sorted(Path(path).rglob('*')) if x.is_file() and x.name!='run.json']
    write(Path(path)/'run.json',v)
