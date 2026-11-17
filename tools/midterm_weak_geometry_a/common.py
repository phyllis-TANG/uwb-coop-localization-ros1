"""Explicit six-epoch XY contract; analysis imports no optimizer."""
import sys,json,gzip,hashlib,copy
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_weak_geometry_a'
OLD=ROOT/'docs/research/midterm_prior_mechanism_b'
sys.path.insert(0,str(ROOT/'tools/midterm_prior_mechanism_b'))
from io_utils import read,save,digest,canonical,csvsave
from math_model import objective,algebra,ellipse
CFG=read(DOC/'CONFIG.json'); SOURCE=read(OLD/'CONFIG.json')
def records(path):
    for line in gzip.open(path,'rt'):yield json.loads(line)
def write_records(path,rows):
    with gzip.GzipFile(filename=str(path),mode='xb',mtime=0) as f:
        for r in rows:f.write(canonical(r)+b'\n')
def initials(anchors,start):
    a=np.asarray(anchors,float);p=np.array(start,float).reshape(6,2,2);center=a.mean(0);s,v=np.linalg.eigh((a-center).T@(a-center));axis=np.array([1.,0.]) if abs(s[1]-s[0])<=1e-12*max(1,s[1]) else v[:,1]
    if axis[np.flatnonzero(abs(axis)>1e-12)[0]]<0:axis=-axis
    normal=np.array([-axis[1],axis[0]]);ref=p-2*((p-center)@normal)[...,None]*normal
    out={}
    for name,cars in [('I1',[0,1]),('I2',[0]),('I3',[1])]:
        z=p.copy();z[:,cars]=ref[:,cars];out[name]=z.ravel().tolist()
    out['I4']=(p+.5*normal).ravel().tolist();return out

def compact(s):return {k:v for k,v in s.items() if k not in ['residual','jacobian','gradient','scaled_gradient','information','analytic_covariance']}
def distance(a,b):return float(np.max(np.linalg.norm((np.array(a[:24])-b[:24]).reshape(12,2),axis=1)))
def groups(candidates,method,accepted_only=False):
    valid=[z for z in candidates if z['final']['endpoint_valid'] and (not accepted_only or z['final']['accepted'])];out=[]
    for z in sorted(valid,key=lambda v:(v['final']['cost'],v['init'])):
        s=z['final'];found=False
        for g in out:
            if all(distance(s['estimate'],y['final']['estimate'])<=CFG['group_position_m'] and (method!='B2' or abs(s['estimate'][-1]-y['final']['estimate'][-1])<=CFG['group_bias_m']) and abs(s['cost']-y['final']['cost'])<=CFG['group_cost_atol']+CFG['group_cost_rtol']*max(1,abs(s['cost']),abs(y['final']['cost'])) for y in g):g.append(z);found=True;break
        if not found:out.append([z])
    return out
