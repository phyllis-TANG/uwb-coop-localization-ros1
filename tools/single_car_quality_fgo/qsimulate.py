"""Paired independent truth/sensors; quality controllers never see labels."""
import copy
import hashlib
import math
from pathlib import Path
import numpy as np
from bridge import base_config
from qio import append,dump,gzip_writer

SCENARIOS=('nominal','uwb_step','uwb_ramp','gyro_drift','odom_turn_bias','common_turn_error','multi_common_uwb','weak_missing')
DEV_SEEDS=(101,151)
VALIDATION_SEEDS=(401,419,443)
ORIGIN=1_792_925_285_431_466_217
STEP_NS=5_000_000
DURATION_NS=60_000_000_000


def motion(t):
    if t<4 or t>=48:return np.zeros(3)
    if t<14:return np.array([.14,0.,0.])
    if t<26:return np.array([.12,.025,.10])
    if t<35:return np.array([-.10,.02,-.10])
    return np.array([.13,-.02,.05])


def integrate(p,v,dt):
    x,y,h=p;vx,vy,w=v;end=h+w*dt
    if abs(w)<1e-10:dx=(math.cos(h)*vx-math.sin(h)*vy)*dt;dy=(math.sin(h)*vx+math.cos(h)*vy)*dt
    else:dx=((math.sin(end)-math.sin(h))*vx+(math.cos(end)-math.cos(h))*vy)/w;dy=((math.cos(h)-math.cos(end))*vx+(math.sin(end)-math.sin(h))*vy)/w
    return np.array([x+dx,y+dy,end])


def antenna_truth(p,model):
    lx,ly=model['base_to_antenna_body_xy_m'];c,s=math.cos(p[2]),math.sin(p[2]);return np.array([p[0]+c*lx-s*ly,p[1]+s*lx+c*ly,model['antenna_height_m']])


