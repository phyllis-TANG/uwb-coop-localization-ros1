"""Eight variables per joint frame; exact read-only single-car F3 factor reuse."""
import copy
from dataclasses import dataclass
from types import SimpleNamespace
import time
import numpy as np
from scipy.linalg import qr
from scipy.optimize import least_squares
from pinned import f0, single, two_legacy

CARS = ('car1', 'car2')


def car_config(config, car):
    return dict(arm='F3', model=config['models'][car], angular=config['angular'][car],
                replay=config['replay'], optimizer=config['optimizer'], fixed_lag_s=20.)


@dataclass
class Prior:
    point: np.ndarray
    matrix: np.ndarray
    offset: np.ndarray

    def __post_init__(self):
        self.point=np.array(self.point,float,copy=True)
        self.matrix=np.array(self.matrix,float,copy=True).reshape(-1,8)
        self.offset=np.array(self.offset,float,copy=True)
        if self.point.shape!=(8,) or self.offset.shape!=(len(self.matrix),): raise ValueError('8D prior shape')
        if not all(np.isfinite(v).all() for v in (self.point,self.matrix,self.offset)): raise ValueError('nonfinite prior')

    def residual(self,x):
        d=np.asarray(x)-self.point
        d[[2,6]]=np.arctan2(np.sin(d[[2,6]]),np.cos(d[[2,6]]))
        return self.matrix@d+self.offset

    def record(self):
        return dict(point=self.point.tolist(),matrix=self.matrix.tolist(),offset=self.offset.tolist())


def initial(config):
    ps=[single.initial_prior(config['models'][c],car_config(config,c)) for c in CARS]
    matrix=np.zeros((8,8))
    for i,p in enumerate(ps): matrix[4*i:4*i+4,4*i:4*i+4]=p.matrix
    return Prior(np.concatenate([p.point for p in ps]),matrix,np.zeros(8))


class Objective:
    def __init__(self,times,local,observations,peers,intervals,config,prior,peer_enabled):
        self.n=len(times); self.prior=prior; self.config=config
        self.parts=[]
        local=np.asarray(local)
        if local.shape!=(self.n,2,3) or len(intervals)!=self.n-1: raise ValueError('joint interval/local shape')
        for i,c in enumerate(CARS):
            zero=single.Prior(np.zeros(4),np.zeros((0,4)),np.zeros(0))
            self.parts.append(single.Objective(times,local[:,i],[o[c] for o in observations],
                [a[c] for a in intervals],config['models'][c],zero,car_config(config,c)))
        self.peers=[(i,p) for i,p in enumerate(peers) if peer_enabled and p is not None]
        self._x=None

    def evaluate(self,flat):
        flat=np.asarray(flat)
        if self._x is not None and np.array_equal(flat,self._x): return self._r,self._j
        states=flat.reshape(self.n,8); r=[self.prior.residual(states[0])]
        p=np.zeros((len(r[0]),8*self.n)); p[:,:8]=self.prior.matrix; js=[p]
        for i,part in enumerate(self.parts):
            cols=(8*np.arange(self.n)[:,None]+np.arange(4*i,4*i+4)).ravel()
            rr,jj=part.evaluate(flat[cols]); expanded=np.zeros((len(rr),8*self.n)); expanded[:,cols]=jj
            r.append(rr); js.append(expanded)
        for k,measured in self.peers:
            pose=states[k,[0,1,2,4,5,6]]
            rr,jj=f0.peer_residual(pose,measured,self.config['models'],self.config['peer']['sigma_m'])
            expanded=np.zeros((1,8*self.n)); expanded[0,8*k+np.array([0,1,2,4,5,6])]=jj
            r.append(np.array([rr])); js.append(expanded)
        self._x=flat.copy();self._r=np.concatenate(r);self._j=np.vstack(js)
        return self._r,self._j

    def fun(self,x): return self.evaluate(x)[0].copy()
    def jac(self,x): return self.evaluate(x)[1].copy()


def solve_independent(objective, states, config):
    """M2 uses each frozen F3 stopping rule, avoiding pooled-ftol coupling.

    The maintained prior remains the full 8-column object. With no cross-car
    factors it is block diagonal; refuse any substantive cross information.
    """
    prior=objective.prior;matrix=prior.matrix
    if matrix.shape!=(8,8) or np.linalg.norm(matrix[:4,4:])+np.linalg.norm(matrix[4:,:4])>1e-10:
        raise ValueError('Independent objective unexpectedly has cross-car prior')
    results=[];out=np.asarray(states).copy()
    for i,car in enumerate(CARS):
        part=objective.parts[i]
        zero_prior=part.prior
        part.prior=single.Prior(prior.point[4*i:4*i+4],matrix[4*i:4*i+4,4*i:4*i+4],prior.offset[4*i:4*i+4])
        part._x=None
        r=least_squares(part.fun,out[:,4*i:4*i+4].ravel(),jac=part.jac,method='trf',tr_solver='exact',loss='linear',
            max_nfev=config['optimizer']['max_nfev'],ftol=1e-7,xtol=1e-7,gtol=1e-7)
        out[:,4*i:4*i+4]=r.x.reshape(-1,4);results.append(r)
        part.prior=zero_prior;part._x=None
    # The final cost/Jacobian always use the full maintained joint objective.
    r,J=objective.evaluate(out.ravel())
    return SimpleNamespace(x=out.ravel(),jac=J,cost=float(r@r/2),success=all(r.success for r in results),
        status=min(r.status for r in results),nfev=sum(r.nfev for r in results),
        optimality=max(r.optimality for r in results),message='independent per-car F3 stopping; '+str([str(r.message) for r in results]))


