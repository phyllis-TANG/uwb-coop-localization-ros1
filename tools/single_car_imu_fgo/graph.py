"""Existing pose factors extended with gyro increments and residual bias.

Only the angular rows change; translation/UWB residuals and analytic derivatives
are read-only reuse of the frozen pose objective. No hard-coded 6D EKF policy.
"""
from dataclasses import dataclass
import copy
import math
import time
import numpy as np
from scipy.linalg import qr
from scipy.optimize import least_squares
from legacy import PoseObjective,pose_prior,rotation,wrap
from integration import angular_covariance


@dataclass
class Prior:
    point:np.ndarray
    matrix:np.ndarray
    offset:np.ndarray
    def __post_init__(self):
        self.point=np.array(self.point,dtype=float,copy=True); self.matrix=np.array(self.matrix,dtype=float,copy=True); self.offset=np.array(self.offset,dtype=float,copy=True)
        d=len(self.point)
        if d not in (3,4) or self.matrix.ndim!=2 or self.matrix.shape[1]!=d or self.offset.shape!=(len(self.matrix),): raise ValueError('prior dimensions')
        if not all(np.isfinite(v).all() for v in [self.point,self.matrix,self.offset]): raise ValueError('nonfinite prior')
    def residual(self,x):
        delta=np.asarray(x)-self.point; delta[2]=wrap(delta[2]); return self.matrix@delta+self.offset


def initial_prior(model,config):
    p=pose_prior(model)
    if config['arm']!='F3': return Prior(p.point,p.matrix,p.offset)
    point=np.r_[p.point,config['angular']['bias_initial_rad_s']['value']]; matrix=np.zeros((4,4)); matrix[:3,:3]=p.matrix; matrix[3,3]=1/config['angular']['bias_initial_sigma_rad_s']['value']
    return Prior(point,matrix,np.zeros(4))


class Objective:
    def __init__(self,times,local,observations,intervals,model,prior,config):
        self.n=len(times); self.d=4 if config['arm']=='F3' else 3; self.prior=prior; self.intervals=copy.deepcopy(intervals)
        if len(intervals)!=self.n-1: raise ValueError('interval count')
        self.dt=np.diff(times); self.sigma=config['angular']['angle_noise_density_rad_sqrt_s']['value']; self.bias_sigma=config['angular']['bias_random_walk_rad_s_sqrt_s']['value']
        for dt,interval in zip(self.dt,self.intervals):
            if interval['dt_ns']!=interval['end_epoch_ns']-interval['start_epoch_ns'] or abs(interval['dt_ns']/1e9-dt)>1e-9: raise ValueError('angular interval does not match keyframe dt')
            if interval['valid'] and (interval.get('gaps') or not math.isfinite(interval['raw_angle_rad'])): raise ValueError('invalid complete angular factor')
        self.pose=PoseObjective(times,local,observations,model,pose_prior(model))
        self._x=None
    def evaluate(self,flat):
        flat=np.asarray(flat)
        if self._x is not None and np.array_equal(flat,self._x): return self._r,self._j
        states=flat.reshape(self.n,self.d); base_r,base_j=self.pose.evaluate(states[:,:3].ravel())
        # Keep only original translation and UWB rows; never keep original yaw.
        keep=[r for i in range(self.n-1) for r in (3+3*i,4+3*i)] + list(range(3*self.n,len(base_r)))
        blocks=[self.prior.residual(states[0])]; prior_j=np.zeros((len(self.prior.offset),self.n*self.d)); prior_j[:,:self.d]=self.prior.matrix; matrices=[prior_j]
        core_j=np.zeros((len(keep),self.n*self.d))
        for i in range(self.n): core_j[:,i*self.d:i*self.d+3]=base_j[np.ix_(keep,range(3*i,3*i+3))]
        blocks.append(base_r[keep]); matrices.append(core_j)
        for i,(dt,interval) in enumerate(zip(self.dt,self.intervals)):
            left,right=i*self.d,(i+1)*self.d
            if interval['valid']:
                angular=wrap(states[i+1,2]-states[i,2]-interval['raw_angle_rad']+(states[i,3]*dt if self.d==4 else 0.))
                if self.d==4:
                    e=np.array([angular,states[i+1,3]-states[i,3]])
                    J=np.zeros((2,self.n*self.d)); J[0,left+2]=-1.; J[0,right+2]=1.; J[0,left+3]=dt; J[1,left+3]=-1.; J[1,right+3]=1.
                    L=np.linalg.cholesky(angular_covariance(dt,self.sigma,self.bias_sigma)); blocks.append(np.linalg.solve(L,e)); matrices.append(np.linalg.solve(L,J))
                else:
                    scale=self.sigma*math.sqrt(dt); J=np.zeros((1,self.n*self.d)); J[0,left+2]=-1/scale; J[0,right+2]=1/scale
                    blocks.append(np.array([angular/scale])); matrices.append(J)
            elif self.d==4:
                scale=self.bias_sigma*math.sqrt(dt); J=np.zeros((1,self.n*self.d)); J[0,left+3]=-1/scale; J[0,right+3]=1/scale
                blocks.append(np.array([(states[i+1,3]-states[i,3])/scale])); matrices.append(J)
        self._x=flat.copy(); self._r=np.concatenate(blocks); self._j=np.vstack(matrices); return self._r,self._j
    def fun(self,x): return self.evaluate(x)[0].copy()
    def jac(self,x): return self.evaluate(x)[1].copy()


