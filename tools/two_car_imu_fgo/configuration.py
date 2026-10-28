"""Frozen F0 non-IMU parameters plus per-car F3 engineering provenance."""
import copy
import json
import math
from pinned import ROOT


def default_config(base=None):
    cfg=copy.deepcopy(base) if base is not None else json.loads((ROOT/'tools/two_car_fixed_lag_fgo_v1/config.json').read_text())
    angular=json.loads((ROOT/'tools/single_car_imu_fgo/config.template.json').read_text())['angular']
    cfg['angular']={}
    cfg['clock_policy']={}
    for car in ('car1','car2'):
        cfg['angular'][car]=copy.deepcopy(angular)
        cfg['angular'][car]['imu_frame_id']['value']=car+'/imu_link'
        cfg['clock_policy'][car]={k:dict(kind='shared_synthetic_header',source='exact shared generated clock',
            approval='synthetic_design',physical_uncertainty_ns=0) for k in ('odom','uwb','imu')}
    return cfg


def validate(cfg):
    ref=json.loads((ROOT/'tools/two_car_fixed_lag_fgo_v1/config.json').read_text())
    if cfg['scope'] not in ('synthetic','field'):raise ValueError('scope')
    for key in ('replay','optimizer','frontend','fixed_lag_s','peer','extensions'):
        if cfg[key]!=ref[key]:raise ValueError('Frozen non-IMU config changed: '+key)
    if cfg['scope']=='field' and cfg.get('execution_level')!='conditional_development':raise ValueError('BLOCKED unapproved field model')
    for car in ('car1','car2'):
        model=cfg['models'][car]
        for key in ('graph_parameters','range_bias_m'):
            if model[key]!=ref['models'][car][key]:raise ValueError('F0 weights/corrections changed')
        a=cfg['angular'][car];template=json.loads((ROOT/'tools/single_car_imu_fgo/config.template.json').read_text())['angular']
        for key in template:
            item=a[key]
            if item['units']!=template[key]['units'] or not item['source'] or item['frozen_before_field_run'] is not True:raise ValueError('angular units/provenance '+car+'/'+key)
            if key not in ('body_z_in_imu_frame','imu_frame_id') and item['value']!=template[key]['value']:raise ValueError('frozen F3 angular parameter')
        axis=a['body_z_in_imu_frame']['value']
        if len(axis)!=3 or not math.isclose(sum(v*v for v in axis),1.,abs_tol=1e-8):raise ValueError('unit axis')
        for key,p in cfg['clock_policy'][car].items():
            expected='shared_synthetic_header' if cfg['scope']=='synthetic' else 'bag_receipt_association'
            if p['kind']!=expected or not p['source'] or not p['approval']:raise ValueError('clock policy')
