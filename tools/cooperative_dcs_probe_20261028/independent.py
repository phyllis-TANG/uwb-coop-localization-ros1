"""Independent scalar DCS readback; imports only frozen scalar audit, no solver."""
import importlib.util,json,math
import numpy as np
from common import ROOT,HERE,sha
lock=json.loads((HERE/'source_lock.json').read_text())['files'];path=ROOT/'tools/two_car_fixed_lag_fgo_v1/audit.py'
if sha(path)!=lock[str(path.relative_to(ROOT))]:raise ValueError('audit source')
spec=importlib.util.spec_from_file_location('independent_f0_equations',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def weights(e):
    t=np.square(e);w=np.where(t<=1.,1.,4./np.square(1.+t));rho=np.where(t<=1.,t,3.-4./(1.+t))
    return w,rho


def nominal(snapshot,flat,config):
    r=audit.residuals(flat,snapshot['times_s'],snapshot['local'],snapshot['observations'],snapshot['peers_m'],config['models'],snapshot['prior'],False)
    x=np.asarray(flat).reshape(-1,6);ps=[]
    if snapshot['peer_enabled']:
        for k,z in enumerate(snapshot['peers_m']):
            if z is not None:ps.append((np.linalg.norm(audit.ant(x[k,:3],config['models']['car1'])-audit.ant(x[k,3:],config['models']['car2']))-z)/config['peer']['sigma_m'])
    return np.r_[r,ps],len(ps)


def cost(snapshot,flat,config):
    r,n=nominal(snapshot,flat,config)
    return float((r[:-n]@r[:-n]+sum(weights(r[-n:])[1]))/2) if n else float(r@r/2)


def marginal(detail,config):
    snap=dict(times_s=detail['times_s'],local=detail['local'],observations=[detail['old_observations'],{'car1':{},'car2':{}}],
        peers_m=[detail['old_peer_m'],None],prior=detail['before'],peer_enabled=True)
    x=np.asarray(detail['states']).ravel();raw,n=nominal(snap,x,config);ww=np.ones(len(raw));offset=0.
    if n:
        ww[-n:],rho=weights(raw[-n:]);offset=float(sum(rho-ww[-n:]*raw[-n:]**2))
    # FD of nominal residual, THEN fixed local scale: deliberately no ds/de.
    J=audit.finite_jac(lambda v:nominal(snap,v,config)[0],x);r=raw*np.sqrt(ww);J=np.sqrt(ww)[:,None]*J
    a,b=J[:,:6],J[:,6:];jp=b-a@np.linalg.lstsq(a,b,rcond=None)[0];rp=r-a@np.linalg.lstsq(a,r,rcond=None)[0]
    M=np.array(detail['after']['matrix']);o=np.array(detail['after']['offset']);H=M.T@M;g=M.T@o
    np.testing.assert_allclose(H,jp.T@jp,atol=1e-5,rtol=1e-8);np.testing.assert_allclose(g,jp.T@rp,atol=1e-6,rtol=1e-8)
    err=abs(o@o+detail['constant']-(rp@rp+offset));assert err<1e-6
    assert abs(detail['dcs_offset_constant']-offset)<1e-10
    return dict(h_abs=float(np.max(abs(H-jp.T@jp))),g_abs=float(np.max(abs(g-jp.T@rp))),constant_abs=float(err),cross=float(np.linalg.norm(H[:3,3:])))