def generate(scenario,seed,duration_ns=DURATION_NS):
    if scenario not in SCENARIOS:raise ValueError('registered scenario only')
    config=base_config.default_config('F0');config['model']['initial_heading_deg']=170.;model=config['model'];n=(duration_ns+1_000_000_000)//STEP_NS+1
    # Dedicated independent RNG streams keep cross-scenario nominal draws paired.
    streams=[np.random.default_rng(np.random.SeedSequence([seed,k])) for k in range(5)];initial,ro,ri,ru,rb=streams
    h=math.radians(170);lx,ly=model['base_to_antenna_body_xy_m'];base=np.array([2-math.cos(h)*lx+math.sin(h)*ly,2-math.sin(h)*lx-math.cos(h)*ly,h]);poses=np.empty((n,3));poses[0]=base+initial.normal(0,[.10,.10,math.radians(3.)])
    physical_bias=np.zeros(n);effective_bias=np.zeros(n)
    for i in range(1,n):poses[i]=integrate(poses[i-1],motion((i-1)*STEP_NS/1e9),STEP_NS/1e9)
    for i in range(n):
        t=i*STEP_NS/1e9
        if scenario=='gyro_drift':physical_bias[i]=.025*min(max((t-12)/10,0),1) if t<32 else .025*max(0,1-(t-32)/5)
        effective_bias[i]=physical_bias[i]+(.025 if scenario=='common_turn_error' and 12<=t<32 else 0.)
    recipe=hashlib.sha256(f'quality-fgo-v1:{scenario}:{seed}:{duration_ns}'.encode()).hexdigest();case='SYN_'+recipe[:12];events=[];index=0
    def emit(kind,t,delay,value):
        nonlocal index
        index+=1;events.append(dict(kind=kind,case_id=case,record_index=index,source_file_sha256=recipe,topic='/car2/'+kind,header_epoch_ns=ORIGIN+t,receive_epoch_ns=ORIGIN+t+delay,value=value))
    local=np.zeros(3);previous=None
    for t in range(0,duration_ns+1,50_000_000):
        rate_error=.025 if scenario in ('odom_turn_bias','common_turn_error') and 12_000_000_000<=t<32_000_000_000 else 0.
        measured=motion(t/1e9)+ro.normal(0,[.008,.008,.004]);measured[2]+=rate_error
        if previous is not None:local=integrate(local,previous,.05)
        previous=measured.copy();emit('odom',t,10_000_000,dict(pose=local.tolist(),angular_z_rad_s=float(measured[2])))
    t=0;j=0
    while t<=duration_ns:
        rate=motion(t/1e9)[2]+effective_bias[t//STEP_NS]+ri.normal(0,.006)
        emit('imu',t,20_000_000,dict(angular_velocity_rad_s=[0.,0.,float(rate)],frame_id='car2/imu_link',units='rad/s'))
        t+=(40_000_000,60_000_000,45_000_000,55_000_000)[j%4];j+=1
    for t in range(0,duration_ns+1,50_000_000):
        point=antenna_truth(poses[t//STEP_NS],model);values={}
        for key,xyz in sorted(model['anchors_xyz_m'].items()):
            noise=ru.normal(0,.08);bias=0.
            if scenario=='uwb_step' and key=='node_10' and 12_000_000_000<=t<32_000_000_000:bias=.60
            if scenario=='uwb_ramp' and key=='node_10' and 12_000_000_000<=t<32_000_000_000:bias=.60*min((t/1e9-12)/12,1.)
            if scenario=='multi_common_uwb' and 12_000_000_000<=t<32_000_000_000:bias=.30
            if scenario=='weak_missing' and 12_000_000_000<=t<32_000_000_000 and key not in ('node_2','node_3'):continue
            if scenario=='weak_missing' and 20_000_000_000<=t<24_000_000_000 and key=='node_3':continue
            values[key]=float(np.linalg.norm(point-np.asarray(xyz)))+model['range_bias_m'][key]+noise+bias
        emit('uwb',t,15_000_000,values)
    events.sort(key=lambda e:(e['receive_epoch_ns'],e['record_index']))
    truth=[dict(epoch_ns=ORIGIN+i*STEP_NS,pose=poses[i].tolist(),antenna_xyz_m=antenna_truth(poses[i],model).tolist(),bias_rad_s=float(effective_bias[i]),physical_gyro_bias_rad_s=float(physical_bias[i])) for i in range(n)]
    targets=['node_10'] if scenario in ('uwb_step','uwb_ramp') else sorted(model['anchors_xyz_m']) if scenario=='multi_common_uwb' else []
    labels=dict(scenario=scenario,seed=seed,origin_epoch_ns=ORIGIN,duration_ns=duration_ns,uwb_fault_events=[dict(event_id=f'{scenario}:{key}',target=key,start_epoch_ns=ORIGIN+12_000_000_000,end_epoch_ns=ORIGIN+32_000_000_000) for key in targets],
        cause_event=dict(kind='uwb' if targets else 'gyro' if scenario=='gyro_drift' else 'odom' if scenario=='odom_turn_bias' else 'common_angle' if scenario=='common_turn_error' else 'availability' if scenario=='weak_missing' else 'none',start_epoch_ns=ORIGIN+12_000_000_000,end_epoch_ns=ORIGIN+32_000_000_000),
        target_bias_definition='F3 target is total residual gyro error relative truth yaw rate; common-mode error is included, physical bias separately retained',not_field_failure_distribution=True)
    return config,events,truth,labels


def save(root,scenario,seed,duration_ns=DURATION_NS):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);base,events,truth,labels=generate(scenario,seed,duration_ns);dump(root/'base.template.json',base);dump(root/'labels.json',labels)
    for name,rows in [('events.jsonl.gz',events),('truth.jsonl.gz',truth)]:
        with gzip_writer(root/name) as f:
            for row in rows:append(f,row)
    return len(events)
