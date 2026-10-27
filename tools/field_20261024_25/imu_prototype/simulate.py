"""Independent 5ms truth integration and asynchronous synthetic normalized events.

Truth/labels are written separately and are not fields in online event wrappers.
No import of the filter's motion/range functions is permitted here.
"""
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from configuration import synthetic_config
from io_utils import append, dump, external_path, gzip_writer

SCENARIOS = ('nominal', 'weak_wall', 'gyro_constant_bias', 'gyro_timevarying_bias', 'range_bias',
             'velocity_slip', 'imu_dropout', 'stationary_unobservable', 'straight_weak_observability', 'gyro_axis_mismatch')
SEEDS = (31, 47, 73)
STEP_NS = 5_000_000
DURATION_NS = 40_000_000_000


def motion(t, car, scenario):
    if scenario == 'stationary_unobservable': return np.zeros(3)
    if scenario == 'straight_weak_observability': return np.array([.12 if 4 <= t < 34 else 0., 0., 0.])
    if t < 4 or t >= 34: result = [0., 0., 0.]
    elif t < 12: result = [.16, 0., 0.]
    elif t < 20: result = [.14, .035, .18]
    elif t < 27: result = [-.10, .025, -.10]
    else: result = [.13, -.025, .06]
    value = np.array(result)
    if car == 'car2': value *= np.array([.8, -1., -.8])
    return value


def truth_step(pose, twist, dt):
    # Separately implemented analytic constant-twist integral, no online import.
    x, y, theta = pose; vx, vy, rate = twist; end = theta + rate * dt
    if abs(rate) < 1e-9:
        dx = dt * (math.cos(theta)*vx - math.sin(theta)*vy)
        dy = dt * (math.sin(theta)*vx + math.cos(theta)*vy)
    else:
        dx = ((math.sin(end)-math.sin(theta))*vx + (math.cos(end)-math.cos(theta))*vy) / rate
        dy = ((math.cos(theta)-math.cos(end))*vx + (math.sin(end)-math.sin(theta))*vy) / rate
    return np.array([x+dx, y+dy, math.atan2(math.sin(end), math.cos(end))])


def antenna_truth(pose, cc):
    arm = cc['antenna_body_xyz_m']['value']; c, s = math.cos(pose[2]), math.sin(pose[2])
    return np.array([pose[0]+c*arm[0]-s*arm[1], pose[1]+s*arm[0]+c*arm[1], cc['base_height_m']['value']+arm[2]])