def eliminate(states,times,local,observations,peers,intervals,config,prior,peer_enabled):
    obs=[observations[0],{c:{} for c in CARS}]
    obj=Objective(times[:2],local[:2],obs,[peers[0],None],intervals[:1],config,prior,peer_enabled)
    r,j=obj.evaluate(np.asarray(states[:2]).ravel()); old,boundary=j[:,:8],j[:,8:]
    q,R,_=qr(old,mode='full',pivoting=True)
    tol=max(old.shape)*np.finfo(float).eps*np.linalg.norm(old,ord=2)
    rank=int(np.sum(np.abs(np.diag(R))>tol))
    projected=q[:,rank:].T@boundary; residual=q[:,rank:].T@r
    q2,matrix=np.linalg.qr(projected,mode='reduced'); offset=q2.T@residual
    if len(matrix):
        sign=np.where(np.diag(matrix)<0,-1.,1.);matrix=sign[:,None]*matrix;offset=sign*offset
    constant=max(0.,float(residual@residual-offset@offset))
    basis_canonicalized=False
    # A rank-deficient QR may rotate residual rows between otherwise independent
    # cars. For M2 only, recover the exact two-F3 block representation of the
    # SAME incident objective. M3 always retains the full joint QR untouched.
    incoming_block = prior.matrix.shape==(8,8) and np.linalg.norm(prior.matrix[:4,4:])+np.linalg.norm(prior.matrix[4:,:4])<=1e-10
    if not peer_enabled and incoming_block and matrix.shape==(8,8) and np.linalg.norm(matrix[:4,4:])+np.linalg.norm(matrix[4:,:4])>1e-10:
        block=np.zeros((8,8));off=np.zeros(8);constants=0.
        for i,car in enumerate(CARS):
            sl=slice(4*i,4*i+4);cfg=car_config(config,car)
            before=single.Prior(prior.point[sl],prior.matrix[sl,sl],prior.offset[sl])
            part,c,_=single.eliminate_oldest(np.asarray(states[:2])[:,sl],times[:2],np.asarray(local[:2])[:,i],
                [observations[0][car],{}],[intervals[0][car]],config['models'][car],before,cfg)
            block[sl,sl]=part.matrix;off[sl]=part.offset;constants+=c
        matrix,offset,constant=block,off,constants;basis_canonicalized=True
    after=Prior(states[1],matrix,offset)
    detail=dict(times_s=list(times[:2]),states=np.asarray(states[:2]).tolist(),local=np.asarray(local[:2]).tolist(),
        old_observations=copy.deepcopy(observations[0]),old_peer_m=peers[0],intervals=copy.deepcopy(intervals[:1]),
        before=prior.record(),after=after.record(),constant=constant,old_dimension=8,rank_old=rank,
        rank_boundary=int(np.linalg.matrix_rank(matrix)) if matrix.size else 0,
        independent_basis_canonicalized=basis_canonicalized,
        cross_information_norm=float(np.linalg.norm((matrix.T@matrix)[:4,4:])),
        incident_policy='prior+old_walls+old_peer+first_translations+first_gyro_bias; retained factors excluded')
    return after,constant,detail


