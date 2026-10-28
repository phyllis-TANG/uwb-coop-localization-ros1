"""Wrap frozen receipt-prefix frontend, adding separately buffered real gyro."""
import collections
import copy
import math
import numpy as np
from pinned import f0_front, integration
from core import CARS, WindowGraph

ARMS=('M0','M1','M2','M3')
FIELD_CASES=('015334','033248','T08','T10')


class JointReplay(f0_front.JointReplay):
    def __init__(self,config,method,on_output,origin_ns):
        if method not in ARMS:raise ValueError('method')
        self.method=method;self.d=8 if method in ('M2','M3') else 6
        self.output_sink=on_output
        super().__init__(config,'D1' if method in ('M1','M3') else 'D0',self._forward,origin_ns)
        if self.d==8:self.graph=WindowGraph(config,self.arm=='D1')
        self.angular={c:integration.AngularBuffer(config['angular'][c]['max_hold_ns']['value'],config['frontend']['max_sensor_samples_per_stream']) for c in CARS}
        self.angular_decisions={c:collections.Counter() for c in CARS}
        self.current_intervals=None;self.original_case=None

    def ingest(self,raw):
        case=raw.get('case_id');self.original_case=case
        if self.config['scope']=='field':
            if case not in FIELD_CASES or self.config.get('execution_level')!='conditional_development':
                raise ValueError('BLOCKED field model/allowlist')
        elif not isinstance(case,str) or not case.startswith('synthetic_'):raise ValueError('synthetic case required')
        view=copy.deepcopy(raw)
        if self.config['scope']=='field':view['case_id']='synthetic_adapter_'+case
        car=raw.get('vehicle_id');kind=raw['kind']
        # Explicitly configured association policy, separately recorded per car.
        if kind in ('odom','uwb','imu'):
            policy=self.config['clock_policy'][car][kind]
            if policy['kind']=='bag_receipt_association':view['header_epoch_ns']=raw['receive_epoch_ns']
            elif policy['kind']!='shared_synthetic_header':raise ValueError('no undeclared identity clock map')
        result=super().ingest(view)
        angular='disabled'
        if kind=='imu':
            c=self.config['angular'][car];value=raw.get('value') or {}
            if value.get('units')!='rad/s':angular='unsupported_gyro_units'
            elif value.get('frame_id')!=c['imu_frame_id']['value']:angular='invalid_imu_frame'
            else:
                try:
                    v=np.asarray(value['angular_velocity_rad_s'],float)
                    if v.shape!=(3,) or not np.isfinite(v).all():raise ValueError('vector')
                    ident={k:raw.get(k) for k in ('record_index','header_epoch_ns','receive_epoch_ns','source_file_sha256','topic','raw_message_sha256','source_observation_id')}
                    ident['mapped_header_epoch_ns']=view['header_epoch_ns']
                    angular=self.angular[car].add(ident,float(v@np.asarray(c['body_z_in_imu_frame']['value']))) if self.d==8 else 'disabled'
                except (KeyError,ValueError,TypeError):angular='invalid_gyro_vector'
            self.angular_decisions[car][angular]+=1
        self.last_angular_decision=angular
        return result

    def _emit(self,stamp,bins):
        self.current_intervals=None
        if self.d==8 and self.graph.times and all(bins[c]['local_odom'] is not None for c in CARS):
            start=self.origin_ns+round(self.graph.times[-1]*1e9);end=self.origin_ns+round(stamp*1e9)
            cutoff=end+1_000_000_000
            self.current_intervals={c:self.angular[c].integrate(start,end,cutoff) for c in CARS}
        if self.d==8:self.graph.next_intervals=self.current_intervals
        super()._emit(stamp,bins)
        if self.d==8 and self.graph.times:
            for c in CARS:self.angular[c].prune(self.origin_ns+round(self.graph.times[-1]*1e9))

    def _forward(self,row):
        row['method_id']=self.method;row['experiment_id']=self.original_case
        row['state_dimension_per_keyframe']=self.d;row['scalar_variables']=self.d*row['graph_states']
        row['angular_intervals']=copy.deepcopy(self.current_intervals)
        row['angular_decisions_cumulative']={c:dict(v) for c,v in self.angular_decisions.items()}
        row['angular_buffer_counts']={c:len(self.angular[c].rows) for c in CARS}
        if self.d==6:
            row.update(bias_rad_s={c:None for c in CARS},angular_valid={c:None for c in CARS},
                estimate_valid={c:bool(row['accepted_graph']) for c in CARS},
                prediction_yaw_source={c:'legacy_odom_pose' for c in CARS},odom_yaw_fallback=False)
        else:
            pose=row['pose'];row['bias_rad_s']={c:None if pose is None else float(pose[4*i+3]) for i,c in enumerate(CARS)}
            row.setdefault('estimate_valid',{c:False for c in CARS});row.setdefault('angular_valid',{c:False for c in CARS})
            row.setdefault('prediction_yaw_source',{c:'no_prediction_missing_odom' for c in CARS});row.setdefault('odom_yaw_fallback',False)
            deps=[(s['dependency']['receive_epoch_ns']-self.origin_ns)/1e9 for a in (self.current_intervals or {}).values() for s in a['segments']]
            if deps:row['dependency_receipt_max_s']=max(deps+[row['dependency_receipt_max_s'] or -math.inf])
        row['joint_estimate_valid']=all(row['estimate_valid'].values())
        row['peer_factor_id']=('peer:car1_to_car2:'+str(row['state_epoch_ns'])) if row['peer_factor_used'] else None
        self.output_sink(copy.deepcopy(row))


def execute(events,config,method,sink):
    from configuration import validate
    validate(config)
    replay=None
    for raw in events:
        if replay is None:replay=JointReplay(config,method,sink,raw['receive_epoch_ns'])
        replay.ingest(raw)
    if replay is None:raise ValueError('empty')
    replay.finish();return replay
