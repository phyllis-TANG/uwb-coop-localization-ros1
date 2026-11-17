"""Shared read-only contracts; source models are imported without modifications."""
import csv,gzip,hashlib,json,sys
from pathlib import Path
import numpy as np
import scipy.optimize
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_joint_coverage_a'
CFG=json.loads((DOC/'CONFIG.json').read_text())
VIEWS=CFG['views'];METHODS=['B0','B1','B2','B3_full_oracle']
def forbidden(*args,**kwargs):raise RuntimeError('Optimizer forbidden: saved-state analysis only')
scipy.optimize.least_squares=forbidden
sys.path.insert(0,str(ROOT/'tools/midterm_mismatch_b'))
sys.path.insert(0,str(ROOT/'tools/midterm_uncertainty_a'))
import readback as rb
from diagnostics import information,block_metrics,quantile
from io_utils import digest

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,obj):
    with Path(p).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
def csvwrite(p,rows):
    with (gzip.open(p,'xt',newline='') if str(p).endswith('.gz') else Path(p).open('x',newline='')) as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows)
def csvread(p):
    with (gzip.open(p,'rt') if str(p).endswith('.gz') else Path(p).open()) as f:return list(csv.DictReader(f))
def read_shard(p):
    units={};records=[];meta=None
    with gzip.open(p,'rt') as f:
        for line in f:
            row=json.loads(line);v=row['value']
            if row['type']=='RUN':assert meta is None;meta=v
            elif row['type']=='INPUT':
                key=v['condition']['id']+'-s'+str(v['seed']);assert key not in units;units[key]=v
            elif row['type']=='METHOD':records.append(v)
            else:raise ValueError(row['type'])
    return meta,units,records

def data_indices(method):
    if method not in METHODS:raise ValueError('Explicit method required')
    return np.array([9*t+l for t in range(6) for l in range(8 if method=='B0' else 9)])
def omega(method,model):
    ids=data_indices(method);t=np.arange(54)//9;l=np.arange(54)%9
    if model=='iid_004':r=np.eye(54)
    elif model=='iid_008':r=np.eye(54)*4
    elif model=='ar1_07':r=(l[:,None]==l[None,:])*.7**abs(t[:,None]-t[None,:])
    else:raise ValueError('Unknown explicit noise model')
    out=np.eye(len(ids)+20);out[:len(ids),:len(ids)]=r[np.ix_(ids,ids)];return out
