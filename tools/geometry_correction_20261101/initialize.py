"""Measurement-only moving initialization; no truth or placement arguments."""
import math
import time
import numpy as np
from scipy.optimize import least_squares
from local_support import CARS,EPOCH,digest

def rot(y):
    c,s=math.cos(y),math.sin(y);return np.array([[c,-s],[s,c]])

def path(events,car,heading):
    odom={e['header_epoch_ns']:np.array(e['value']['pose']) for e in events if e['kind']=='odom' and e['vehicle_id']==car and e['header_epoch_ns']<=EPOCH+6*10**9}
    gyro={e['header_epoch_ns']:float(e['value']['angular_velocity_rad_s'][2]) for e in events if e['kind']=='imu' and e['vehicle_id']==car and e['header_epoch_ns']<EPOCH+6*10**9}
    stamps=sorted(odom);positions={stamps[0]:np.zeros(2)};yaw={stamps[0]:heading}
    if stamps!=[EPOCH+i*50_000_000 for i in range(121)]:raise ValueError('Incomplete initialization odometry support')
    for a,b in zip(stamps,stamps[1:]):
        if a not in gyro:raise ValueError('Incomplete initialization gyro support; no odom angle fallback')
        positions[b]=positions[a]+rot(yaw[a])@rot(-odom[a][2])@(odom[b][:2]-odom[a][:2])
        yaw[b]=yaw[a]+gyro[a]*.05  # prior bias=0; true bias is never read.
    return positions,yaw

def fit_xy(offsets,refs,height,measured):
    offsets=np.asarray(offsets);refs=np.asarray(refs);measured=np.asarray(measured)
    # Squared differences at the same timestamp cancel the moving point norm.
    A=[];rhs=[]
    for o,z in zip(offsets,measured):
        for j in range(1,4):
            d=refs[j,:2]-refs[0,:2]
            A.append(2*d)
            rhs.append(z[0]**2-z[j]**2+refs[j,:2]@refs[j,:2]-refs[0,:2]@refs[0,:2]
                +(height-refs[j,2])**2-(height-refs[0,2])**2-2*d@o)
    A=np.array(A)
    if np.linalg.matrix_rank(A)!=2:raise ValueError('Unobservable initializer')
    start=np.linalg.lstsq(A,rhs,rcond=None)[0]
    def residual(x):return (np.sqrt(np.sum((x+offsets[:,None,:]-refs[None,:,:2])**2,axis=2)+(height-refs[None,:,2])**2)-measured).ravel()
    def jac(x):
        d=x+offsets[:,None,:]-refs[None,:,:2]
        rho=np.sqrt(np.sum(d*d,axis=2)+(height-refs[None,:,2])**2)
        return (d/rho[:,:,None]).reshape(-1,2)
    result=least_squares(residual,start,jac=jac,loss='linear',method='trf',max_nfev=200,ftol=1e-10,xtol=1e-10,gtol=1e-10)
    if not result.success or not np.isfinite(result.x).all() or np.linalg.matrix_rank(result.jac)!=2:raise ValueError('Initializer failed')
    return result,dict(algebraic_start_xy_m=start.tolist(),solver_success=bool(result.success),nfev=int(result.nfev),cost=float(result.cost),optimality=float(result.optimality),stationarity_norm=float(np.linalg.norm(result.jac.T@result.fun)),residual_rms_m=float(np.sqrt(np.mean(result.fun**2))))

def initialize(config,events,initial_primitive,p):
    from copy import deepcopy
    config=deepcopy(config);cutoff=EPOCH+6_050_000_000;started=time.perf_counter();receipt={}
    eligible=[e for e in events if e['receive_epoch_ns']<=cutoff]
    for car in CARS:
        m=config['models'][car];keys=p['wall_nodes'];z0=np.array(initial_primitive[car])
        heading0=math.radians(2.)*z0[2]
        positions,yaw=path(eligible,car,heading0)
        ranges=[e for e in eligible if e['kind']=='uwb' and e['vehicle_id']==car and 0<=e['header_epoch_ns']-EPOCH<5*10**9]
        if len(ranges)!=100:raise ValueError('Need complete first5s wall observations')
        offsets=[positions[e['header_epoch_ns']]+rot(yaw[e['header_epoch_ns']])@np.array(m['base_to_antenna_body_xy_m']) for e in ranges]
        measured=[[e['value'][k] for k in keys] for e in ranges]
        result,detail=fit_xy(offsets,[m['anchors_xyz_m'][k] for k in keys],m['antenna_height_m'],measured)
        reference=EPOCH+6*10**9
        base6=result.x+.08*z0[:2]+positions[reference]
        ant6=base6+rot(yaw[reference])@np.array(m['base_to_antenna_body_xy_m'])
        m['start_antenna_xyz_m']=[float(ant6[0]),float(ant6[1]),m['antenna_height_m']]
        m['initial_heading_deg']=math.degrees(yaw[reference])
        receipt[car]=dict(**detail,fit_base_at_t0_xy_m=result.x.tolist(),prior_antenna_at_t6_xyz_m=m['start_antenna_xyz_m'],
            prior_yaw_at_t6_rad=yaw[reference],initial_standard_normal_primitive=z0.tolist(),
            wall_observation_ids=[e['source_observation_id'] for e in ranges],wall_observation_header_interval_s=[0,5],
            initialization_data_sha256=digest([e for e in eligible if e['vehicle_id']==car]),
            gyro_bias_used_rad_s=0.,XY_perturbation_m=(.08*z0[:2]).tolist())
    config['provenance']['initial']='first5s processed walls, measured odom/gyro motion compensation, propagated to6s, shared .08m/2deg primitives; no truth'
    return config,dict(cars=receipt,available_epoch_ns=cutoff,reference_state_epoch_ns=EPOCH+6*10**9,
        no_wall_observation_reused_in_first_graph_bin=True,elapsed_s=time.perf_counter()-started)
