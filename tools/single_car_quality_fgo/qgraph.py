"""Adapters over frozen factor definitions; only UWB rows get sqrt(g) once.

The two _frozen_update methods below are source-derived orchestration from the
base commit, with local objective/elimination hooks and extra audit fields only.
No old module or global is patched; shadow/main instances share no mutable data.
"""
import copy
import math
import time
import numpy as np
from scipy.linalg import qr
from scipy.optimize import least_squares
from bridge import PoseGraph,PoseObjective,BoundaryPrior,pose_predict,imu_graph
from qio import digest


def prior_record(prior):return dict(point=prior.point.tolist(),matrix=prior.matrix.tolist(),offset=prior.offset.tolist())


class WeightRows:
    def _init_weights(self,observations,weights,first):
        if len(observations)!=len(weights):raise ValueError('one frozen weight map per keyframe')
        self.frozen_weights=copy.deepcopy(weights);self.weight_rows=[]
        for i,row in enumerate(observations):
            for key in sorted(row):
                gain=weights[i][key]
                if not math.isfinite(gain) or not 0<=gain<=1:raise ValueError('information multiplier bounds')
                self.weight_rows.append((first+len(self.weight_rows),math.sqrt(gain)))
        self._wx=None
    def evaluate(self,flat):
        flat=np.asarray(flat)
        if self._wx is not None and np.array_equal(flat,self._wx):return self._wr,self._wj
        r,J=super().evaluate(flat);r=r.copy();J=J.copy()
        for row,scale in self.weight_rows:r[row]*=scale;J[row]*=scale
        self._wx=flat.copy();self._wr,self._wj=r,J;return r,J


class WeightedPoseObjective(WeightRows,PoseObjective):
    def __init__(self,times,local,observations,model,prior,weights):
        PoseObjective.__init__(self,times,local,observations,model,prior);self._init_weights(observations,weights,3*self.n)


class WeightedImuObjective(WeightRows,imu_graph.Objective):
    def __init__(self,times,local,observations,intervals,model,prior,config,weights):
        imu_graph.Objective.__init__(self,times,local,observations,intervals,model,prior,config);self._init_weights(observations,weights,len(prior.offset)+2*(self.n-1))


class WeightBook:
    def _setup(self,provider,role,origin):
        self.provider=provider;self.role=role;self.origin=origin;self.quality_weights=[];self.quality_ids=[];self.marginal_events=[]
        self._initial_guess=None;self._candidate_states=None
    def _freeze(self,stamp,observations):
        epoch=self.origin+round(stamp*1e9)
        result=self.provider(epoch,observations) if self.provider else dict(weights={k:1. for k in observations},ids={k:f'{self.role}|{epoch}|{k}' for k in observations})
        if set(result['weights'])!=set(observations) or set(result['ids'])!=set(observations):raise ValueError('ledger/factor key mismatch')
        self.quality_weights.append(copy.deepcopy(result['weights']));self.quality_ids.append(copy.deepcopy(result['ids']))
        self.marginal_events=[];self._initial_guess=None;self._candidate_states=None
    def _details(self,before,after,states,times,local,observations,intervals,weights,ids,constant,rank_info):
        record=dict(**rank_info,incident_factor_policy='carried_prior + oldest UWB + first translation + first angular/bias only',includes_retained_UWB=False,retains_affine_offset=True,
            consumed_quality_factor_ids=list(ids[0].values()),retained_quality_factor_ids=[],prior_before_digest=digest(prior_record(before)),prior_after_digest=digest(prior_record(after)),
            linearization_input=dict(states=np.asarray(states[:2]).tolist(),times_s=list(times[:2]),local_odom=np.asarray(local[:2]).tolist(),observations=[dict(observations[0]),{}],
                intervals=copy.deepcopy(intervals[:1]) if intervals is not None else None,prior=prior_record(before),quality_weights=[dict(weights[0]),{}],factor_ids=[dict(ids[0]),{}]),
            prior_after=prior_record(after),eliminated_constant=constant)
        return record
    def _snapshot(self,result,intervals=None):
        result['quality_weights']=copy.deepcopy(self.quality_weights);result['quality_factor_ids']=copy.deepcopy(self.quality_ids)
        result['optimizer_initial_guess']=copy.deepcopy(self._initial_guess)
        result['objective_snapshot']=dict(times_s=list(self.times),local_odom=np.asarray(self.local).tolist(),observations=copy.deepcopy(self.observations),
            intervals=copy.deepcopy(intervals),states=np.asarray(self.states).tolist(),candidate_states=copy.deepcopy(self._candidate_states),prior=prior_record(self.prior),
            quality_weights=copy.deepcopy(self.quality_weights),quality_factor_ids=copy.deepcopy(self.quality_ids))
        return result


