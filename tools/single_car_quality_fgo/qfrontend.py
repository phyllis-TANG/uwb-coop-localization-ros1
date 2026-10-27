"""Causal shadow-first coordinator, frozen per-factor ledger and actual timing."""
import bisect
import collections
import copy
import math
import time
import numpy as np
from bridge import base_frontend,base_replay,base_config,antenna
from qgraph import WeightedPoseGraph,WeightedImuGraph,prior_record
from qpolicy import LinkPolicy
from qconfig import validate,values
from qio import digest,clean


def semantic(value):
    if isinstance(value,dict):
        return {k:semantic(v) for k,v in value.items() if not (k.endswith('_wall_s') or k.startswith(('estimated_worker_','host_','processing_')))}
    if isinstance(value,list):return [semantic(v) for v in value]
    return value


class RecentInputs:
    def __init__(self,base,origin):self.base,self.origin=base,origin;self.rows={'odom':[],'uwb':[]};self.count=0;self.prefix='0'*64
    def add(self,raw):
        self.count+=1;self.prefix=digest(dict(previous=self.prefix,event=clean(raw)))
        if raw['kind'] not in self.rows:return
        identity=base_frontend.convert(raw,self.base,self.origin).identity
        self.rows[raw['kind']].append((identity,copy.deepcopy(raw['value'])))
        if len(self.rows[raw['kind']])>self.base['frontend']['max_sensor_samples_per_stream']:raise BufferError('quality provenance source buffer capacity')
    def support(self,epoch):
        t=(epoch-self.origin)/1e9;deadline=epoch+1_000_000_000;model=self.base['model'];half=self.base['replay']['range_bin_half_width_s'];minimum=self.base['replay']['minimum_samples_per_link']
        odom=[r for r in self.rows['odom'] if r[0]['receive_epoch_ns']<=deadline];stamps=[(r[0]['mapped_header_epoch_ns']-self.origin)/1e9 for r in odom];i=bisect.bisect_left(stamps,t)
        endpoints=[]
        if i<len(stamps) and stamps[i]==t:endpoints=[odom[i][0]]
        elif 0<i<len(stamps):endpoints=[odom[i-1][0],odom[i][0]]
        support=collections.defaultdict(list)
        for identity,row in self.rows['uwb']:
            if identity['receive_epoch_ns']>deadline or abs((identity['mapped_header_epoch_ns']-self.origin)/1e9-t)>half:continue
            for key,raw in row.items():
                if key not in model['anchors_xyz_m'] or not np.isfinite(raw) or raw<=0 or raw-model['range_bias_m'][key]<=0:continue
                support[key].append(dict(identity=identity,raw_range_m=raw))
        medians={k:float(np.median([r['raw_range_m'] for r in rows])) for k,rows in support.items() if len(rows)>=minimum}
        return dict(state_epoch_ns=epoch,availability_cutoff_epoch_ns=deadline,odom_endpoints=endpoints,range_support=dict(support),range_medians=medians,input_prefix_count=self.count,input_prefix_digest=self.prefix)
    def prune(self,epoch):
        cutoff=epoch+1_000_000_000;times=[r[0]['mapped_header_epoch_ns'] for r in self.rows['odom']];i=bisect.bisect_right(times,epoch)-1
        if i>0:del self.rows['odom'][:i]
        self.rows['uwb']=[r for r in self.rows['uwb'] if r[0]['mapped_header_epoch_ns']>=cutoff-round(self.base['replay']['range_bin_half_width_s']*1e9)]


