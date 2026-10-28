"""Immutable external outputs and explicit SHA provenance."""
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def dump(path,value):Path(path).write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n')
def lines(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else open(path)) as f:
        for line in f:
            if line.strip():yield json.loads(line)

def write_lines(path,rows):
    with Path(path).open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as f:
        for row in rows:f.write((json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())

def external(path):
    p=Path(path).resolve()
    if p==ROOT or ROOT in p.parents:raise ValueError('Git-external output required')
    return p

def git_state():
    return dict(code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()))

def sources():
    lock=json.loads((HERE/'dependency_lock.json').read_text())
    return {**{k:sha(ROOT/k) for k in lock},**{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.json')}}

def utc():return datetime.now(timezone.utc).isoformat()
