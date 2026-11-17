"""Noise-scale study: explicit six-epoch XY model, read-only PR112 primitives."""
import sys,json,gzip,hashlib,copy,importlib.util,csv
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_geometry_perturbation_a'
OLD=ROOT/'docs/research/midterm_noise_scale_a'
spec=importlib.util.spec_from_file_location('pr112_common',ROOT/'tools/midterm_weak_geometry_a/common.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
read,save,digest,canonical,csvsave=legacy.read,legacy.save,legacy.digest,legacy.canonical,legacy.csvsave
records,write_records,initials,groups,compact=legacy.records,legacy.write_records,legacy.initials,legacy.groups,legacy.compact
objective,algebra,ellipse=legacy.objective,legacy.algebra,legacy.ellipse
SOURCE=legacy.SOURCE

def cached_npz(path):
    """Each member decompressed once; all subsequent access is an ndarray lookup."""
    with np.load(path,allow_pickle=False) as archive:return {k:archive[k] for k in archive.files}

def exact_hessian(u,m,x):
    # PR112 exact range Hessian, valid for B1/B2/B3 peer model only.
    r,j=objective(u,m,x);h=j.T@j;p=x[:24].reshape(6,2,2);a=np.array(u['obs']['anchors']);sigma=u['obs']['range_sigma'];eye=np.eye(2)
    for t in range(6):
        for car in range(2):
            ix=slice(4*t+2*car,4*t+2*car+2)
            for k in range(4):
                delta=p[t,car]-a[k];dist=np.linalg.norm(delta);v=delta/dist;h[ix,ix]+=r[9*t+4*car+k]*(eye-np.outer(v,v))/(sigma*dist)
        delta=p[t,1]-p[t,0];dist=np.linalg.norm(delta);v=delta/dist;s=r[9*t+8]*(eye-np.outer(v,v))/(sigma*dist);i=slice(4*t,4*t+2);k=slice(4*t+2,4*t+4);h[i,i]+=s;h[k,k]+=s;h[i,k]-=s;h[k,i]-=s
    return h

def project_weak(g,e,near_rtol=.001):
    ev,v=np.linalg.eigh(g);tol=max(near_rtol*abs(ev[0]),100*np.finfo(float).eps*np.linalg.norm(g,2));mask=ev<=ev[0]+tol;w=v[:,mask];gp=w.T@g@w;ep=w.T@e@w;rp=ep-gp;n=w.shape[1]
    return dict(weak_dimension=n,near_eigenvalue_tolerance=float(tol),gn_min=float(ev[0]),gn_next=float(ev[n]) if n<len(ev) else None,weak_gn=float(np.trace(gp)/n),weak_exact=float(np.trace(ep)/n),weak_second_order=float(np.trace(rp)/n),weak_second_order_signed_ratio=float(np.trace(rp)/np.trace(gp)) if np.trace(gp)>0 else None,weak_relative_norm=float(np.linalg.norm(rp,2)/np.linalg.norm(gp,2)) if np.linalg.norm(gp,2)>0 else None,weak_exact_min=float(np.linalg.eigvalsh(ep)[0]),weak_exact_max=float(np.linalg.eigvalsh(ep)[-1]),overall_relative_frobenius=float(np.linalg.norm(e-g)/np.linalg.norm(g)),exact_min=float(np.linalg.eigvalsh(e)[0])),w,gp,ep

def weak_curvature(u,m,x):
    _,j=objective(u,m,x);d=np.r_[np.ones(24),.1] if m=='B2' else np.ones(24);g=(j*d).T@(j*d);e=exact_hessian(u,m,x)*d[:,None]*d
    return project_weak(g,e)

# Preserve exclusive atomic writes and fsync the directory entry for attempts/results.
_exclusive_save=save
def save(path,value):
    import os
    _exclusive_save(path,value)
    fd=os.open(str(Path(path).parent),os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
