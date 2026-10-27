"""Exact, separately validated prototype interface; no implicit sensor calibration."""
import copy
import json
import math
from pathlib import Path
import jsonschema
import numpy as np
from legacy import model, CARS

MODES = ('legacy_odom_pose', 'body_odom_rate', 'body_imu_fixed_bias', 'body_imu_bias')
IMU_MODES = MODES[2:]
UNITS = {'velocity_noise': 'm/sqrt(s)', 'heading_noise': 'rad/sqrt(s)',
         'bias_random_walk': '(rad/s)/sqrt(s)', 'gap_xy_noise': 'm/sqrt(s)',
         'gap_yaw_noise': 'rad/sqrt(s)', 'max_control_hold_ns': 'ns', 'max_control_latency_ns': 'ns'}
VEHICLE_UNITS = {'gyro_axis_body_z_in_imu_frame': 'dimensionless', 'imu_frame_id': 'frame_id',
                 'bias_initial': 'rad/s', 'bias_initial_sigma': 'rad/s'}
SCHEMA = Path(__file__).with_name('config.schema.json')


def mode_of(config):
    return config.get('imu_prototype', {}).get('motion_mode', 'legacy_odom_pose')


def known(item):
    return isinstance(item, dict) and item.get('value') is not None and item.get('status', 'provided') == 'provided'


def validate(config):
    model.validate_config(config)
    if 'imu_prototype' not in config:
        return
    jsonschema.Draft202012Validator(json.loads(SCHEMA.read_text())).validate(config['imu_prototype'])
    p = config['imu_prototype']; mode = p['motion_mode']
    if not p['enabled']:
        if mode != 'legacy_odom_pose':
            raise ValueError('disabled prototype must use the frozen legacy mode')
        return
    if mode == 'legacy_odom_pose':
        raise ValueError('legacy mode must explicitly leave the prototype disabled')
    if config['peer_source_vehicle'] != 'car1':
        raise ValueError('this prototype freezes Car1->Car2 peer updates')
    if p['frame_mode'] == 'source_odometry_motion_only':
        if p['ranges_enabled'] or p['fusion_methods'] != ['independent']:
            raise ValueError('source-frame motion-only requires ranges disabled and independent only')
    def check_item(item, units, name):
        if item['units'] != units:
            raise ValueError('incorrect units: ' + name)
        if config['scope'] == 'field' and item['source_kind'] == 'synthetic_design' and known(item):
            raise ValueError('field use requires a new explicit engineering assumption: ' + name)
    for name, units in UNITS.items():
        item = p['parameters'][name]; check_item(item, units, name)
        if known(item):
            value = item['value']
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
                raise ValueError('finite nonnegative parameter required: ' + name)
            if name.endswith('_ns') and (type(value) is not int or value <= 0):
                raise ValueError('positive integer time gate required: ' + name)
    for car in CARS:
        vehicle = p['vehicles'][car]
        for name, units in VEHICLE_UNITS.items():
            item = vehicle[name]; check_item(item, units, car + ':' + name)
            if not known(item):
                continue
            if name == 'gyro_axis_body_z_in_imu_frame':
                axis = np.asarray(item['value'], dtype=float)
                if axis.shape != (3,) or not np.isfinite(axis).all() or not math.isclose(float(axis @ axis), 1., abs_tol=1e-8):
                    raise ValueError('body Z axis must be an explicit unit vector')
            elif name == 'imu_frame_id':
                if not isinstance(item['value'], str) or not item['value']:
                    raise ValueError('explicit IMU frame ID required')
            else:
                value = item['value']
                if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                    raise ValueError('invalid bias parameter')
                if name.endswith('sigma') and value < 0:
                    raise ValueError('negative bias sigma')
        clock = vehicle['imu_clock']
        if clock['status'] == 'provided':
            if not model.clock_ready(clock) or clock['destination_clock_id'] != config['master_clock_id']:
                raise ValueError('invalid provided IMU clock')
            if config['scope'] == 'field' and clock['source_kind'] == 'synthetic_design':
                raise ValueError('synthetic IMU clock cannot silently become a field clock')
            interval = clock.get('valid_source_interval_ns')
            if interval is not None and (len(interval) != 2 or not all(type(v) is int for v in interval) or interval[0] > interval[1]):
                raise ValueError('invalid IMU clock validity interval')


