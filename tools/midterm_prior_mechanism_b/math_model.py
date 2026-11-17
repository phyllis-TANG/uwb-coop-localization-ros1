"""Independent vectorized reconstruction and local linear algebra; no optimizer imports."""
import numpy as np
from scipy.stats import chi2,norm,ncx2
from scipy.integrate import quad

def reference(u,m):return np.r_[np.array(u['truth']).ravel(),u['condition']['bias_m']] if m=='B2' else np.array(u['truth']).ravel()
def objective(u,m,x):
    o=u['obs'];p=x[:24].reshape(6,2,2);a=np.array(o['anchors']);n=len(x);d=p[:,:,None,:]-a;dist=np.linalg.norm(d,axis=-1);dp=p[:,1]-p[:,0];peer=np.linalg.norm(dp,axis=-1);v=np.column_stack([dist.reshape(6,8),peer]);j=np.zeros((6,9,n))
    for t in range(6):
        for car in range(2):j[t,car*4:car*4+4,4*t+2*car:4*t+2*car+2]=d[t,car]/dist[t,car,:,None]
        j[t,8,4*t:4*t+2]=-dp[t]/peer[t];j[t,8,4*t+2:4*t+4]=dp[t]/peer[t]
    if m=='B2':v[:,8]+=x[-1];j[:,8,-1]=1
    y=np.array(o['ranges']).reshape(6,9)
    if m=='B3':y=y-np.array(u['oracle']).reshape(6,9)
    keep=8 if m=='B0' else 9;r=[((v-y)/o['range_sigma'])[:,:keep].ravel()];js=[j[:,:keep].reshape(-1,n)/o['range_sigma']];mj=np.zeros((20,n))
    for i in range(20):mj[i,i]=-1;mj[i,i+4]=1
    r.append((np.diff(p.reshape(6,4),axis=0).ravel()-o['movement'])/o['motion_sigma']);js.append(mj/o['motion_sigma']);pj=np.zeros((4,n));pj[:,:4]=np.eye(4)
    r.append((x[:4]-o['prior_center'])/o['prior_sigma']);js.append(pj/o['prior_sigma']);return np.concatenate(r),np.vstack(js)

def algebra(j,m,c,mechanism):
    scale=np.r_[np.ones(24)*c['solver']['position_scale_m'],c['solver']['bias_scale_m']] if m=='B2' else np.ones(24)*c['solver']['position_scale_m'];u,s,vt=np.linalg.svd(j*scale,full_matrices=False);rank=int(sum(s>s[0]*c['information']['rank_relative_tolerance']));out=dict(rank=rank,dimension=len(scale),singular_values=s.tolist(),status='RANK_DEFICIENT',gain=None,curvature=None,mechanism_noise=None)
    if rank<len(scale):return out
    k=(scale[:,None]*vt.T/s)@u.T;cov=k@k.T;kn=k if mechanism=='random_correct' else k[:,:-4];noise=kn@kn.T
    if not np.isfinite(np.r_[cov.ravel(),noise.ravel()]).all():out['status']='NONFINITE_COVARIANCE';return out
    out.update(status='AVAILABLE',gain=k,curvature=(cov+cov.T)/2,mechanism_noise=(noise+noise.T)/2);return out

def deterministic_rhs(u,m):
    nrange=48 if m=='B0' else 54;v=np.zeros(nrange+24)
    if m=='B1':v[8:54:9]=u['condition']['bias_m']/u['obs']['range_sigma']
    if u['condition']['mechanism']=='fixed_survey':v[-4:]=(np.array(u['obs']['prior_center'])-np.array(u['truth'])[0].ravel())/u['obs']['prior_sigma']
    return v

def linear_components(u,m,c):
    x=reference(u,m);r,j=objective(u,m,x);a=algebra(j,m,c,u['condition']['mechanism']);mu=None if a['gain'] is None else a['gain']@deterministic_rhs(u,m);return x,r,j,a,mu

def ellipse(cov,error,c):
    if cov is None:return dict(reason='GLOBAL_UNAVAILABLE',q=None,trace=None,area95=None,eigenvalues=None)
    eigen=np.linalg.eigvalsh(cov)
    if not np.isfinite(eigen).all():return dict(reason='NONFINITE_MARGINAL',q=None,trace=None,area95=None,eigenvalues=None)
    if eigen[0]<=max(0.,eigen[-1]*c['coverage']['marginal_relative_eigenvalue_floor']):return dict(reason='SINGULAR_MARGINAL',q=None,trace=float(np.trace(cov)),area95=None,eigenvalues=eigen.tolist())
    return dict(reason='AVAILABLE',q=float(error@np.linalg.solve(cov,error)),trace=float(np.trace(cov)),area95=float(np.pi*chi2.ppf(.95,len(error))*np.sqrt(np.linalg.det(cov))) if len(error)==2 else None,eigenvalues=eigen.tolist())

def gaussian_ellipse_probability(mu,noise,candidate,level):
    """Deterministic 1D quadrature of exact 2D Gaussian over candidate ellipse; singular noise allowed."""
    v,w=np.linalg.eigh(candidate)
    if v[0]<=0:return None
    transform=(w/np.sqrt(v)).T;nn=transform@noise@transform.T;lam,rot=np.linalg.eigh(nn);mm=rot.T@transform@mu;lam=np.maximum(lam,0);rad=np.sqrt(chi2.ppf(level,2))
    if np.max(abs(lam-1))<1e-9:return float(ncx2.cdf(rad*rad,2,float(mm@mm)))
    # Integrate dimension with larger variance; handle a deterministic second coordinate.
    sd=np.sqrt(lam[::-1]);mm=mm[::-1]
    if sd[0]<1e-12:return float(mm@mm<=rad*rad)
    def inner(x):
        h=np.sqrt(max(0.,rad*rad-x*x))
        return float(abs(mm[1])<=h) if sd[1]<1e-12 else norm.cdf((h-mm[1])/sd[1])-norm.cdf((-h-mm[1])/sd[1])
    return float(quad(lambda x:norm.pdf((x-mm[0])/sd[0])/sd[0]*inner(x),-rad,rad,epsabs=1e-8,limit=150)[0])
