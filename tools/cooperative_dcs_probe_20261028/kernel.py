"""Scalar peer DCS: exact nominal geometry, IRLS curvature, true robust cost.

The SciPy loss third row is deliberately a zero GN-curvature encoding, NOT
rho''. This yields s*J and s*e locally while TRF acceptance evaluates rho.
No production module globals are modified. Only this graph's function bindings
replace the peer objective / solver loss / incident linearization.
"""
import copy,json,math,types
import numpy as np
from bindings import base,legacy
from common import HERE
PHI=json.loads((HERE/'dcs_config.json').read_text())['phi']
if PHI!=1.0:raise ValueError('Only preregistered Phi=1 allowed')


def kernel_values(t,phi=PHI):
    t=np.asarray(t,float)
    if phi<=0 or not math.isfinite(phi) or np.any(t<0) or not np.isfinite(t).all():raise ValueError('DCS nominal chi-square/Phi')
    s=np.minimum(1.,2.*phi/(phi+t));w=s*s
    rho=np.where(t<=phi,t,3*phi-4*phi*phi/(phi+t))
    return s,w,rho


def nominal_peer(state,measured,models,sigma):
    if not np.isfinite(measured) or measured<=0 or sigma<=0:raise ValueError('peer observation/scale')
    positions=[];derivatives=[]
    for i,car in enumerate(legacy.CARS):
        m=models[car];p=state[3*i:3*i+3];lx,ly=m['base_to_antenna_body_xy_m'];co,si=np.cos(p[2]),np.sin(p[2])
        positions.append(np.r_[legacy.antenna(p,[lx,ly]),m['antenna_height_m']]);derivatives.append(np.array([-si*lx-co*ly,co*lx-si*ly]))
    delta=positions[0]-positions[1];distance=np.linalg.norm(delta)
    if distance<=1e-12:raise ValueError('degenerate peer distance')
    unit=delta[:2]/distance
    return (distance-measured)/sigma,np.r_[unit,unit@derivatives[0],-unit,-unit@derivatives[1]]/sigma


class PeerObjective:
    def __init__(self,times,local,observations,peers,config,prior,peer_enabled=True,dcs=True,linearizations=None,trials=None):
        self.base=base.Objective(times,local,observations,peers,config,prior,False)
        self.times=list(times);self.n=len(times);self.config=config;self.dcs=dcs
        self.peers=[(i,p) for i,p in enumerate(peers) if peer_enabled and p is not None]
        self.linearizations=linearizations;self.trials=trials;self._x=None
    def evaluate(self,flat):
        flat=np.asarray(flat)
        if self._x is not None and np.array_equal(flat,self._x):return self._r,self._j
        r,j=self.base.evaluate(flat);rs=[r];js=[j];x=flat.reshape(self.n,6)
        for k,z in self.peers:
            e,J=nominal_peer(x[k],z,self.config['models'],self.config['peer']['sigma_m']);expanded=np.zeros((1,6*self.n));expanded[0,6*k:6*k+6]=J
            rs.append(np.array([e]));js.append(expanded)
        self._x=flat.copy();self._r=np.concatenate(rs);self._j=np.vstack(js);return self._r,self._j
    def loss(self,z):
        rho=np.vstack((np.asarray(z).copy(),np.ones(len(z)),np.zeros(len(z))))
        if self.dcs and self.peers:
            n=len(self.peers);s,w,cost=kernel_values(z[-n:])
            # scipy internally floors curvature to EPS. Refuse unsupported
            # extreme information rather than silently claiming exact s².
            if np.any(w<np.finfo(float).eps):raise FloatingPointError('DCS weight below SciPy curvature floor; not silently clipped')
            rho[0,-n:]=cost;rho[1,-n:]=w
        return rho
    def peer_records(self,x):
        r,_=self.evaluate(x);n=len(self.peers);out=[]
        for (k,z),e in zip(self.peers,r[-n:] if n else []):
            s,w,rho=kernel_values(e*e) if self.dcs else (1.,1.,e*e)
            out.append(dict(state_time_s=self.times[k],measurement_m=z,nominal_residual_m=float(e*self.config['peer']['sigma_m']),
                nominal_e=float(e),chi_square=float(e*e),s=float(s),information_weight=float(w),influence=float(w*e),
                scaled_residual=float(s*e),rho=float(rho)))
        return out
    def cost(self,x):
        r,_=self.evaluate(x);return float(np.sum(self.loss(r*r)[0])/2)
    def fun(self,x):
        r,_=self.evaluate(x)
        if self.trials is not None:self.trials.append(dict(states=np.asarray(x).reshape(self.n,6).tolist(),true_cost=self.cost(x)))
        return r.copy()
    def jac(self,x):
        r,J=self.evaluate(x)
        if self.linearizations is not None:
            weights=self.loss(r*r)[1]
            self.linearizations.append(dict(iteration=len(self.linearizations),states=np.asarray(x).reshape(self.n,6).tolist(),true_cost=self.cost(x),
                peers=self.peer_records(x),gradient_inf_norm=float(np.linalg.norm(J.T@(weights*r),ord=np.inf)),
                curvature='Jt diag(w) J; peer w=s² frozen at this accepted linearization; no ds/de'))
        return J.copy()
    def weighted(self,x):
        r,J=self.evaluate(x);weights=self.loss(r*r)[1];s=np.sqrt(weights)
        correction=float(np.sum(self.loss(r*r)[0]-weights*r*r))
        return s*r,s[:,None]*J,correction