def readiness(config, method):
    mode = mode_of(config)
    if mode == 'legacy_odom_pose':
        return model.readiness(config)[method]
    p = config['imu_prototype']; blocked = {car: [] for car in CARS}
    for car in CARS:
        cc = config['vehicles'][car]
        if p['frame_mode'] == 'room' and p['ranges_enabled']:
            blocked[car] += model.readiness(config)['independent'][car]
        else:
            if p['frame_mode'] == 'room' and not model.known(cc.get('initial_room_pose')):
                blocked[car].append(car + ':initial_room_pose:unknown')
            if not model.known(cc.get('initial_covariance_diagonal')):
                blocked[car].append(car + ':initial_covariance_diagonal:unknown')
            if not model.clock_ready(cc.get('odom_clock')):
                blocked[car].append(car + ':odom_clock:unknown')
        for name, item in p['parameters'].items():
            if not known(item):
                blocked[car].append('imu_prototype.parameters.' + name + ':pending')
        if mode in IMU_MODES:
            for name in ('gyro_axis_body_z_in_imu_frame', 'imu_frame_id'):
                if not known(p['vehicles'][car][name]):
                    blocked[car].append(car + ':' + name + ':pending')
            if not model.clock_ready(p['vehicles'][car]['imu_clock']):
                blocked[car].append(car + ':imu_clock:pending')
        if mode == 'body_imu_bias':
            for name in ('bias_initial', 'bias_initial_sigma'):
                if not known(p['vehicles'][car][name]):
                    blocked[car].append(car + ':' + name + ':pending')
    if method == 'joint':
        common = sorted(set(blocked['car1'] + blocked['car2']))
        blocked = {car: common.copy() for car in CARS}
    return blocked


def parameter(value, units, source_kind='engineering_assumption', source='predeclared uncalibrated engineering starting value'):
    return dict(value=value, units=units, source_kind=source_kind, source=source, frozen_before_field_run=True)


def synthetic_config():
    cfg = json.loads((Path(__file__).resolve().parents[1] / 'causal_baselines/synthetic_config.json').read_text())
    cfg.pop('validation_protocol', None)
    p = dict(schema_version=1, enabled=True, motion_mode='body_imu_bias', fusion_methods=['independent', 'joint'],
             frame_mode='room', ranges_enabled=True, assumption_profile_id='synthetic_engineering_imu_v1',
             input_correlation_assumption='body velocity/odom rate/gyro may share upstream processing; Q is engineering, not a claim of independence',
             parameters={name: parameter(value, UNITS[name]) for name, value in dict(velocity_noise=.04, heading_noise=.025,
                 bias_random_walk=.0007, gap_xy_noise=.4, gap_yaw_noise=.3, max_control_hold_ns=100000000, max_control_latency_ns=200000000).items()}, vehicles={})
    for car in CARS:
        clock = copy.deepcopy(cfg['vehicles'][car]['odom_clock'])
        clock.update(source_kind='synthetic_design', units='ns', frozen_before_field_run=True)
        p['vehicles'][car] = dict(gyro_axis_body_z_in_imu_frame=parameter([0., 0., 1.], 'dimensionless', 'synthetic_design', 'synthetic sensor aligned with body Z'),
            imu_frame_id=parameter(car + '/imu_link', 'frame_id', 'synthetic_design', 'synthetic normalized IMU frame'),
            bias_initial=parameter(0., 'rad/s'), bias_initial_sigma=parameter(.03, 'rad/s'), imu_clock=clock)
    cfg['imu_prototype'] = p
    return cfg


def with_mode(config, mode):
    cfg = copy.deepcopy(config)
    cfg['imu_prototype']['motion_mode'] = mode
    cfg['imu_prototype']['enabled'] = mode != 'legacy_odom_pose'
    return cfg
