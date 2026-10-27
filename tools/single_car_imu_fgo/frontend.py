"""Original bins/wait with angular factors; all input ns identities retained."""
import collections
import copy
from dataclasses import dataclass
import math
import time
import numpy as np
from legacy import FixedLagReplay,Event,antenna,pose_prior,rotation,wrap
from graph import WindowGraph
from integration import AngularBuffer
from configuration import map_ns


@dataclass(frozen=True)
class TimedEvent:
    received_s:float
    kind:str
    header_s:float|None
    value:object
    identity:dict
    raw:dict


def convert(raw,config,origin):
    kind=raw['kind']; source=raw.get('header_epoch_ns')
    mapped=map_ns(source,config['clock_maps'][kind]) if kind in ('odom','uwb','imu') else source
    identity={key:raw.get(key) for key in ('record_index','header_epoch_ns','receive_epoch_ns','source_file_sha256','topic')}; identity['mapped_header_epoch_ns']=mapped
    value=raw['value']['pose'] if kind=='odom' else raw.get('value')
    return TimedEvent((raw['receive_epoch_ns']-origin)/1e9,kind,(mapped-origin)/1e9 if mapped is not None else None,value,identity,raw)


class ImuReplay(FixedLagReplay):
    def __init__(self,config,on_output,origin,lag_s=20.):
        super().__init__(config['model'],config['replay'],on_output,lag_s=lag_s,max_nfev=config['optimizer']['max_nfev'],max_sensor_samples=config['frontend']['max_sensor_samples_per_stream'])
        self.config=copy.deepcopy(config); self.arm=config['arm']; self.origin=origin
        self.graph=WindowGraph(config,lag_s=lag_s,max_nfev=config['optimizer']['max_nfev'])
        self.angular=AngularBuffer(config['angular']['max_hold_ns']['value'],self.max_samples); self.rejections=collections.Counter()
    def ingest(self,event):
        super().ingest(event)
        source_kind='odom' if self.arm=='F1' else 'imu'
        if event.kind!=source_kind: return 'not_angular_control'
        try:
            if source_kind=='odom': rate=float(event.raw['value']['angular_z_rad_s'])
            else:
                row=event.raw['value']
                if row.get('units','rad/s')!='rad/s': self.rejections['unsupported_gyro_units']+=1; return 'unsupported_gyro_units'
                if row.get('frame_id')!=self.config['angular']['imu_frame_id']['value']: self.rejections['invalid_imu_frame']+=1; return 'invalid_imu_frame'
                vector=np.asarray(row['angular_velocity_rad_s'],dtype=float)
                if vector.shape!=(3,) or not np.isfinite(vector).all(): self.rejections['invalid_gyro_vector']+=1; return 'invalid_gyro_vector'
                rate=float(vector@np.asarray(self.config['angular']['body_z_in_imu_frame']['value']))
            status=self.angular.add(event.identity,rate); self.rejections[status]+=1; return status
        except (ValueError,TypeError,KeyError): self.rejections['invalid_angular_control']+=1; return 'invalid_angular_control'
    def _prune(self,next_state):
        super()._prune(next_state)
        if hasattr(self,'angular') and self.graph.times:
            self.angular.prune(self.origin+round(self.graph.times[-1]*1e9))
    def _emit(self,stamp,deadline):
        started=time.perf_counter(); self.last_closed_state=stamp; local,receipt=self._interpolate(stamp)
        state_ns=self.origin+round(stamp*1e9); cutoff=self.origin+round(deadline*1e9)
        if local is None:
            self.counters['missing_odom_bracket']+=1
            record=dict(state_time_s=stamp,availability_cutoff_s=deadline,status='missing_odom_bracket',accepted_graph=False,estimate_valid=False,pose=None,antenna_xy_m=None,graph_states=len(self.graph.times),dependency_receipt_max_s=None,solve_wall_s=0.,marginal_wall_s=0.,angular_valid=False,odom_yaw_fallback=False,angular_interval=None)
        else:
            grouped=collections.defaultdict(list); receipts=[receipt]
            for header,values,received in self.ranges:
                if abs(header-stamp)<=self.half:
                    for key,raw in values.items(): grouped[key].append(raw)
                    if values: receipts.append(received)
            observations={key:float(np.median(values)) for key,values in sorted(grouped.items()) if len(values)>=self.minimum}
            interval=None
            if self.graph.times:
                interval=self.angular.integrate(self.origin+round(self.graph.times[-1]*1e9),state_ns,cutoff)
                receipts.extend((s['dependency']['receive_epoch_ns']-self.origin)/1e9 for s in interval['segments'])
                if not interval['valid']: self.counters['missing_angular_interval']+=1
            self.dependency_max=max(self.dependency_max,max(receipts))
            if self.dependency_max>deadline+1e-12: raise AssertionError('future dependency')
            if self.first_local is None: self.first_local=local.copy()
            heading=math.radians(self.model['initial_heading_deg']); angle=heading-self.first_local[2]
            aligned=np.r_[rotation(angle)@(local[:2]-self.first_local[:2])+pose_prior(self.model).point[:2],local[2]+angle]
            result=self.graph.update(stamp,local,observations,interval); pose=np.asarray(result['pose']); prediction=np.asarray(result['prediction_pose'])
            self.previous_pose,self.previous_local=pose.copy(),local.copy()
            record=dict(result,state_time_s=stamp,availability_cutoff_s=deadline,antenna_xy_m=antenna(pose,self.model['base_to_antenna_body_xy_m']).tolist(),
                local_odom=local.tolist(),aligned_odom_pose=aligned.tolist(),aligned_odom_antenna_xy_m=antenna(aligned,self.model['base_to_antenna_body_xy_m']).tolist(),
                range_medians_m=observations,range_sample_counts={key:len(grouped[key]) for key in sorted(self.model['anchors_xyz_m'])},dependency_receipt_max_s=self.dependency_max,
                position_correction_m=float(np.linalg.norm(pose[:2]-prediction[:2])),yaw_correction_deg=math.degrees(abs(wrap(pose[2]-prediction[2]))),angular_interval=interval,
                aligned_odom_role='diagnostic_only_not_new_yaw_prediction_or_factor',fallback_yaw_source=result['prediction_yaw_source'])
        self._prune(stamp+self.step); record['sensor_buffer_counts']=dict(odom=len(self.odom),uwb=len(self.ranges),angular=len(self.angular.rows))
        elapsed=time.perf_counter()-started; worker_start=max(deadline,self.worker_finish); self.worker_finish=worker_start+elapsed
        record.update(arm=self.arm,state_epoch_ns=state_ns,availability_cutoff_epoch_ns=cutoff,update_wall_s=elapsed,
            estimated_worker_start_s=worker_start,estimated_worker_finish_s=self.worker_finish,estimated_worker_queue_s=worker_start-deadline,
            angular_source='odom_angular_z' if self.arm=='F1' else 'projected_imu',angular_rejections_cumulative=dict(self.rejections),
            field_accuracy_evaluated=False)
        self.output_count+=1; self.on_output(copy.deepcopy(record))
