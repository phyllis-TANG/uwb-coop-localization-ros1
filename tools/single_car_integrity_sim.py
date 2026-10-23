#!/usr/bin/env python3
"""Independent synthetic sensor generation. Truth/labels never enter worker API."""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import numpy as np
from single_car_fixed_lag import initial_prior
from single_car_sequential_replay import antenna, rotation


def truth_pose(times, model, perturbation, speed=.04):
    t=np.asarray(times,dtype=float)
    start=initial_prior(model).point
    heading=start[2]+perturbation[2]
    first=np.clip(t-10,0,25)*speed
    second=np.clip(t-45,0,25)*speed
    xy=np.array([first,second]).T @ rotation(heading).T + start[:2]+perturbation[:2]
    yaw=heading+np.clip((t-35)/10,0,1)*(math.pi/2)
    return np.column_stack([xy,yaw])


def injection(scenario,t):
    window=scenario['interval_s']
    active=bool(window is not None and window[0] <= t < window[1])
    bias=0.
    if active and scenario['id'] in ('spike','positive','negative'):
        bias=scenario['amplitude_m']
    elif active and scenario['id']=='ramp':
        bias=scenario['amplitude_m']*(t-window[0])/(window[1]-window[0])
    return active,bias


def generate(protocol,scenario,seed):
    streams=[np.random.default_rng(s) for s in np.random.SeedSequence(seed).spawn(4)]
    initial_rng,odom_rng,range_rng,receipt_rng=streams
    model=protocol['model']; noise=protocol['noise']; timing=protocol['timing']
    dt=1/protocol['trajectory']['sensor_hz']
    times=np.arange(round(protocol['trajectory']['duration_s']/dt)+1)*dt
    perturb=initial_rng.normal(size=3)*[.2,.2,math.radians(5)]
    truth=truth_pose(times,model,perturb,protocol['trajectory']['speed_m_s'])
    # Ideal local odometry is integrated from true increments, then separately
    # perturbed. Initial truth pose/heading is not passed to the estimator.
    odom=np.zeros_like(truth)
    scale=float(odom_rng.normal(0,noise['odom_scale_sigma']))
    for i in range(1,len(times)):
        body=rotation(-truth[i-1,2]) @ (truth[i,:2]-truth[i-1,:2])
        odom[i,:2]=odom[i-1,:2]+rotation(odom[i-1,2]) @ (body*(1+scale)+odom_rng.normal(size=2)*noise['odom_xy_rw_sigma_m_sqrt_s']*math.sqrt(dt))
        odom[i,2]=odom[i-1,2]+truth[i,2]-truth[i-1,2]+odom_rng.normal()*noise['odom_yaw_rw_sigma_rad_sqrt_s']*math.sqrt(dt)
    anchors=sorted(model['anchors_xyz_m'])
    state=range_rng.normal(size=len(anchors))*noise['range_marginal_sigma_m']
    events=[]; labels=[]; previous_receipt={'odom':-1.,'uwb':-1.}
    for i,t in enumerate(times):
        active,bias=injection(scenario,t)
        rho=noise['mismatch_range_ar1_rho'] if active and scenario['id']=='correlated' else noise['nominal_range_ar1_rho']
        if i:
            state=rho*state+noise['range_marginal_sigma_m']*math.sqrt(1-rho*rho)*range_rng.normal(size=len(anchors))
        xy=antenna(truth[i],model['base_to_antenna_body_xy_m'])
        ranges={k:float(np.linalg.norm(np.r_[xy,model['antenna_height_m']]-model['anchors_xyz_m'][k]))+model['range_bias_m'][k]+float(state[j])+(bias if k==scenario['anchor'] else 0.) for j,k in enumerate(anchors)}
        if active and scenario['id']=='drop_one':
            del ranges[scenario['anchor']]
        if active and scenario['id']=='two_anchors':
            ranges={k:v for k,v in ranges.items() if k in scenario['remaining_anchors']}
        for kind,value,delay_range in [('odom',odom[i].tolist(),timing['odom_delay_s']),('uwb',ranges,timing['uwb_delay_s'])]:
            delay=float(receipt_rng.uniform(*delay_range))
            if kind=='uwb' and i>0 and i%timing['uwb_extra_delay_every_samples']==0:
                delay+=timing['uwb_extra_delay_s']
            receipt=max(float(t)+delay,previous_receipt[kind]+1e-6)
            previous_receipt[kind]=receipt
            events.append(dict(received_s=receipt,kind=kind,header_s=float(t),value=value))
        labels.append(dict(time_s=float(t),active=active,injected_bias_m=bias,rho=rho))
    events.sort(key=lambda e:e['received_s']) # generator schedules delivery; worker never reorders
    return events,times,truth,labels,dict(initial_perturbation=perturb.tolist(),odom_scale_error=scale)


def save_generated(target,protocol,scenario,seed):
    target=Path(target); target.mkdir(parents=True,exist_ok=False)
    events,times,poses,labels,realization=generate(protocol,scenario,seed)
    with (target/'sensors.jsonl').open('w') as stream:
        for event in events:
            stream.write(json.dumps(event,sort_keys=True,allow_nan=False)+'\n')
    with (target/'truth.csv').open('w',newline='') as stream:
        writer=csv.writer(stream); writer.writerow(['time_s','base_x_m','base_y_m','yaw_rad','antenna_x_m','antenna_y_m'])
        for t,p in zip(times,poses):
            writer.writerow([t,*p,*antenna(p,protocol['model']['base_to_antenna_body_xy_m'])])
    (target/'fault_labels.json').write_text(json.dumps(dict(scenario=scenario,seed=seed,realization=realization,samples=labels),indent=2)+'\n')