class WeightedPoseGraph(WeightBook,PoseGraph):
    def __init__(self,config,provider=None,role='main',origin=0):
        PoseGraph.__init__(self,config['model'],config['fixed_lag_s'],config['optimizer']['max_nfev']);self._setup(provider,role,origin)
    def update(self,stamp,local,observations):
        self._freeze(stamp,observations);result=self._frozen_update(stamp,local,observations)
        result['marginalization_details']=copy.deepcopy(self.marginal_events)
        return self._snapshot(result)
    def _objective(self,times,local,observations,model,prior):return WeightedPoseObjective(times,local,observations,model,prior,self.quality_weights)
    def _eliminate(self,states,times,local,observations,model,prior):
        weights,ids=copy.deepcopy(self.quality_weights[:2]),copy.deepcopy(self.quality_ids[:2])
        objective=WeightedPoseObjective(times[:2],local[:2],[observations[0],{}],model,prior,weights)
        r,jac=objective.evaluate(np.asarray(states[:2]).ravel());old,boundary=jac[:,:3],jac[:,3:6]
        if np.linalg.matrix_rank(old)!=3:raise ValueError('Rank-deficient old-state elimination')
        if np.linalg.matrix_rank(jac)!=6:raise ValueError('Rank-deficient joint information; boundary is not fully constrained')
        q,_=np.linalg.qr(old,mode='complete');pj=q[:,3:].T@boundary;pr=q[:,3:].T@r;q2,M=np.linalg.qr(pj,mode='reduced');offset=q2.T@pr
        if M.shape!=(3,3) or np.linalg.matrix_rank(M)!=3:raise ValueError('Rank-deficient boundary prior')
        sign=np.where(np.diag(M)<0,-1.,1.);M,offset=sign[:,None]*M,sign*offset;constant=max(0.,float(pr@pr-offset@offset));after=BoundaryPrior(states[1],M,offset)
        self.marginal_events.append(self._details(prior,after,states,times,local,observations,None,weights,ids,constant,dict(old_dimension=3,old_rank=3,boundary_rank=3,rank_deficient=False)))
        del self.quality_weights[0];del self.quality_ids[0]
        return after,constant
    def _frozen_update(self, stamp, local, observations):
        local = np.asarray(local, dtype=float).copy()
        if self.times and stamp-self.times[-1] < self.minimum_step-1e-9:
            raise ValueError('Graph keyframes violate the minimum spacing')
        if local.shape != (3,) or not np.isfinite(local).all():
            raise ValueError('Invalid local Odom state')
        guess = self.prior.point.copy() if not self.states else pose_predict(
            self.states[-1], self.local[-1], local)
        self.times.append(float(stamp)); self.local.append(local)
        self.observations.append(dict(observations)); self.states.append(guess)
        self.total_keyframes += 1
        self.peak_transient_states = max(self.peak_transient_states, len(self.times))
        started = time.perf_counter()
        while self.lag_s is not None and self.times[-1]-self.times[0] > self.lag_s+1e-12:
            self.prior, constant = self._eliminate(
                self.states, self.times, self.local, self.observations, self.model, self.prior)
            self.eliminated_constant += constant
            for seq in (self.times, self.local, self.observations, self.states):
                del seq[0]
            self.marginalizations += 1
        marginal_wall = time.perf_counter()-started
        n = len(self.times)
        self.peak_solve_states = max(self.peak_solve_states, n)
        accepted, status = False, 'predict_only_warmup'
        info, candidate = {}, None
        started = time.perf_counter()
        if n >= 3:
            try:
                objective = self._objective(self.times, self.local, self.observations, self.model, self.prior)
                self._initial_guess=np.asarray(self.states).tolist()
                result = least_squares(objective.fun, np.asarray(self.states).ravel(),
                    jac=objective.jac, method='trf', tr_solver='exact', loss='linear',
                    max_nfev=self.max_nfev, ftol=1e-7, xtol=1e-7, gtol=1e-7)
                if np.isfinite(result.x).all():
                    self._candidate_states=result.x.reshape(n,3).tolist()
                    candidate = result.x.reshape(n, 3)[-1].tolist()
                accepted = bool(result.success and candidate is not None)
                info = dict(optimizer_success=bool(result.success), optimizer_status=int(result.status),
                            optimizer_nfev=int(result.nfev), optimizer_njev=int(result.njev),
                            optimizer_cost=float(result.cost), optimizer_optimality=float(result.optimality),
                            optimizer_message=str(result.message))
                if accepted:
                    self.states = [p.copy() for p in result.x.reshape(n, 3)]
                    status = 'graph' if observations else 'graph_no_current_ranges'
                else:
                    status = 'predict_only_solver_failed'
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                status = 'predict_only_solver_error'
                info = dict(error=type(error).__name__+': '+str(error))
        solve_wall = time.perf_counter()-started
        return dict(pose=self.states[-1].tolist(), accepted_graph=accepted, status=status,
                    candidate_pose=candidate, optimizer=info, graph_states=n,
                    graph_time_span_s=self.times[-1]-self.times[0],
                    marginalizations=self.marginalizations, marginal_wall_s=marginal_wall,
                    solve_wall_s=solve_wall, prior_matrix=self.prior.matrix.tolist(),
                    prior_offset=self.prior.offset.tolist(), prior_point=self.prior.point.tolist())


