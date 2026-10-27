"""Independent truth and sensor generator; only events go to FGO replay."""
import copy
import hashlib
import math
from pathlib import Path
import numpy as np
from configuration import default_config
from io_utils import append,dump,gzip_writer

SCENARIOS=('nominal','gyro_constant_bias','gyro_drift','weak_geometry','range_bias','velocity_slip','imu_gap','stationary_unobservable')
SEEDS=(31,47,73)
ORIGIN=1_792_925_285_431_466_217
STEP_NS=5_000_000
DURATION_NS=50_000_000_000


def motion(t,scenario):
    if scenario=='stationary_unobservable' or t<4 or t>=42: return np.zeros(3)
    if t<15: return np.array([.14,0.,0.])
    if t<25: return np.array([.12,.025,.12])
    if t<32: return np.array([-.10,.02,-.10])
    return np.array([.14,-.025,.04])


def integrate(pose,twist,dt):
    x,y,theta=pose; vx,vy,w=twist; end=theta+w*dt
    if abs(w)<1e-10:
        dx=(math.cos(theta)*vx-math.sin(theta)*vy)*dt; dy=(math.sin(theta)*vx+math.cos(theta)*vy)*dt
    else:
        dx=((math.sin(end)-math.sin(theta))*vx+(math.cos(end)-math.cos(theta))*vy)/w
        dy=((math.cos(theta)-math.cos(end))*vx+(math.sin(end)-math.sin(theta))*vy)/w
    return np.array([x+dx,y+dy,end])


def tag(pose,model):
    lx,ly=model['base_to_antenna_body_xy_m']; c,s=math.cos(pose[2]),math.sin(pose[2])
    return np.array([pose[0]+c*lx-s*ly,pose[1]+s*lx+c*ly,model['antenna_height_m']])


def generate(scenario,seed,duration_ns=DURATION_NS):
    if scenario not in SCENARIOS or type(duration_ns) is not int or duration_ns%100_000_000: raise ValueError('bounded synthetic recipe')
    cfg=default_config(); model=cfg['model']; model['initial_heading_deg']=170.
    if scenario=='stationary_unobservable': model['base_to_antenna_body_xy_m']=[0.,0.]
    theta=math.radians(model['initial_heading_deg']); lever=model['base_to_antenna_body_xy_m']; xy=np.asarray(model['start_antenna_xyz_m'][:2])-np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])@lever
    n=(duration_ns+1_000_000_000)//STEP_NS+1; rng=np.random.default_rng(seed); poses=np.empty((n,3)); poses[0]=np.array([*xy,theta])+rng.normal(0.,[.10,.10,math.radians(3.)])
    bias=np.zeros(n)
    if scenario in ('gyro_constant_bias','stationary_unobservable'): bias[:]=.025
    elif scenario=='gyro_drift':
        bias[0]=.010
        for i in range(1,n): bias[i]=bias[i-1]+rng.normal(0,.0015*math.sqrt(STEP_NS/1e9))
        bias+=.015*np.sin(np.arange(n)*STEP_NS/1e9/8.)
    for i in range(1,n): poses[i]=integrate(poses[i-1],motion((i-1)*STEP_NS/1e9,scenario),STEP_NS/1e9)
    source=hashlib.sha256(f'fgo-synthetic-v1:{scenario}:{seed}:{duration_ns}'.encode()).hexdigest(); case='SYN_'+source[:12]; events=[]; index=0
    def emit(kind,t,delay,value):
        nonlocal index
        index+=1; events.append(dict(kind=kind,case_id=case,record_index=index,source_file_sha256=source,topic='/car2/'+kind,
                                    header_epoch_ns=ORIGIN+t,receive_epoch_ns=ORIGIN+t+delay,value=value))
    local=np.zeros(3); previous=None
    for t in range(0,duration_ns+1,50_000_000):
        measured=motion(t/1e9,scenario)+rng.normal(0.,[.008,.008,.004])
        if scenario=='velocity_slip' and 15_000_000_000<=t<35_000_000_000: measured[:2]=measured[:2]*1.25+[0.,.05]
        if previous is not None: local=integrate(local,previous,.05)
        previous=measured.copy(); emit('odom',t,10_000_000,dict(pose=local.tolist(),angular_z_rad_s=float(measured[2])))
    t=0; j=0
    while t<=duration_ns:
        if not(scenario=='imu_gap' and 18_000_000_000<=t<22_000_000_000):
            rate=motion(t/1e9,scenario)[2]+bias[t//STEP_NS]+rng.normal(0.,.006)
            emit('imu',t,20_000_000,dict(angular_velocity_rad_s=[0.,0.,float(rate)],frame_id='car2/imu_link',units='rad/s'))
        t+=(40_000_000,60_000_000,45_000_000,55_000_000)[j%4]; j+=1
    for t in range(0,duration_ns+1,50_000_000):
        point=tag(poses[t//STEP_NS],model); values={}
        for key,xyz in sorted(model['anchors_xyz_m'].items()):
            if scenario=='weak_geometry' and key!='node_2': continue
            values[key]=float(np.linalg.norm(point-np.asarray(xyz)))+model['range_bias_m'][key]+rng.normal(0.,.08)
            if scenario=='range_bias' and key=='node_10' and 12_000_000_000<=t<35_000_000_000: values[key]+=.30
        emit('uwb',t,15_000_000,values)
    if scenario=='imu_gap' and duration_ns>=24_000_000_000:
        emit('imu',19_000_000_000,5_000_000_000,dict(angular_velocity_rad_s=[0.,0.,.5],frame_id='car2/imu_link',units='rad/s'))
    events.sort(key=lambda e:(e['receive_epoch_ns'],e['record_index']))
    truth=[dict(epoch_ns=ORIGIN+i*STEP_NS,pose=poses[i].tolist(),antenna_xyz_m=tag(poses[i],model).tolist(),bias_rad_s=float(bias[i])) for i in range(n)]
    labels=dict(scenario=scenario,seed=seed,range_bias_interval_s=[12,35],velocity_slip_interval_s=[15,35],imu_gap_interval_s=[18,22],
                source_identity_note='synthetic recipe identity, not a file hash; actual event file hash is recorded separately',not_a_field_fault_distribution=True)
    return cfg,events,truth,labels


def save(root,scenario,seed,duration_ns=DURATION_NS):
    root=Path(root); root.mkdir(parents=True,exist_ok=False); cfg,events,truth,labels=generate(scenario,seed,duration_ns)
    dump(root/'template.json',cfg); dump(root/'labels.json',labels)
    for name,rows in [('events.jsonl.gz',events),('truth.jsonl.gz',truth)]:
        with gzip_writer(root/name) as stream:
            for row in rows: append(stream,row)
    return len(events)
