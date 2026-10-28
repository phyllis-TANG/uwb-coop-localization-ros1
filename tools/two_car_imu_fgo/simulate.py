"""Only estimator events are exposed; gyro generated from independent design."""
import copy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from pinned import f0_sim
from configuration import default_config
from io_utils import dump,sha,write_lines,external

SCENARIOS=('nominal','gyro_constant_bias','car1_gyro_gap','peer_bias','car1_common_wall_bias')
SEEDS=(101,211)
CARS=('car1','car2')


def make_case(seed,scenario):
    if scenario not in SCENARIOS:raise ValueError('scenario')
    base,events,truth,labels=f0_sim.make_case(seed,'peer_bias' if scenario=='peer_bias' else 'nominal')
    config=default_config(base);recipe=dict(base_generator_sha256=sha(f0_sim.__file__),generator_sha256=sha(__file__),
        seed=seed,scenario=scenario,gyro_sample_step_ns=50_000_000,gyro_white_noise_sigma_rad_s=.006,
        gyro_rate_definition='independent analytic trajectory average rate over next50ms, held over that interval',
        gyro_constant_bias_rad_s={'car1':.025,'car2':-.015} if scenario=='gyro_constant_bias' else {c:0. for c in CARS},
        car1_gyro_gap_s=[24,38],range_fault_s=[24,38],peer_bias_m=1.2,common_wall_bias_m=.30)
    source=hashlib.sha256(json.dumps(recipe,sort_keys=True).encode()).hexdigest()
    case=f'synthetic_two_car_imu_{seed}_{scenario}'
    for e in events:
        e['case_id']=case
        if scenario=='car1_common_wall_bias' and e['kind']=='uwb' and e['vehicle_id']=='car1' and 24<=((e['header_epoch_ns']-f0_sim.EPOCH_NS)/1e9)<38:
            for k in base['models']['car1']['anchors_xyz_m']:e['value'][k]+=.30
    model=json.loads(f0_sim.CONFIG.read_text())['models'];rng=np.random.default_rng(seed+881_001)
    noise=rng.normal(0,.006,(1281,2))
    for i in range(1281):
        t=i*.05
        for j,c in enumerate(CARS):
            if scenario=='car1_gyro_gap' and c=='car1' and 24<=t<38:continue
            yaw0=f0_sim.true_pose(t,c,model[c])[2];yaw1=f0_sim.true_pose(t+.05,c,model[c])[2]
            rate=(yaw1-yaw0)/.05+noise[i,j]+recipe['gyro_constant_bias_rad_s'][c]
            value=dict(angular_velocity_rad_s=[0.,0.,float(rate)],frame_id=c+'/imu_link',units='rad/s')
            e=dict(case_id=case,vehicle_id=c,kind='imu',header_epoch_ns=f0_sim.EPOCH_NS+i*50_000_000,
                receive_epoch_ns=f0_sim.EPOCH_NS+i*50_000_000+(20+((7*i+3*j)%21))*1_000_000,
                source_file_sha256=source,source_observation_id=f'{c}:imu:{i}',topic='/'+c+'/imu',value=value,
                source_identity_kind='synthetic_generation_recipe_not_ROS_bag')
            e['raw_message_sha256']=hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest();events.append(e)
    events.sort(key=lambda e:e['receive_epoch_ns'])
    for i,e in enumerate(events):e['record_index']=i
    for r in truth:
        for c in CARS:r['cars'][c]['bias_rad_s']=recipe['gyro_constant_bias_rad_s'][c]
    labels.update(case_id=case,scenario=scenario,recipe=recipe)
    return config,events,truth,labels


def save(root,seed,scenario):
    root=external(root);root.mkdir(parents=True,exist_ok=False)
    c,e,t,l=make_case(seed,scenario)
    dump(root/'config.json',c);write_lines(root/'events.jsonl.gz',e);write_lines(root/'truth.jsonl.gz',t);dump(root/'labels.json',l)
    m=dict(seed=seed,scenario=scenario,files={p.name:sha(p) for p in root.iterdir()},record_count=len(e),truth_and_labels_are_estimator_inputs=False)
    dump(root/'manifest.json',m);return m