def eliminate_oldest(states,times,local,observations,intervals,model,prior,config):
    d=len(prior.point); objective=Objective(times[:2],local[:2],[observations[0],{}],intervals[:1],model,prior,config)
    r,J=objective.evaluate(np.asarray(states[:2]).ravel()); old,boundary=J[:,:d],J[:,d:2*d]
    # Pivoting identifies the full old column space even if a yaw direction is free.
    Q,R,_=qr(old,mode='full',pivoting=True); scale=np.linalg.norm(old,ord=2); tol=max(old.shape)*np.finfo(float).eps*scale
    rank=int(np.sum(np.abs(np.diag(R))>tol)); projected=Q[:,rank:].T@boundary; residual=Q[:,rank:].T@r
    Q2,M=np.linalg.qr(projected,mode='reduced'); offset=Q2.T@residual
    if len(M):
        sign=np.where(np.diag(M)<0,-1.,1.); M=sign[:,None]*M; offset=sign*offset
    constant=max(0.,float(residual@residual-offset@offset)); carried=Prior(states[1],M,offset)
    info=dict(old_dimension=d,old_rank=rank,boundary_rank=int(np.linalg.matrix_rank(M)) if M.size else 0,prior_rows=len(M),
        rank_deficient=bool(rank<d or (np.linalg.matrix_rank(M) if M.size else 0)<d),incident_factor_policy='carried_prior+old_UWB+first_translation+first_angular/bias_only',
        includes_retained_UWB=False,retains_affine_offset=True,eliminated_constant=constant,
        linearization_input=dict(states=np.asarray(states[:2]).tolist(),times_s=list(times[:2]),local_odom=np.asarray(local[:2]).tolist(),observations=[dict(observations[0]),{}],intervals=copy.deepcopy(intervals[:1]),
                                 prior=dict(point=prior.point.tolist(),matrix=prior.matrix.tolist(),offset=prior.offset.tolist())),
        prior_after=dict(point=carried.point.tolist(),matrix=carried.matrix.tolist(),offset=carried.offset.tolist()))
    return carried,constant,info


def predict(previous,previous_local,local,interval):
    body=rotation(-previous_local[2])@(np.asarray(local[:2])-previous_local[:2]); guess=np.array(previous,copy=True)
    guess[:2]+=rotation(previous[2])@body
    if interval['valid']: guess[2]=wrap(previous[2]+interval['raw_angle_rad']-(previous[3] if len(previous)==4 else 0.)*((interval['end_epoch_ns']-interval['start_epoch_ns'])/1e9))
    return guess


