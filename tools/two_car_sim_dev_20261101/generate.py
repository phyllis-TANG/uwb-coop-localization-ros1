"""Sensor-level CPU development input. No bags; only seed7 is enabled.

Trajectory coordinates denote antenna XY, with independent declared yaw. Base
XY follows from the lever arm. This is planar rigid motion, not a nonholonomic
vehicle dynamics model. Gyro is instantaneous at its timestamp, held forward;
it never encodes the next interval's future average yaw rate.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import sys
import numpy as np
from common import CARS, DEVELOPMENT_SEED, EPOCH_NS, ROOT, digest, dump, new_output, sha, sources, write_lines

sys.path.insert(1, str(ROOT/'tools/two_car_imu_fgo'))
from configuration import default_config, validate as validate_estimator

CONDITIONS = ('nominal', 'car1_wall_14', 'car1_wall_28', 'car2_wall_14', 'car2_wall_28')


def validate(spec):
    if spec['development_only'] is not True or spec['seed'] != DEVELOPMENT_SEED:
        raise ValueError('Only exposed development seed7 is enabled; formal execution is not implemented')
    duration = spec['duration_s']
    if not isinstance(duration, int) or not 24 <= duration <= 90:
        raise ValueError('Integer duration 24..90 required')
    if spec['sample_step_ns'] != 50_000_000 or spec['motion'] not in ('static_moving', 'both_moving'):
        raise ValueError('Unsupported sampling/motion')
    if spec['fixed_car'] not in CARS or spec['initial_prior_time_s'] != 1:
        raise ValueError('Role/prior time')
    if not 0 <= spec['fault_start_s'] or spec['fault_start_s']+14 >= duration:
        raise ValueError('Need a recovery interval for the 14s development fault')
    for car in CARS:
        points = spec['trajectories'][car]
        if len(points) < 2 or points[0]['t_s'] != 0 or points[-1]['t_s'] != duration:
            raise ValueError('Trajectory must span the complete run')
        times = [p['t_s'] for p in points]
        if any(b <= a for a, b in zip(times, times[1:])):
            raise ValueError('Nonmonotone trajectory')
        for p in points:
            if len(p['antenna_xy_m']) != 2 or not np.isfinite([*p['antenna_xy_m'], p['yaw_rad'], p['t_s']]).all():
                raise ValueError('Invalid trajectory coordinate')
    n = spec['noise']
    if min(n['wall_vehicle_common_fraction'], n['wall_network_common_fraction']) < 0 or n['wall_vehicle_common_fraction']+n['wall_network_common_fraction'] > 1:
        raise ValueError('Wall variance fractions')
    for key in ('range_sigma_m', 'odom_step_xy_sigma_m', 'odom_step_yaw_sigma_rad',
                'gyro_white_sigma_rad_s', 'gyro_bias_rw_rad_s_sqrt_s', 'initial_xy_sigma_m', 'initial_yaw_sigma_deg'):
        if not math.isfinite(n[key]) or n[key] < 0:
            raise ValueError('Invalid noise scale: '+key)
    if not np.isfinite([spec['gyro_bias_rad_s'][c] for c in CARS]).all():
        raise ValueError('Invalid bias')


def rotation(yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s], [s, c]])


def design(t, car, spec):
    """Present-time analytic pose design and instantaneous yaw derivative."""
    role = spec['fixed_car'] if car == spec['fixed_car'] else next(c for c in CARS if c != spec['fixed_car'])
    if spec['motion'] == 'static_moving' and role == spec['fixed_car']:
        return np.array(spec['fixed_antenna_xy_m'], float), float(spec['fixed_yaw_rad']), 0.
    # Static/moving roles can swap without editing the moving trajectory.
    key = 'car2' if spec['motion'] == 'static_moving' else car
    points = spec['trajectories'][key]
    for a, b in zip(points, points[1:]):
        if t <= b['t_s']:
            u = min(1., max(0., (t-a['t_s'])/(b['t_s']-a['t_s'])))
            s = u*u*(3-2*u)
            xy = (1-s)*np.array(a['antenna_xy_m'])+s*np.array(b['antenna_xy_m'])
            yaw = (1-s)*a['yaw_rad']+s*b['yaw_rad']
            rate = 6*u*(1-u)/(b['t_s']-a['t_s'])*(b['yaw_rad']-a['yaw_rad'])
            return xy, float(yaw), float(rate)
    raise ValueError('Time beyond trajectory')


def pose(t, car, spec, model):
    xy, yaw, rate = design(t, car, spec)
    base = xy-rotation(yaw)@np.array(model['base_to_antenna_body_xy_m'])
    return np.r_[base, yaw], np.r_[xy, model['antenna_height_m']], rate


def make(spec, condition):
    validate(spec)
    sources()
    if condition not in CONDITIONS:
        raise ValueError('Unknown condition')
    fault_car = None if condition == 'nominal' else condition.split('_')[0]
    fault_duration = 0 if fault_car is None else int(condition.rsplit('_', 1)[1])
    if fault_car and spec['fault_start_s']+fault_duration >= spec['duration_s']:
        raise ValueError('Fault must end before the run; no silent clipping')
    # Reuse the frozen estimator model/weights/frontend; this is not field calibration.
    config = default_config()
    config['provenance'].update(scope='synthetic_development_design_not_field_calibration',
        initial='t=1 declared design plus independent seed noise; no endpoint constraints')
    geometry = copy.deepcopy(config['models'])
    rng = np.random.default_rng(spec['seed'])
    count = spec['duration_s']*20+1
    dt = .05
    n = spec['noise']
    # All draws precede fault injection; conditions share all nominal primitives.
    global_wall = rng.normal(size=count)
    data = {}
    for car in CARS:
        states = [pose(i*dt, car, spec, geometry[car]) for i in range(count)]
        states_pose = np.array([p[0] for p in states])
        antennas = np.array([p[1] for p in states])
        rates = np.array([p[2] for p in states])
        init_noise = rng.normal(size=3)
        config['models'][car]['start_antenna_xyz_m'] = [
            *(antennas[20, :2]+init_noise[:2]*n['initial_xy_sigma_m']), geometry[car]['antenna_height_m']]
        config['models'][car]['initial_heading_deg'] = math.degrees(states_pose[20, 2])+init_noise[2]*n['initial_yaw_sigma_deg']
        step_noise = rng.normal(size=(count-1, 3))*[n['odom_step_xy_sigma_m'], n['odom_step_xy_sigma_m'], n['odom_step_yaw_sigma_rad']]
        odom = np.zeros((count, 3))
        for i in range(1, count):
            before, after = states_pose[i-1], states_pose[i]
            body = rotation(-before[2])@(after[:2]-before[:2])+step_noise[i-1, :2]
            odom[i, :2] = odom[i-1, :2]+rotation(odom[i-1, 2])@body
            odom[i, 2] = odom[i-1, 2]+after[2]-before[2]+step_noise[i-1, 2]
        vehicle_wall = rng.normal(size=count)
        iid_wall = rng.normal(size=(count, 4))
        pv, pn = n['wall_vehicle_common_fraction'], n['wall_network_common_fraction']
        walls = n['range_sigma_m']*(math.sqrt(1-pv-pn)*iid_wall+math.sqrt(pv)*vehicle_wall[:, None]+math.sqrt(pn)*global_wall[:, None])
        peer = rng.normal(0, n['range_sigma_m'], count)
        bias_steps = rng.normal(0, n['gyro_bias_rw_rad_s_sqrt_s']*math.sqrt(dt), count-1)
        bias = spec['gyro_bias_rad_s'][car]+np.r_[0., np.cumsum(bias_steps)]
        gyro = rates+bias+rng.normal(0, n['gyro_white_sigma_rad_s'], count)
        data[car] = dict(pose=states_pose, antennas=antennas, odom=odom, walls=walls, peer=peer, bias=bias, gyro=gyro)
    validate_estimator(config)
    # Neither condition nor fault interval appears in the estimator-visible case id.
    case = f"synthetic_dev_seed{spec['seed']}_{spec['motion']}"
    identity = digest(dict(spec=spec, condition=condition, source_sha256=sources()))
    events = [dict(case_id=case, kind='clock', vehicle_id=None, header_epoch_ns=EPOCH_NS,
        receive_epoch_ns=EPOCH_NS, source_file_sha256=identity, source_observation_id='clock:0',
        topic='/synthetic/clock', value=dict(clock_epoch_ns=EPOCH_NS))]
    for i in range(count):
        t = i*dt
        peer_distance = float(np.linalg.norm(data['car1']['antennas'][i]-data['car2']['antennas'][i]))
        for ci, car in enumerate(CARS):
            m, d = geometry[car], data[car]
            values = {k:float(np.linalg.norm(d['antennas'][i]-np.array(m['anchors_xyz_m'][k]))+d['walls'][i, j])
                      for j, k in enumerate(sorted(m['anchors_xyz_m']))}
            active = car == fault_car and spec['fault_start_s'] <= t < spec['fault_start_s']+fault_duration
            if active:
                values = {k:v+.30 for k, v in values.items()}
            values['node_0' if car == 'car1' else 'node_1'] = peer_distance+float(d['peer'][i])
            samples = [('odom', dict(pose=d['odom'][i].tolist())), ('uwb', values),
                ('imu', dict(angular_velocity_rad_s=[0., 0., float(d['gyro'][i])], frame_id=car+'/imu_link', units='rad/s'))]
            for ki, (kind, value) in enumerate(samples):
                delay = (10+((7*i+5*(3*ci+ki)) % 31))*1_000_000
                row = dict(case_id=case, vehicle_id=car, kind=kind,
                    header_epoch_ns=EPOCH_NS+i*spec['sample_step_ns'], receive_epoch_ns=EPOCH_NS+i*spec['sample_step_ns']+delay,
                    source_file_sha256=identity, source_observation_id=f'{car}:{kind}:{i}',
                    topic=f'/{car}/{kind}', value=value, raw_message_sha256=digest(value),
                    source_identity_kind='synthetic_recipe_not_bag')
                if kind == 'uwb':
                    row['representation'] = 'bridge'
                events.append(row)
    events.sort(key=lambda e:e['receive_epoch_ns'])
    for i, e in enumerate(events):
        e['record_index'] = i
    truth = [dict(state_epoch_ns=EPOCH_NS+t*10**9, time_s=t,
        cars={car:dict(pose=data[car]['pose'][20*t].tolist(), antenna_xyz_m=data[car]['antennas'][20*t].tolist(),
                      bias_rad_s=float(data[car]['bias'][20*t])) for car in CARS}) for t in range(spec['duration_s']+1)]
    labels = dict(development_only=True, independent_validation=False, seed=spec['seed'], condition=condition,
        duration_s=spec['duration_s'], epoch_ns=EPOCH_NS,
        fault=None if fault_car is None else dict(vehicle_id=fault_car, interval_s=[spec['fault_start_s'], spec['fault_start_s']+fault_duration],
            additive_wall_bias_m=.30, peer_modified=False, assumption='controlled source fault, not natural NLOS law'),
        truth_convention='base XY/yaw; antenna XY coordinates include 3D heights',
        sample_hold='state [t,t+1), clipped at duration; timestamped sensor noise; no independent frame trials',
        noise=copy.deepcopy(n), spec_sha256=digest(spec))
    return config, events, truth, labels


def save(spec_path, condition, output):
    spec = json.loads(Path(spec_path).read_text())
    c, e, t, l = make(spec, condition)
    root = new_output(output)
    dump(root/'config.json', c)
    write_lines(root/'events.jsonl.gz', e)
    write_lines(root/'truth.jsonl.gz', t)
    dump(root/'labels.json', l)
    dump(root/'generation.json', spec)
    manifest = dict(development_only=True, files={p.name:sha(p) for p in root.iterdir()}, source_sha256=sources(),
        event_count=len(e), truth_count=len(t), estimator_inputs=['config.json', 'events.jsonl.gz'],
        truth_and_labels_are_estimator_inputs=False)
    dump(root/'manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--spec', required=True, type=Path)
    p.add_argument('--condition', choices=CONDITIONS, required=True)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(save(a.spec, a.condition, a.output)))