class WindowGraph:
    def __init__(self,config,peer_enabled):
        self.config=copy.deepcopy(config);self.peer_enabled=peer_enabled;self.prior=initial(config)
        self.times=[];self.local=[];self.observations=[];self.peers=[];self.intervals=[];self.states=[]
        self.next_intervals=None;self.marginalizations=0;self.eliminated_constant=0.
        self.peak_solve_states=0;self.peak_transient_states=0;self.missing_edges={c:0 for c in CARS}

    def update(self,stamp,local,observations,peer):
        local=np.asarray(local,float)
        if local.shape!=(2,3) or not np.isfinite(local).all():raise ValueError('joint local')
        edge=self.next_intervals
        if self.times and (edge is None or stamp-self.times[-1]<1-1e-9): raise ValueError('interval/spacing')
        if self.states:
            guess=np.concatenate([single.predict(self.states[-1][4*i:4*i+4],self.local[-1][i],local[i],edge[c]) for i,c in enumerate(CARS)])
            sources={c:'integrated_gyro_minus_bias' if edge[c]['valid'] else 'held_yaw_missing_gyro' for c in CARS}
        else:
            guess=self.prior.point.copy();sources={c:'declared_external_initial_heading' for c in CARS}
        old=copy.deepcopy((self.times,self.local,self.observations,self.peers,self.intervals,self.states,
                            self.prior,self.marginalizations,self.eliminated_constant,self.missing_edges))
        if self.times:
            self.intervals.append(copy.deepcopy(edge))
            for c in CARS:self.missing_edges[c]+=int(not edge[c]['valid'])
        self.times.append(float(stamp));self.local.append(local.copy());self.observations.append(copy.deepcopy(observations))
        self.peers.append(peer if self.peer_enabled else None);self.states.append(guess.copy())
        self.peak_transient_states=max(self.peak_transient_states,len(self.times));details=[];started=time.perf_counter()
        error=None
        try:
            while self.times[-1]-self.times[0]>20+1e-12:
                self.prior,constant,detail=eliminate(self.states,self.times,self.local,self.observations,self.peers,
                    self.intervals,self.config,self.prior,self.peer_enabled)
                details.append(detail);self.eliminated_constant+=constant;self.marginalizations+=1
                for seq in (self.times,self.local,self.observations,self.peers,self.states,self.intervals):del seq[0]
        except (ValueError,FloatingPointError,np.linalg.LinAlgError) as exc:
            (self.times,self.local,self.observations,self.peers,self.intervals,self.states,self.prior,
             self.marginalizations,self.eliminated_constant,self.missing_edges)=old
            error=str(exc);details=[]
        marginal=time.perf_counter()-started;n=len(self.times);accepted=False;rank=None;candidate=None;info={}
        warmstart=np.asarray(self.states).tolist()
        status='predict_only_marginal_error' if error else 'predict_only_warmup'
        if error:info={'error':error}
        self.peak_solve_states=max(self.peak_solve_states,n);started=time.perf_counter()
        if not error and n>=3:
            try:
                obj=Objective(self.times,self.local,self.observations,self.peers,self.intervals,self.config,self.prior,self.peer_enabled)
                if self.peer_enabled:
                    result=least_squares(obj.fun,np.asarray(self.states).ravel(),jac=obj.jac,method='trf',tr_solver='exact',loss='linear',
                        max_nfev=self.config['optimizer']['max_nfev'],ftol=1e-7,xtol=1e-7,gtol=1e-7)
                else:
                    result=solve_independent(obj,self.states,self.config)
                if np.isfinite(result.x).all():candidate=result.x.reshape(n,8).tolist()
                rank=int(np.linalg.matrix_rank(result.jac));accepted=bool(result.success and candidate is not None)
                info=dict(success=bool(result.success),status=int(result.status),nfev=int(result.nfev),cost=float(result.cost),
                          optimality=float(result.optimality),message=str(result.message))
                if accepted:self.states=[p.copy() for p in result.x.reshape(n,8)];status='graph'
                else:status='predict_only_solver_failed'
            except (ValueError,FloatingPointError,np.linalg.LinAlgError) as exc:
                status='predict_only_solver_error';info={'error':str(exc)}
        valid={c:bool(edge is None or edge[c]['valid']) for c in CARS}
        full_rank=rank is not None and rank==n*8
        if not all(valid.values()):status+='_missing_angular'
        if accepted and not full_rank:status+='_rank_deficient'
        return dict(pose=guess.tolist() if error else self.states[-1].tolist(),prediction_pose=guess.tolist(),candidate_states=candidate,
            accepted_graph=accepted,status=status,optimizer=info,graph_states=n,graph_time_span_s=self.times[-1]-self.times[0] if n else 0.,
            marginalizations=self.marginalizations,marginal_wall_s=marginal,solve_wall_s=time.perf_counter()-started,
            marginalization_details=details,prior=self.prior.record(),numerical_rank=rank,numerical_full_rank=full_rank,
            angular_valid=valid,estimate_valid={c:bool(accepted and valid[c] and full_rank) for c in CARS},
            prediction_yaw_source=sources,odom_yaw_fallback=False,missing_angular_edges_cumulative=copy.deepcopy(self.missing_edges),
            optimizer_warmstart_states=warmstart)

    def snapshot(self):
        return copy.deepcopy(dict(times_s=self.times,local=np.asarray(self.local).tolist(),observations=self.observations,
            peers_m=self.peers,intervals=self.intervals,states=np.asarray(self.states).tolist(),prior=self.prior.record(),
            eliminated_constant=self.eliminated_constant,peer_enabled=self.peer_enabled))
