"""Artifact equations only; no online graph/Jacobian/optimizer imports."""
import importlib.util,json
import numpy as np
from common import ROOT,HERE,sha
path=ROOT/'tools/two_car_fixed_lag_fgo_v1/audit.py';lock=json.loads((HERE/'source_lock.json').read_text())['files'];assert sha(path)==lock[str(path.relative_to(ROOT))]
spec=importlib.util.spec_from_file_location('f0_scalar_audit',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
def residuals(flat,snapshot,config,weight):
 r=audit.residuals(flat,snapshot['times_s'],snapshot['local'],snapshot['observations'],snapshot['peers_m'],config['models'],snapshot['prior'],False)
 x=np.asarray(flat).reshape(-1,6);peer=[]
 if snapshot['peer_enabled']:
  for state,z in zip(x,snapshot['peers_m']):
   if z is None:continue
   d=np.linalg.norm(audit.ant(state[:3],config['models']['car1'])-audit.ant(state[3:],config['models']['car2']))
   peer.append(np.sqrt(weight)*audit.range_residual(d,z,config['peer']['sigma_m']))
 return np.r_[r,peer]
def antenna_xy(pose,config):return np.array([audit.ant(pose[3*i:3*i+3],config['models'][c])[:2] for i,c in enumerate(audit.CARS)])
def marginal(d,config,weight,enabled=True):
 s=dict(times_s=d['times_s'],local=d['local'],observations=[d['old_observations'],{'car1':{},'car2':{}}],peers_m=[d['old_peer_m'],None],prior=d['before'],peer_enabled=enabled)
 x=np.asarray(d['states']).ravel();f=lambda v:residuals(v,s,config,weight);r=f(x);J=audit.finite_jac(f,x);a,b=J[:,:6],J[:,6:]
 jp=b-a@np.linalg.lstsq(a,b,rcond=None)[0];rp=r-a@np.linalg.lstsq(a,r,rcond=None)[0];M=np.array(d['after']['matrix']);o=np.array(d['after']['offset'])
 np.testing.assert_allclose(M.T@M,jp.T@jp,atol=3e-6,rtol=2e-6);np.testing.assert_allclose(M.T@o,jp.T@rp,atol=2e-6,rtol=2e-6)
 np.testing.assert_allclose(o@o+d['constant'],rp@rp,atol=2e-6,rtol=2e-6)
 return dict(H_max_abs=float(np.max(abs(M.T@M-jp.T@jp))),g_max_abs=float(np.max(abs(M.T@o-jp.T@rp))),constant_abs=float(abs(o@o+d['constant']-rp@rp)))
