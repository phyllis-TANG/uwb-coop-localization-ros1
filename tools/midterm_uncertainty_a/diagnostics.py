"""Small explicit diagnostic interface; no estimator, optimizer, ridge or inferred layout.
J_data and J_prior are already whitened by the ESTIMATOR's weights.
actual_noise is covariance in those whitened DATA coordinates, not raw metres.
"""
from dataclasses import dataclass
from functools import lru_cache
import numpy as np
from scipy.stats import chi2

@dataclass(frozen=True)
class Layout:
    names: tuple
    units: tuple
    position_blocks: tuple  # tuples (car, epoch, x_index, y_index), explicit
    bias_index: object
    scales: tuple
    data_rows: int
    prior_rows: int
    whitening: str

@dataclass(frozen=True)
class Noise:
    kind: str  # identity or full, in estimator-whitened coordinates
    dimension: int
    covariance: object = None

def information(j,scales,rtol=1e-8):
    n=len(scales);j=np.asarray(j,float);d=np.asarray(scales,float)
    if j.ndim!=2 or j.shape[1]!=n:raise ValueError('Jacobian/layout dimension mismatch')
    if not np.isfinite(j).all():return dict(reason='NONFINITE_J',rank=None,covariance=None)
    _,s,v=np.linalg.svd(j*d,full_matrices=True)
    rank=int(np.sum(s>s[0]*rtol)) if len(s) and s[0]>0 else 0
    cov=None;reason='RANK_DEFICIENT'
    if rank==n:
        cov=(d[:,None]*v.T/s**1)@(d[:,None]*v.T/s**1).T
        cov=(cov+cov.T)/2
        if not np.isfinite(cov).all():cov=None;reason='NONFINITE_COVARIANCE'
        else:reason='AVAILABLE'
    null=d[:,None]*v[rank:].T
    return dict(reason=reason,rank=rank,dimension=n,singular_values=s,condition=float(s[0]/s[-1]) if rank==n else None,
                rank_sensitivity={str(t):int(sum(s>s[0]*t)) if len(s) else 0 for t in [1e-6,1e-8,1e-10,1e-12]},nullspace=null,covariance=cov)

@lru_cache(None)
def quantile(level,dimension):return float(chi2.ppf(level,dimension))

def block_metrics(cov,indices,error,levels=(.95,.99)):
    out=dict(available=False,reason='GLOBAL_COVARIANCE_UNAVAILABLE',covariance=None,q=None,trace=None,levels={})
    if cov is None:return out
    c=cov[np.ix_(indices,indices)];e=np.asarray(error)
    if not np.isfinite(c).all():out['reason']='NONFINITE_MARGINAL';return out
    eigen=np.linalg.eigvalsh(c)
    if eigen[0]<=0:out['reason']='NONPOSITIVE_MARGINAL';return out
    q=float(e@np.linalg.solve(c,e))
    out.update(available=True,reason='AVAILABLE',covariance=c,q=q,trace=float(np.trace(c)))
    for level in levels:
        threshold=quantile(level,len(indices))
        item=dict(covered=bool(q<=threshold),threshold=threshold,semi_axes=np.sqrt(threshold*eigen))
        if len(indices)==2:item['area']=float(np.pi*threshold*np.sqrt(np.linalg.det(c)))
        out['levels'][str(level)]=item
    return out

def diagnose(*,state,error,j_data,j_prior,layout,actual_noise,numerical_status,rtol=1e-8,levels=(.95,.99)):
    n=len(layout.names);x=np.asarray(state,float);err=np.asarray(error,float);a=np.asarray(j_data,float);l=np.asarray(j_prior,float)
    if len(layout.units)!=n or len(layout.scales)!=n or len(set(layout.names))!=n:raise ValueError('Explicit unique names, units and scales required')
    if x.shape!=(n,) or err.shape!=(n,) or a.shape!=(layout.data_rows,n) or l.shape!=(layout.prior_rows,n):raise ValueError('Explicit state/observation contract mismatch')
    if not layout.whitening or not all(u=='m' for u in layout.units) or min(layout.scales)<=0:raise ValueError('Current interface supports metre states and explicit positive scales only')
    if actual_noise.dimension!=layout.data_rows:raise ValueError('Noise coordinate dimension mismatch')
    for car,t,i,k in layout.position_blocks:
        if i==k or not (0<=i<n and 0<=k<n):raise ValueError('Invalid explicit position indices')
    if layout.bias_index is not None and not (0<=layout.bias_index<n):raise ValueError('Invalid explicit bias index')
    if actual_noise.kind=='identity':omega=None
    elif actual_noise.kind=='full':
        omega=np.asarray(actual_noise.covariance,float)
        if omega.shape!=(layout.data_rows,layout.data_rows) or not np.isfinite(omega).all() or not np.allclose(omega,omega.T,atol=1e-12) or np.linalg.eigvalsh(omega)[0]<-1e-12:raise ValueError('Actual whitened covariance must be finite symmetric PSD')
    else:raise ValueError('Noise kind must be explicit identity/full')
    if not np.isfinite(x).all() or not np.isfinite(err).all():raise ValueError('Nonfinite state/error; caller must record unavailable evidence')
    data=information(a,layout.scales,rtol);total=information(np.vstack([a,l]),layout.scales,rtol)
    c=total['covariance'];noise=None
    if c is not None:
        gain=c@a.T;noise=gain@gain.T if omega is None else gain@omega@gain.T;noise=(noise+noise.T)/2
        if not np.isfinite(noise).all():noise=None
    matrices={'total_curvature':c,'fixed_prior_noise':noise,'data_only':data['covariance']}
    out=dict(layout=layout,numerical_status=dict(numerical_status),data=data,total=total,matrices=matrices,positions={},bias={},coupling={})
    for name,cov in matrices.items():
        out['positions'][name]=[block_metrics(cov,[i,k],err[[i,k]],levels) for _,_,i,k in layout.position_blocks]
        bi=layout.bias_index
        if bi is not None:
            out['bias'][name]=block_metrics(cov,[bi],err[[bi]],levels)
            corr=[];r2=[]
            if cov is not None and cov[bi,bi]>0:
                for _,_,i,k in layout.position_blocks:
                    ids=[i,k];p=cov[np.ix_(ids,ids)];v=cov[ids,bi]
                    corr.extend((v/np.sqrt(np.diag(p)*cov[bi,bi])).tolist())
                    r2.append(float(v@np.linalg.solve(p,v)/cov[bi,bi]) if np.linalg.eigvalsh(p)[0]>0 else None)
            out['coupling'][name]=dict(coordinate_correlations=corr,position_multiple_R2=r2)
    return out