class WindowGraph(base.WindowGraph):
    def __init__(self,config,peer_enabled=True,dcs=True):
        super().__init__(config,peer_enabled);self.dcs=dcs;self.trace=[];self.trials=[];self.last_candidate=None
        def factory(*args):
            if not args[-1]:return base.Objective(*args)
            return PeerObjective(*args,dcs=self.dcs,linearizations=self.trace,trials=self.trials)
        def solver(fun,x0,**kwargs):
            obj=fun.__self__
            if isinstance(obj,PeerObjective) and self.dcs:kwargs['loss']=obj.loss
            result=base.least_squares(fun,x0,**kwargs);self.last_candidate=result.x.reshape(-1,6).tolist();return result
        scope={**base.__dict__,'Objective':factory,'least_squares':solver,'eliminate_oldest':self._eliminate}
        self._native_update=types.FunctionType(base.WindowGraph.update.__code__,scope,'dcs_bound_original_update')
    def _eliminate(self,states,times,local,observations,peers,config,prior,peer_enabled):
        if not peer_enabled:return base.eliminate_oldest(states,times,local,observations,peers,config,prior,False)
        obj=PeerObjective(times[:2],local[:2],[observations[0],{c:{} for c in legacy.CARS}], [peers[0],None],config,prior,True,self.dcs)
        x=np.asarray(states[:2]).ravel();r,J,correction=obj.weighted(x)
        def incident(*args):return r,J
        fn=types.FunctionType(base.eliminate_oldest.__code__,{**base.__dict__,'incident_system':incident},'dcs_incident_original_elimination')
        after,constant,details=fn(states,times,local,observations,peers,config,prior,peer_enabled)
        details.update(projected_quadratic_constant=constant,dcs_offset_constant=correction,dcs_consumed_peer=obj.peer_records(x),constant=constant+correction,
            dcs_policy='weight frozen at elimination; full joint prior not reweighted/cleared later',phi=PHI)
        return after,constant+correction,details
    def update(self,*args):
        self.trace=[];self.trials=[];self.last_candidate=None
        row=self._native_update(self,*args)
        row.update(dcs_linearizations=copy.deepcopy(self.trace),dcs_trials=copy.deepcopy(self.trials),candidate_states=self.last_candidate,
                   dcs_phi=PHI,dcs_weight_policy='all active peers reweighted per accepted linearization; marginalized prior frozen')
        if self.times:
            obj=PeerObjective(self.times,self.local,self.observations,self.peers,self.config,self.prior,self.peer_enabled,self.dcs)
            row['dcs_final_peers']=obj.peer_records(np.asarray(self.states).ravel())
        else:row['dcs_final_peers']=[]
        return row
