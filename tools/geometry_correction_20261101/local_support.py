"""Private experiment IO, locks, scoped immutable imports."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DOC=ROOT/'docs/research/geometry_correction_20261101_private'
CARS=('car1','car2')
METHODS=('M2','M3','M3W025')
EPOCH=1_790_000_000_000_000_000

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def lines(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:
        for s in f:
            if s.strip():yield json.loads(s)
def write(p,rows):
    with Path(p).open('xb') as f,gzip.GzipFile(fileobj=f,filename='',mode='wb',mtime=0) as z:
        for r in rows:z.write((canonical(r)+'\n').encode())
def new(p):
    p=Path(p).resolve()
    if p==ROOT or ROOT in p.parents:raise ValueError('Git-external run outputs required')
    p.mkdir(parents=True,exist_ok=False);return p
def sources():
    lock=json.loads((HERE/'dependency_lock.json').read_text())
    for p,h in lock.items():
        if sha(ROOT/p)!=h:raise ValueError('Frozen dependency changed '+p)
    return {**lock,**{str(p.relative_to(ROOT)):sha(p) for p in HERE.iterdir() if p.suffix in ('.py','.json')}}
def gitstate():
    def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True).strip()
    return dict(code_commit=git('rev-parse','HEAD'),worktree_dirty=bool(git('status','--porcelain')))
def load(name,path,aliases=None):
    saved={k:sys.modules.get(k) for k in (aliases or {})}
    try:
        sys.modules.update(aliases or {})
        spec=importlib.util.spec_from_file_location(name,ROOT/path);mod=importlib.util.module_from_spec(spec);sys.modules[name]=mod;spec.loader.exec_module(mod);return mod
    finally:
        for k,v in saved.items():
            if v is None:sys.modules.pop(k,None)
            else:sys.modules[k]=v
def clone(fn,**bindings):
    ns=dict(fn.__globals__);ns.update(bindings)
    return types.FunctionType(fn.__code__,ns,fn.__name__,fn.__defaults__,fn.__closure__)
def protocol():
    p=DOC/'PROTOCOL.json'
    if sha(p)!=json.loads((DOC/'PROTOCOL.sha256.json').read_text())['sha256']:raise ValueError('Protocol SHA')
    return json.loads(p.read_text())