def generate(scenario, seed, duration_ns=DURATION_NS):
    if scenario not in SCENARIOS: raise ValueError('unknown scenario')
    if type(duration_ns) is not int or duration_ns % 100_000_000: raise ValueError('100ms multiple duration required')
    config = synthetic_config(); origin = config['vehicles']['car1']['odom_clock']['source_origin_ns']
    config['imu_prototype']['assumption_profile_id'] = 'synthetic_engineering_imu_v1'
    if scenario == 'stationary_unobservable':
        for cc in config['vehicles'].values(): cc['antenna_body_xyz_m']['value'][:2] = [0., 0.]
    rng = np.random.default_rng(seed); count = duration_ns // STEP_NS + 1
    poses = {car: np.empty((count, 3)) for car in ('car1', 'car2')}; biases = {}
    for car in poses:
        poses[car][0] = config['vehicles'][car]['initial_room_pose']['value']
        b = np.zeros(count)
        if scenario in ('gyro_constant_bias', 'stationary_unobservable', 'straight_weak_observability'):
            b[:] = .020 if car == 'car1' else -.015
        elif scenario == 'gyro_timevarying_bias':
            # True RW stronger than assumed: intentional generator/model mismatch.
            b[0] = .010 if car == 'car1' else -.010
            for i in range(1, count): b[i] = b[i-1] + rng.normal(0., .0015 * math.sqrt(STEP_NS/1e9))
            b += .010 * np.sin(np.arange(count)*STEP_NS/1e9/6.)
        biases[car] = b
        for i in range(1, count): poses[car][i] = truth_step(poses[car][i-1], motion((i-1)*STEP_NS/1e9, car, scenario), STEP_NS/1e9)
    events = []; index = 0
    source_identity = hashlib.sha256(f'imu-synthetic-v1:{scenario}:{seed}:{duration_ns}'.encode()).hexdigest()
    def emit(kind, car, source_ns, delay_ns, **fields):
        nonlocal index
        index += 1
        row = dict(experiment_id='SYNTHETIC_'+source_identity[:12], vehicle_id=car, source_file_sha256=source_identity,
                   topic='/'+car+'/'+kind, record_index=index, header_epoch_ns=origin+source_ns,
                   receive_epoch_ns=origin+source_ns+delay_ns, **fields)
        events.append(dict(kind=kind, row=row))
    for car in poses:
        odom_pose = poses[car][0].copy(); previous_twist = None
        for t in range(0, duration_ns+1, 50_000_000):
            i = t//STEP_NS; twist = motion(t/1e9, car, scenario).copy()
            common_rate_noise = rng.normal(0., .003)
            noisy = twist + rng.normal(0., [.010, .010, .006]); noisy[2] += common_rate_noise
            if scenario == 'velocity_slip' and car == 'car1' and 10_000_000_000 <= t < 24_000_000_000:
                noisy[:2] = noisy[:2] * 1.2 + [0., .04]
            if previous_twist is not None: odom_pose = truth_step(odom_pose, previous_twist, .05)
            previous_twist = noisy.copy()
            emit('odom', car, t, 5_000_000, frame_id=car+'/odom', child_frame_id=car+'/base_footprint',
                 position_x=float(odom_pose[0]), position_y=float(odom_pose[1]), position_z=0.,
                 orientation_x=0., orientation_y=0., orientation_z=math.sin(odom_pose[2]/2), orientation_w=math.cos(odom_pose[2]/2),
                 linear_x=float(noisy[0]), linear_y=float(noisy[1]), linear_z=0., angular_x=0., angular_y=0., angular_z=float(noisy[2]))
        t = 0; j = 0
        while t <= duration_ns:
            if not (scenario == 'imu_dropout' and car == 'car1' and 14_000_000_000 <= t < 17_000_000_000):
                rate = motion(t/1e9, car, scenario)[2] + biases[car][t//STEP_NS] + rng.normal(0., .006)
                if scenario == 'gyro_axis_mismatch' and car == 'car1': rate = -rate
                emit('imu', car, t, 3_000_000 if t == 0 else (12_000_000 if car == 'car1' else 15_000_000),
                     frame_id=car+'/imu_link', angular_velocity_x=0., angular_velocity_y=0., angular_velocity_z=float(rate),
                     angular_velocity_units='rad/s', orientation_x=0., orientation_y=0., orientation_z=0., orientation_w=1.)
            t += (40_000_000, 60_000_000, 45_000_000, 55_000_000)[j % 4]; j += 1
        targets = ['node_2', 'node_3', 'node_8', 'node_10', 'node_0' if car == 'car1' else 'node_1']
        for t in range(10_000_000 if car == 'car1' else 30_000_000, duration_ns, 100_000_000):
            i = t//STEP_NS; own = antenna_truth(poses[car][i], config['vehicles'][car])
            for link, target in enumerate(targets):
                if scenario in ('weak_wall', 'straight_weak_observability') and car == 'car2' and target not in ('node_2', 'node_1'): continue
                other = 'car2' if car == 'car1' else 'car1'
                destination = antenna_truth(poses[other][i], config['vehicles'][other]) if target in ('node_0', 'node_1') else np.asarray(config['anchors_xyz_m']['value'][target])
                measured = float(np.linalg.norm(own - destination)) + rng.normal(0., .08 if target not in ('node_0','node_1') else .10)
                if scenario == 'range_bias' and car == 'car1' and target == 'node_2' and 10_000_000_000 <= t < 24_000_000_000: measured += .30
                emit('range', car, t, 12_000_000, tag_id='node_1' if car == 'car1' else 'node_0', target_id=target,
                     link_index=link, range_m=measured, valid=1, source='raw', primary_observation=1, pairing_status='unpaired')
    events.sort(key=lambda e:(e['row']['receive_epoch_ns'],e['row']['record_index'],e['row'].get('link_index',0)))
    truth = [dict(epoch_ns=origin+i*STEP_NS, vehicles={car:dict(pose=poses[car][i].tolist(), gyro_bias_rad_s=float(biases[car][i])) for car in poses}) for i in range(count)]
    labels = dict(scenario=scenario, seed=seed, injection_interval_ns=[origin+10_000_000_000, origin+24_000_000_000],
                  dropout_interval_ns=[origin+14_000_000_000, origin+17_000_000_000],
                  description='exploratory synthetic design, not an asserted field fault distribution')
    return config, events, truth, labels


def save(root, scenario, seed, duration_ns=DURATION_NS):
    root = Path(root); root.mkdir(parents=True, exist_ok=False)
    config, events, truth, labels = generate(scenario, seed, duration_ns)
    dump(root/'config.template.json', config); dump(root/'labels.json', labels)
    for name, rows in [('events.jsonl.gz', events), ('truth.jsonl.gz', truth)]:
        with gzip_writer(root/name) as stream:
            for row in rows: append(stream, row)
    return len(events)


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--scenario', choices=SCENARIOS, required=True); p.add_argument('--seed',type=int,required=True); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(save(external_path(a.output),a.scenario,a.seed))
