"""Independent neutral-ledger checks for a future frozen A adapter.

Consumes logged before/after prediction states; never estimates a trajectory or
imports an online estimator. The adapter/policy must name A's frozen integration
rule. Passing fixtures does not verify an unavailable A implementation.
"""
import math
import numpy as np


def wrapped(value):return math.atan2(math.sin(value),math.cos(value))


def covariance_check(value,size):
    p=np.asarray(value,dtype=float)
    if p.shape!=(size,size) or not np.isfinite(p).all():raise ValueError('covariance shape/nonfinite')
    if np.max(np.abs(p-p.T))>1e-10 or np.linalg.eigvalsh((p+p.T)/2).min() < -1e-10:
        raise ValueError('covariance nonsymmetry/negative eigenvalue')
    return True


def source(row,lookup,car,kind,cutoff,measurement_ns,segment_start,max_age):
    key=(kind,row)
    if key not in lookup:raise ValueError('unknown control trace')
    item=lookup[key]
    if item['vehicle_id']!=car:raise ValueError('cross-car control')
    if item['receive_epoch_ns']>cutoff:raise ValueError('not-yet-arrived control')
    if measurement_ns>segment_start or segment_start-measurement_ns>max_age:
        raise ValueError('future or stale measurement support')
    return item


def verify_segment(log,lookup,policy):
    # All times here are declared target-clock values in the neutral ledger.
    # Raw header is never silently equated with the physical target clock.
    start,end=log['segment_start_ns'],log['segment_end_ns']
    cutoff,decision,publish=[log[k] for k in ('control_available_asof_receive_ns','decision_receive_ns','publication_receive_ns')]
    if not all(type(x) is int for x in (start,end,cutoff,decision,publish)) or not start<=end or not cutoff<=decision<=publish:
        raise ValueError('invalid segment/arrival time order')
    car=log['vehicle_id'];mode=log['motion_mode']
    if mode not in ('body_odom_rate','body_imu_fixed_bias','body_imu_bias'):raise ValueError('neutral ledger is for new motion predictions only')
    v=source(log['velocity_record_index'],lookup,car,'odom',cutoff,log['velocity_measurement_ns'],start,policy['max_velocity_age_ns'])
    use_imu=mode!='body_odom_rate';kind='imu' if use_imu else 'odom'
    rate=source(log['rate_record_index'],lookup,car,kind,cutoff,log['rate_measurement_ns'],start,policy['max_rate_age_ns'])
    before=np.asarray(log['before_state'],float);after=np.asarray(log['predicted_state'],float)
    if before.shape!=(4,) or after.shape!=(4,) or not np.isfinite(np.r_[before,after]).all():raise ValueError('prediction state invalid')
    raw=float(rate['angular_velocity_z'] if use_imu else rate['angular_z'])
    omega=(raw*policy['gyro_sign']*policy['gyro_scale_to_rad_s']-before[3]) if use_imu else raw
    if mode=='body_imu_fixed_bias' and (before[3]!=0 or after[3]!=0):raise ValueError('fixed-zero bias mode changed bias')
    if not math.isclose(log['applied_angular_rate_rad_s'],omega,rel_tol=1e-11,abs_tol=1e-12):raise ValueError('gyro sign/unit/bias mismatch')
    dt=(end-start)/1e9;vx,vy=float(v['linear_x']),float(v['linear_y']);angle=omega*dt
    rule=policy['integration_rule']
    if rule=='constant_twist_exact':
        a=math.sin(angle)/omega if abs(omega)>1e-10 else dt
        b=(1-math.cos(angle))/omega if abs(omega)>1e-10 else 0.0
        bx,by=a*vx-b*vy,b*vx+a*vy;heading=before[2]
    elif rule in ('forward_euler','midpoint'):
        bx,by=vx*dt,vy*dt;heading=before[2]+(angle/2 if rule=='midpoint' else 0)
    else:raise ValueError('A frozen integration rule not supported; explicit adapter required')
    predicted=np.array([before[0]+math.cos(heading)*bx-math.sin(heading)*by,
                        before[1]+math.sin(heading)*bx+math.cos(heading)*by,wrapped(before[2]+angle),before[3]])
    delta=predicted-after;delta[2]=wrapped(delta[2])
    if np.max(np.abs(delta))>1e-9:raise ValueError('logged pure prediction violates frozen kinematics')
    if 'predicted_covariance' in log:covariance_check(log['predicted_covariance'],4)
    return {'verified':True,'scope':'one logged pure motion prediction; no UWB update or accuracy evaluation'}
