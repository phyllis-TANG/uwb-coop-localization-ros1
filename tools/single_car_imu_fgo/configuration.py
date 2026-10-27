"""Explicit source/units for every new angular assumption; no field tuning."""
import copy
import json
import math
from pathlib import Path
import numpy as np
import jsonschema
from legacy import ROOT

ARMS=('F0','F1','F2','F3')
UNITS={'angle_noise_density_rad_sqrt_s':'rad/sqrt(s)','bias_initial_rad_s':'rad/s','bias_initial_sigma_rad_s':'rad/s',
       'bias_random_walk_rad_s_sqrt_s':'(rad/s)/sqrt(s)','max_hold_ns':'ns','body_z_in_imu_frame':'dimensionless','imu_frame_id':'frame_id'}


def parameter(value,units,source_kind='engineering_assumption',source='frozen exploratory engineering assumption; not calibrated'):
    return dict(value=value,units=units,source_kind=source_kind,source=source,frozen_before_field_run=True)


def default_config(arm='F0'):
    original=json.loads((ROOT/'docs/field_tests/single_car_fixed_lag_20261022/protocol.json').read_text())
    angular={k:parameter(v,UNITS[k]) for k,v in dict(angle_noise_density_rad_sqrt_s=math.radians(2),bias_initial_rad_s=0.,bias_initial_sigma_rad_s=.03,bias_random_walk_rad_s_sqrt_s=.0007,max_hold_ns=100_000_000,body_z_in_imu_frame=[0.,0.,1.],imu_frame_id='car2/imu_link').items()}
    angular['body_z_in_imu_frame']['source_kind']='synthetic_design'; angular['imu_frame_id']['source_kind']='synthetic_design'
    clock=parameter(dict(source_origin_ns=0,destination_origin_ns=0,rate_numerator=1,rate_denominator=1,uncertainty_ns=0),'ns','synthetic_design','generated shared clock; field must explicitly redeclare its assumption')
    return dict(schema_version=1,scope='synthetic',arm=arm,model=original['model'],replay=original['replay'],fixed_lag_s=20.,
        optimizer=original['optimizer'],frontend=original['frontend'],angular=angular,clock_maps={kind:copy.deepcopy(clock) for kind in ('odom','uwb','imu')},
        assumptions=['Odom body translation expression still depends on upstream Odom yaw; gyro/Odom correlation uncalibrated',
                     'pose/yaw initial prior is external and uncertain; no artificial endpoint factor',
                     'IMU replaces Odom yaw factor; no IMU orientation or acceleration factor',
                     'missing angular edge has no yaw factor; held-yaw prediction only, no Odom yaw fallback'])


def validate(config):
    jsonschema.Draft202012Validator(json.loads(Path(__file__).with_name('config.schema.json').read_text())).validate(config)
    if config.get('schema_version')!=1 or config.get('scope') not in ('synthetic','field') or config.get('arm','F0') not in ARMS: raise ValueError('unsupported config')
    m=config['model']; p=config['replay']; d=config['fixed_lag_s']
    if d!=20. or p['keyframe_step_s']!=1 or p['release_delay_s']!=1 or p['range_bin_half_width_s']!=.4 or p['minimum_samples_per_link']!=5: raise ValueError('first version freezes original timing and aggregation')
    if config['optimizer']['max_nfev']<1 or config['frontend']['max_sensor_samples_per_stream']<2: raise ValueError('invalid work budget')
    if set(m['anchors_xyz_m'])!=set(m['range_bias_m']): raise ValueError('P1 mapping mismatch')
    for name in UNITS:
        item=config['angular'][name]
        if set(item)!={'value','units','source_kind','source','frozen_before_field_run'}: raise ValueError('new parameter provenance keys: '+name)
        if item['units']!=UNITS[name] or not item['source'] or item['frozen_before_field_run'] is not True or item['source_kind'] not in ('engineering_assumption','measured','manufacturer_generic','synthetic_design'): raise ValueError('new parameter provenance: '+name)
        if config['scope']=='field' and item['source_kind']=='synthetic_design': raise ValueError('field requires explicit new engineering/measured assumptions: '+name)
        value=item['value']
        if name=='body_z_in_imu_frame':
            a=np.asarray(value,dtype=float)
            if a.shape!=(3,) or not np.isfinite(a).all() or not math.isclose(float(a@a),1.,abs_tol=1e-8): raise ValueError('explicit unit body-Z axis required')
        elif name=='imu_frame_id':
            if not isinstance(value,str) or not value: raise ValueError('IMU frame required')
        elif name=='max_hold_ns':
            if type(value) is not int or value<=0: raise ValueError('integer positive hold')
        elif isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or (name!='bias_initial_rad_s' and value<=0): raise ValueError('finite angular parameters required')
    for kind in ('odom','uwb','imu'):
        item=config['clock_maps'][kind]
        if item['units']!='ns' or item['frozen_before_field_run'] is not True or not item['source']: raise ValueError('clock provenance')
        if item['source_kind'] not in ('engineering_assumption','measured','manufacturer_generic','synthetic_design') or config['scope']=='field' and item['source_kind']=='synthetic_design': raise ValueError('clock assumption scope')
        v=item['value']
        if not all(type(v[k]) is int for k in ['source_origin_ns','destination_origin_ns','rate_numerator','rate_denominator','uncertainty_ns']): raise ValueError('integer clock parameters')
        if v['rate_numerator']<=0 or v['rate_denominator']<=0 or v['uncertainty_ns']<0: raise ValueError('clock rate/uncertainty')


def map_ns(header,clock):
    v=clock['value']; delta=(header-v['source_origin_ns'])*v['rate_numerator']; scaled=(abs(delta)+v['rate_denominator']//2)//v['rate_denominator']
    return v['destination_origin_ns']+(scaled if delta>=0 else -scaled)
