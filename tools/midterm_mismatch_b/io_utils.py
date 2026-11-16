"""No optimizer imports; canonical evidence IO and fixed pairing statistics."""
import csv,gzip,hashlib,json,os,tempfile
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_mismatch_b'
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def read(p):
    p=Path(p);raw=p.read_bytes();return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);raw=canonical(x)
    if p.suffix=='.gz':raw=gzip.compress(raw,mtime=0)
    fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.link(tmp,p)
    finally:os.unlink(tmp)
def csvsave(p,rows):
    with Path(p).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows)
def interval(values,planned,c,complete=True):
    a=np.asarray(values,float);n=len(a);s=c['statistics'];r=dict(planned=planned,n_valid=n,mean=float(a.mean()) if n else None,lower=None,upper=None,ci_status=None)
    if not complete:r['ci_status']='INCOMPLETE'
    elif n<s['minimum_valid_seeds']:r['ci_status']='INSUFFICIENT_VALID_SEEDS'
    elif (planned-n)/planned>s['maximum_missing_fraction_for_ci']:r['ci_status']='EXCESS_MISSING'
    else:
        rng=np.random.Generator(np.random.PCG64(s['bootstrap_seed']));means=a[rng.integers(0,n,(s['bootstrap_repetitions'],n))].mean(axis=1);alpha=(1-s['confidence'])/2
        lo,hi=np.quantile(means,[alpha,1-alpha]);r.update(lower=float(lo),upper=float(hi),ci_status='POINTWISE' if n==planned else 'CONDITIONAL_VALID_SUBSET')
    return r