class Pipeline:
    def __init__(self,config,origin,graph_sink=None,ledger_sink=None,publication_sink=None,anchor_mono_ns=None,anchor_epoch_ns=None):
        validate(config);self.config=copy.deepcopy(config);self.base=config['base'];self.group=config['group'];self.origin=origin;self.enabled=config['quality_enabled'];self.p=values(config)
        self.graph_sink=graph_sink or (lambda r:None);self.ledger_sink=ledger_sink or (lambda r:None);self.publication_sink=publication_sink or (lambda r:None)
        self.anchor_mono_ns=time.monotonic_ns() if anchor_mono_ns is None else anchor_mono_ns;self.anchor_epoch_ns=time.time_ns() if anchor_epoch_ns is None else anchor_epoch_ns
        self.recent=RecentInputs(self.base,origin);self.links=sorted(self.base['model']['anchors_xyz_m']);self.policy={k:LinkPolicy(self.p) for k in self.links} if self.enabled else {}
        self.pending={};self.last_graph_id={};self.shadows={};self.source_roots={k:'0'*64 for k in self.links};self.current_decisions=None;self.pending_main=None;self.last_receive=None
        self.diag_gyro=base_frontend.AngularBuffer(self.base['angular']['max_hold_ns']['value'],self.base['frontend']['max_sensor_samples_per_stream']);self.diag_odom=base_frontend.AngularBuffer(self.base['angular']['max_hold_ns']['value'],self.base['frontend']['max_sensor_samples_per_stream']);self.last_diag_epoch=None;self.last_diag_local=None
        self.publications=0;self.last_available=None;self.ingest_cost_ns=0;self.worker_finish_ns=origin;self.current_cycle_start=None
        self.main=base_replay.make_replay(self.base,lambda r:self._graph_output('main',r),origin)
        if self.enabled:
            self.main.graph=self._new_graph(self._weight_provider,'main')
            for target in self.links:
                front=base_replay.make_replay(self.base,lambda r,k=target:self._graph_output(k,r),origin);front.graph=self._new_graph(None,'shadow:'+target);self.shadows[target]=front
    def _new_graph(self,provider,role):
        cls=WeightedImuGraph if self.base['arm']=='F3' else WeightedPoseGraph
        return cls(self.base,provider=provider,role=self.group+':'+role,origin=self.origin)
    def _weight_provider(self,epoch,observations):
        if self.current_decisions is None or self.current_decisions['epoch']!=epoch:raise AssertionError('main cannot create factor before causal frozen decisions')
        expected=self.current_decisions['support']['range_medians']
        if expected!=observations:raise AssertionError('quality aggregation differs from original frontend')
        rows=self.current_decisions['rows']
        return dict(weights={k:rows[k]['policy']['information_multiplier'] for k in observations},ids={k:rows[k]['factor_id'] for k in observations})
    def _graph_output(self,role,row):
        front=self.main if role=='main' else self.shadows[role];g=front.graph;epoch=row.get('state_epoch_ns',self.origin+round(row['state_time_s']*1e9));cutoff=epoch+1_000_000_000
        support=self.recent.support(epoch)
        if role!='main':
            support=copy.deepcopy(support);support['range_support'].pop(role,None);support['range_medians'].pop(role,None);support['input_prefix_digest']=self.source_roots[role]
        snapshot=copy.deepcopy(row.get('objective_snapshot'))
        if snapshot is None:
            snapshot=dict(times_s=list(g.times),local_odom=np.asarray(g.local).tolist(),observations=copy.deepcopy(g.observations),states=np.asarray(g.states).tolist(),candidate_states=None,prior=prior_record(g.prior),quality_weights=[{k:1. for k in o} for o in g.observations])
        snapshot.setdefault('quality_weights',[{k:1. for k in o} for o in snapshot['observations']])
        # Intervals are logged once at creation, not copied 21 times per update.
        if snapshot.get('intervals') is not None:
            snapshot['interval_end_epochs_ns']=[self.origin+round(t*1e9) for t in g.times[1:]];snapshot.pop('intervals',None)
        payload=copy.deepcopy(row);payload.pop('objective_snapshot',None);payload['state_epoch_ns']=epoch;payload['availability_cutoff_epoch_ns']=cutoff
        payload['objective_snapshot']=snapshot
        numeric_full=row.get('numerical_full_rank')
        if self.base['arm']=='F0' and self.enabled and row['accepted_graph']:
            objective=g._objective(g.times,g.local,g.observations,g.model,g.prior);J=objective.jac(np.asarray(g.states).ravel());rank=int(np.linalg.matrix_rank(J));numeric_full=rank==3*len(g.times)
            payload.update(numerical_rank=rank,numerical_full_rank=numeric_full)
        record=dict(record_type='graph_publication',role=role,excluded_target=role if role!='main' else None,state_epoch_ns=epoch,availability_cutoff_epoch_ns=cutoff,
            previous_record_id=self.last_graph_id.get(role),input_prefix_count=self.recent.count,input_prefix_digest=self.recent.prefix if role=='main' else self.source_roots[role],
            support_new=support,row=payload,shadow_weights_adaptive=False if role!='main' else None)
        record['record_id']=digest(semantic(clean(record)));self.last_graph_id[role]=record['record_id'];self.graph_sink(clean(record))
        if role=='main':
            if self.pending_main is not None:raise BufferError('main output not committed')
            self.pending_main=record
        else:
            self.pending.setdefault(epoch,{})[role]=record
            if len(self.pending)>2:raise BufferError('shadow cannot run ahead of main publication')
    def _geometry(self,shadow,target):
        row=shadow['row'];snapshot=row['objective_snapshot'];observations=snapshot['observations'][-1] if snapshot['observations'] else {}
        others=sorted(k for k in observations if k!=target)
        if len(others)<self.p['min_other_links']:return None,'INSUFFICIENT_OTHER_WALL_LINKS',None
        pose=row['pose'];tagxy=antenna(pose,self.base['model']['base_to_antenna_body_xy_m']);height=self.base['model']['antenna_height_m'];H=[]
        for key in others:
            delta=np.r_[tagxy,height]-np.asarray(self.base['model']['anchors_xyz_m'][key]);distance=float(np.linalg.norm(delta))
            if distance<1e-10:return None,'DEGENERATE_SHADOW_GEOMETRY',None
            H.append(delta[:2]/distance)
        singular=np.linalg.svd(H,compute_uv=False);ratio=float(singular[-1]/singular[0]) if singular[0]>0 else 0.
        if ratio<self.p['min_xy_singular_ratio']:return None,'WEAK_SHADOW_XY_GEOMETRY',dict(other_links=others,singular_values=singular.tolist(),ratio=ratio)
        delta=np.r_[tagxy,height]-np.asarray(self.base['model']['anchors_xyz_m'][target]);pred=float(np.linalg.norm(delta))
        return pred,None,dict(other_links=others,singular_values=singular.tolist(),ratio=ratio)
    def _motion_diagnostic(self,epoch):
        cutoff=epoch+10**9;local,_=self.main._interpolate((epoch-self.origin)/1e9);result=dict(not_used_for_quality=True,comparison_is_not_truth=True,state_epoch_ns=epoch,gyro_interval=None,odom_rate_interval=None,odom_pose_delta_yaw_rad=None,raw_odom_rate_minus_gyro_rad=None,raw_odom_pose_minus_gyro_rad=None)
        if self.last_diag_epoch is not None:
            gyro=self.diag_gyro.integrate(self.last_diag_epoch,epoch,cutoff);odom=self.diag_odom.integrate(self.last_diag_epoch,epoch,cutoff);result['gyro_interval']=gyro;result['odom_rate_interval']=odom
            if local is not None and self.last_diag_local is not None:result['odom_pose_delta_yaw_rad']=math.atan2(math.sin(local[2]-self.last_diag_local[2]),math.cos(local[2]-self.last_diag_local[2]))
            if gyro['valid'] and odom['valid']:result['raw_odom_rate_minus_gyro_rad']=odom['raw_angle_rad']-gyro['raw_angle_rad']
            if gyro['valid'] and result['odom_pose_delta_yaw_rad'] is not None:result['raw_odom_pose_minus_gyro_rad']=result['odom_pose_delta_yaw_rad']-gyro['raw_angle_rad']
        self.last_diag_epoch=epoch;self.last_diag_local=local.copy() if local is not None else None;self.diag_gyro.prune(epoch);self.diag_odom.prune(epoch)
        return result
    def _diagnostic_ingest(self,raw):
        kind=raw['kind']
        if kind not in ('odom','imu'):return
        try:
            event=base_frontend.convert(raw,self.base,self.origin)
            if kind=='odom':self.diag_odom.add(event.identity,float(raw['value']['angular_z_rad_s']))
            else:
                value=raw['value']
                if value.get('units','rad/s')!='rad/s' or value.get('frame_id')!=self.base['angular']['imu_frame_id']['value']:return
                vector=np.asarray(value['angular_velocity_rad_s'],dtype=float)
                if vector.shape==(3,) and np.isfinite(vector).all():self.diag_gyro.add(event.identity,float(vector@self.base['angular']['body_z_in_imu_frame']['value']))
        except (ValueError,TypeError,KeyError):return
    def _prepare(self,epoch):
        support=self.recent.support(epoch);current=self.pending.get(epoch,{});rows={};cutoff=epoch+1_000_000_000
        for target in self.links:
            aggregate=support['range_medians'].get(target);reference=current.get(target);reason=None;score=None;signed=None;prediction=None;geometry=None
            if self.enabled:
                if aggregate is None:reason='NO_CURRENT_AGGREGATED_LINK'
                elif not support['odom_endpoints']:reason='NO_ODOM_BRACKET'
                elif reference is None:reason='SHADOW_NOT_AVAILABLE_AT_SAME_CUTOFF'
                elif reference['availability_cutoff_epoch_ns']!=cutoff:raise AssertionError('future/stale shadow reference')
                elif not reference['row']['accepted_graph']:reason='SHADOW_SOLVE_NOT_ACCEPTED'
                elif not reference['row'].get('numerical_full_rank',False):reason='SHADOW_NUMERICAL_RANK_INSUFFICIENT'
                elif self.base['arm']=='F3' and not reference['row']['angular_valid']:reason='SHADOW_ANGULAR_GAP'
                else:
                    prediction,reason,geometry=self._geometry(reference,target)
                    if reason is None:signed=aggregate-self.base['model']['range_bias_m'][target]-prediction;score=abs(signed)/self.p['score_scale_m']
                decision=self.policy[target].step(epoch,score,reason)
            else:decision=dict(state='unmonitored',policy_mode_held=None,reason='QUALITY_NOT_ENABLED_BASELINE',information_multiplier=1.,score=None,monitorable=None,transition=False)
            gain=decision['information_multiplier'];sigma=self.base['model']['graph_parameters']['range_sigma_m'];factor_id=f'{self.group}|{epoch}|{target}'
            row=dict(record_type='frozen_quality_factor',interface_version='quality_fgo_v1',publication_id=f'{self.group}|{epoch}',factor_id=factor_id,group=self.group,target=target,
                state_epoch_ns=epoch,availability_cutoff_epoch_ns=cutoff,frozen_host_epoch_ns=time.time_ns(),frozen_host_monotonic_ns=time.monotonic_ns(),
                actual_output_available_epoch_ns=None,availability_reason='joined later via immutable publication_id',
                original_link_quality=None,original_link_quality_status='NaN_or_unavailable_not_used_for_quality',
                raw_aggregate_m=aggregate,P1_subtracted_m=self.base['model']['range_bias_m'][target],corrected_aggregate_m=aggregate-self.base['model']['range_bias_m'][target] if aggregate is not None else None,
                raw_signed_consistency_residual_m=signed,raw_residual_sign='corrected_measurement_minus_excluded_prediction',engineering_score=score,score_scale_m=self.p['score_scale_m'],score_semantics='fixed-scale engineering consistency, not calibrated NIS/PL',
                reference_record_id=reference['record_id'] if reference else None,reference_excluded_target=target if self.enabled else None,reference_geometry=geometry,
                target_dependencies=support['range_support'].get(target,[]),shared_input_prefix=dict(count=support['input_prefix_count'],digest=support['input_prefix_digest']),
                policy=decision,original_sigma_m=sigma,base_nominal_information_per_m2=1/sigma**2,
                actual_information_multiplier=gain if aggregate is not None else None,actual_residual_sqrt_multiplier=math.sqrt(gain) if aggregate is not None else None,
                actual_nominal_information_per_m2=gain/sigma**2 if aggregate is not None else None,
                information_admitted=bool(aggregate is not None and gain>0),factor_action='absent_no_factor' if aggregate is None else 'zero_information_row' if gain==0 else 'weighted_pseudo_huber_row',
                frozen_before_main_solve=True,no_history_rollback=True)
            rows[target]=row;self.ledger_sink(clean(row))
        self.current_decisions=dict(epoch=epoch,support=support,rows=rows,motion_diagnostic=self._motion_diagnostic(epoch))
    def _wait(self,receive_ns):
        if not self.config['timing']['paced']:return
        deadline=self.anchor_mono_ns+receive_ns-self.origin
        while True:
            remaining=deadline-time.monotonic_ns()
            if remaining<=0:return
            time.sleep(min(remaining/1e9,.05))
    def _commit(self,start_ns):
        if self.pending_main is None:return
        record=self.pending_main;epoch=record['state_epoch_ns'];self.pending_main=None;row=record['row'];cutoff=record['availability_cutoff_epoch_ns'];compute_ns=time.monotonic_ns()-start_ns+self.ingest_cost_ns;self.ingest_cost_ns=0
        if self.config['timing']['paced']:
            available=self.origin+time.monotonic_ns()-self.anchor_mono_ns;timing='paced_actual_host_monotonic_mapping'
        else:
            available=max(cutoff,self.worker_finish_ns)+compute_ns;timing='development_virtual_fifo_plus_measured_compute'
        self.worker_finish_ns=available
        output=dict(record_type='main_publication',publication_id=f'{self.group}|{epoch}',group=self.group,state_epoch_ns=epoch,availability_cutoff_epoch_ns=cutoff,
            available_receive_epoch_ns=available,host_data_ready_epoch_ns=time.time_ns(),host_data_ready_monotonic_ns=time.monotonic_ns(),timing_mode=timing,
            measured_complete_processor_wall_s=compute_ns/1e9,processing_cycle_start_monotonic_ns=start_ns,monitoring_and_shadow_included=self.enabled,
            main_solve_start_monotonic_ns=self.current_decisions['main_solve_start_monotonic_ns'],main_solve_finish_monotonic_ns=self.current_decisions['main_solve_finish_monotonic_ns'],graph_record_id=record['record_id'],frozen_factor_ids=[r['factor_id'] for r in self.current_decisions['rows'].values()],row=row)
        diagnostics=[]
        if row.get('pose') is not None:
            model=self.base['model'];xy=antenna(row['pose'],model['base_to_antenna_body_xy_m']);sigma=model['graph_parameters']['range_sigma_m']
            for target,decision in self.current_decisions['rows'].items():
                if decision['raw_aggregate_m'] is None:continue
                delta=np.r_[xy,model['antenna_height_m']]-np.asarray(model['anchors_xyz_m'][target]);error=float(np.linalg.norm(delta))-decision['corrected_aggregate_m'];z=error/sigma;s=math.sqrt(1+z*z);original=z*math.sqrt(2/(s+1));derivative=math.sqrt((s+1)/2)/s/sigma;gain=decision['actual_information_multiplier']
                diagnostics.append(dict(factor_id=decision['factor_id'],postfit_signed_raw_residual_m=error,residual_sign='main_prediction_minus_corrected_measurement',original_pseudo_huber_residual=original,actual_weighted_residual=math.sqrt(gain)*original,
                    original_robust_J_scale_per_m=derivative,actual_robust_J_scale_per_m=math.sqrt(gain)*derivative,quality_information_multiplier=gain,not_used_for_quality=True))
        output['postfit_factor_diagnostics']=diagnostics
        output['motion_conflict_diagnostic']=self.current_decisions['motion_diagnostic']
        # sink flushes actual pose/graphs/ledger before recording final availability.
        final=self.publication_sink(clean(output))
        if isinstance(final,dict):self.worker_finish_ns=final['available_receive_epoch_ns']
        self.publications+=1;self.pending.pop(epoch,None);self.current_decisions=None;self.recent.prune(epoch)
    def _clock(self,cutoff):
        self._wait(cutoff);start=time.monotonic_ns();raw=dict(kind='clock',case_id='scheduler',record_index=-1,receive_epoch_ns=cutoff+1,value=None)
        event=base_frontend.convert(raw,self.base,self.origin)
        for front in self.shadows.values():front.ingest(event)
        epoch=cutoff-1_000_000_000;self._prepare(epoch);self.current_decisions['main_solve_start_monotonic_ns']=time.monotonic_ns();self.main.ingest(event);self.current_decisions['main_solve_finish_monotonic_ns']=time.monotonic_ns();self._commit(start)
    def ingest(self,raw):
        receive=raw['receive_epoch_ns']
        if self.last_receive is not None and receive<self.last_receive:raise ValueError('recorded receive order required')
        while self.main.next_state is not None:
            deadline=self.origin+round((self.main.next_state+self.main.delay)*1e9)
            if deadline>=receive:break
            self._clock(deadline)
        self._wait(receive);start=time.monotonic_ns();self.recent.add(raw);self._diagnostic_ingest(raw)
        for target,front in self.shadows.items():
            filtered=copy.deepcopy(raw)
            if raw['kind']=='uwb':filtered['value']={k:v for k,v in raw['value'].items() if k!=target}
            self.source_roots[target]=digest(dict(previous=self.source_roots[target],event=clean(filtered)))
            front.ingest(base_frontend.convert(filtered,self.base,self.origin))
        self.main.ingest(base_frontend.convert(raw,self.base,self.origin));self.ingest_cost_ns+=time.monotonic_ns()-start;self.last_receive=receive
    def finish(self):
        if self.last_receive is None:return
        # Equal-deadline messages have all been admitted; no timer beyond recorded EOF.
        if self.main.next_state is not None:
            deadline=self.origin+round((self.main.next_state+self.main.delay)*1e9)
            if deadline<=self.last_receive:self._clock(deadline)