class WindowGraph:
    def __init__(self,config,lag_s=20.,max_nfev=None):
        self.config=copy.deepcopy(config); self.model=config['model']; self.d=4 if config['arm']=='F3' else 3
        self.minimum_step=config['replay']['keyframe_step_s']; self.lag_s=lag_s; self.max_nfev=config['optimizer']['max_nfev'] if max_nfev is None else max_nfev
        self.prior=initial_prior(self.model,config); self.times=[]; self.local=[]; self.observations=[]; self.intervals=[]; self.states=[]
        self.marginalizations=0; self.eliminated_constant=0.; self.peak_solve_states=0; self.peak_transient_states=0; self.total_keyframes=0; self.missing_angular_edges=0
    def update(self,stamp,local,observations,interval=None):
        local=np.asarray(local,dtype=float).copy()
        if local.shape!=(3,) or not np.isfinite(local).all(): raise ValueError('invalid local pose')
        if self.times and stamp-self.times[-1]<self.minimum_step-1e-9: raise ValueError('keyframe spacing')
        if self.states:
            if interval is None: raise ValueError('missing angular interval object')
            guess=predict(self.states[-1],self.local[-1],local,interval); self.intervals.append(copy.deepcopy(interval)); self.missing_angular_edges+=int(not interval['valid'])
        else: guess=self.prior.point.copy()
        prediction=guess.copy(); self.times.append(float(stamp)); self.local.append(local); self.observations.append(dict(observations)); self.states.append(guess); self.total_keyframes+=1
        self.peak_transient_states=max(self.peak_transient_states,len(self.times)); margins=[]; start=time.perf_counter()
        while self.lag_s is not None and self.times[-1]-self.times[0]>self.lag_s+1e-12:
            self.prior,c,info=eliminate_oldest(self.states,self.times,self.local,self.observations,self.intervals,self.model,self.prior,self.config)
            self.eliminated_constant+=c; self.marginalizations+=1; margins.append(info)
            for seq in (self.times,self.local,self.observations,self.states): del seq[0]
            del self.intervals[0]
        marginal_wall=time.perf_counter()-start; n=len(self.times); self.peak_solve_states=max(self.peak_solve_states,n)
        accepted=False; status='predict_only_warmup'; info={}; candidate=None; candidate_states=None; rank=None; start=time.perf_counter()
        if n>=3:
            try:
                objective=Objective(self.times,self.local,self.observations,self.intervals,self.model,self.prior,self.config)
                result=least_squares(objective.fun,np.asarray(self.states).ravel(),jac=objective.jac,method='trf',tr_solver='exact',loss='linear',max_nfev=self.max_nfev,ftol=1e-7,xtol=1e-7,gtol=1e-7)
                if np.isfinite(result.x).all():
                    candidate_states=result.x.reshape(n,self.d).tolist(); candidate=candidate_states[-1]
                accepted=bool(result.success and candidate is not None); rank=int(np.linalg.matrix_rank(result.jac))
                info=dict(optimizer_success=bool(result.success),optimizer_status=int(result.status),optimizer_nfev=int(result.nfev),optimizer_njev=int(result.njev),optimizer_cost=float(result.cost),optimizer_optimality=float(result.optimality),optimizer_message=str(result.message))
                if accepted:
                    self.states=[p.copy() for p in result.x.reshape(n,self.d)]; status='graph' if observations else 'graph_no_current_ranges'
                else: status='predict_only_solver_failed'
            except (ValueError,FloatingPointError,np.linalg.LinAlgError) as error: status='predict_only_solver_error'; info=dict(error=type(error).__name__+': '+str(error))
        elapsed=time.perf_counter()-start; angular_valid=interval is None or interval['valid']; full_rank=rank is not None and rank==n*self.d
        if not angular_valid: status+='_missing_angular'
        if accepted and not full_rank: status+='_rank_deficient'
        return dict(pose=self.states[-1][:3].tolist(),bias_rad_s=float(self.states[-1][3]) if self.d==4 else 0.,accepted_graph=accepted,
            estimate_valid=bool(accepted and angular_valid and full_rank),status=status,candidate_pose=candidate[:3] if candidate is not None else None,candidate_bias_rad_s=candidate[3] if candidate is not None and self.d==4 else None,optimizer=info,
            prediction_pose=prediction[:3].tolist(),prediction_yaw_source='declared_external_initial_heading' if self.total_keyframes==1 else 'integrated_angular_minus_bias' if angular_valid else 'held_yaw_initial_guess_missing_angular',
            odom_yaw_fallback=False,angular_valid=bool(angular_valid),missing_angular_edges_cumulative=self.missing_angular_edges,
            graph_states=n,scalar_variables=n*self.d,state_dimension_per_keyframe=self.d,graph_time_span_s=self.times[-1]-self.times[0],
            numerical_rank=rank,numerical_full_rank=full_rank,marginalizations=self.marginalizations,marginal_wall_s=marginal_wall,solve_wall_s=elapsed,
            prior_matrix=self.prior.matrix.tolist(),prior_offset=self.prior.offset.tolist(),prior_point=self.prior.point.tolist(),marginalization_details=margins,
            objective_snapshot=dict(times_s=list(self.times),local_odom=np.asarray(self.local).tolist(),observations=copy.deepcopy(self.observations),intervals=copy.deepcopy(self.intervals),
                states=np.asarray(self.states).tolist(),candidate_states=candidate_states,prior=dict(point=self.prior.point.tolist(),matrix=self.prior.matrix.tolist(),offset=self.prior.offset.tolist())))