class WeightedImuGraph(WeightBook,imu_graph.WindowGraph):
    def __init__(self,config,provider=None,role='main',origin=0):
        imu_graph.WindowGraph.__init__(self,config);self._setup(provider,role,origin)
    def update(self,stamp,local,observations,interval=None):
        self._freeze(stamp,observations);result=self._frozen_update(stamp,local,observations,interval)
        return self._snapshot(result,self.intervals)
    def _objective(self,times,local,observations,intervals,model,prior,config):return WeightedImuObjective(times,local,observations,intervals,model,prior,config,self.quality_weights)
    def _eliminate(self,states,times,local,observations,intervals,model,prior,config):
        weights,ids=copy.deepcopy(self.quality_weights[:2]),copy.deepcopy(self.quality_ids[:2]);d=len(prior.point)
        objective=WeightedImuObjective(times[:2],local[:2],[observations[0],{}],intervals[:1],model,prior,config,weights)
        r,J=objective.evaluate(np.asarray(states[:2]).ravel());old,boundary=J[:,:d],J[:,d:2*d]
        Q,R,_=qr(old,mode='full',pivoting=True);tol=max(old.shape)*np.finfo(float).eps*np.linalg.norm(old,ord=2);rank=int(np.sum(np.abs(np.diag(R))>tol))
        projected=Q[:,rank:].T@boundary;residual=Q[:,rank:].T@r;Q2,M=np.linalg.qr(projected,mode='reduced');offset=Q2.T@residual
        if len(M):
            sign=np.where(np.diag(M)<0,-1.,1.);M=sign[:,None]*M;offset=sign*offset
        constant=max(0.,float(residual@residual-offset@offset));after=imu_graph.Prior(states[1],M,offset)
        info=self._details(prior,after,states,times,local,observations,intervals,weights,ids,constant,dict(old_dimension=d,old_rank=rank,boundary_rank=int(np.linalg.matrix_rank(M)) if M.size else 0,rank_deficient=bool(rank<d or (np.linalg.matrix_rank(M) if M.size else 0)<d)))
        del self.quality_weights[0];del self.quality_ids[0]
        return after,constant,info
    def _frozen_update(self,stamp,local,observations,interval=None):
        local=np.asarray(local,dtype=float).copy()
        if local.shape!=(3,) or not np.isfinite(local).all(): raise ValueError('invalid local pose')
        if self.times and stamp-self.times[-1]<self.minimum_step-1e-9: raise ValueError('keyframe spacing')
        if self.states:
            if interval is None: raise ValueError('missing angular interval object')
            guess=imu_graph.predict(self.states[-1],self.local[-1],local,interval); self.intervals.append(copy.deepcopy(interval)); self.missing_angular_edges+=int(not interval['valid'])
        else: guess=self.prior.point.copy()
        prediction=guess.copy(); self.times.append(float(stamp)); self.local.append(local); self.observations.append(dict(observations)); self.states.append(guess); self.total_keyframes+=1
        self.peak_transient_states=max(self.peak_transient_states,len(self.times)); margins=[]; start=time.perf_counter()
        while self.lag_s is not None and self.times[-1]-self.times[0]>self.lag_s+1e-12:
            self.prior,c,info=self._eliminate(self.states,self.times,self.local,self.observations,self.intervals,self.model,self.prior,self.config)
            self.eliminated_constant+=c; self.marginalizations+=1; margins.append(info)
            for seq in (self.times,self.local,self.observations,self.states): del seq[0]
            del self.intervals[0]
        marginal_wall=time.perf_counter()-start; n=len(self.times); self.peak_solve_states=max(self.peak_solve_states,n)
        accepted=False; status='predict_only_warmup'; info={}; candidate=None; candidate_states=None; rank=None; start=time.perf_counter()
        if n>=3:
            try:
                objective=self._objective(self.times,self.local,self.observations,self.intervals,self.model,self.prior,self.config)
                self._initial_guess=np.asarray(self.states).tolist()
                result=least_squares(objective.fun,np.asarray(self.states).ravel(),jac=objective.jac,method='trf',tr_solver='exact',loss='linear',max_nfev=self.max_nfev,ftol=1e-7,xtol=1e-7,gtol=1e-7)
                if np.isfinite(result.x).all():
                    self._candidate_states=result.x.reshape(n,self.d).tolist()
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
