"""One explicit engineering consistency policy; frozen F0/F3 baselines."""
import copy
import math
import json
from pathlib import Path
import jsonschema
from bridge import base_config

GROUPS={'Q0':'F0','Q1':'F3','Q2':'F0','Q3':'F3'}
VALUES=dict(score_scale_m=.20,warn_score=1.5,disable_score=3.,clear_score=.75,warn_count=2,disable_count=2,clear_count=3,recover_count=3,
            lowered_information=.10,recovery_information=.25,min_other_links=3,min_xy_singular_ratio=.15)


def default(group='Q0'):
    units={k:'dimensionless' for k in VALUES};units['score_scale_m']='m'
    for k in ['warn_count','disable_count','clear_count','recover_count','min_other_links']:units[k]='count'
    return dict(schema_version=1,interface_version='quality_fgo_v1',group=group,quality_enabled=group in ('Q2','Q3'),
        base=base_config.default_config(GROUPS[group]),controller={k:base_config.parameter(v,units[k]) for k,v in VALUES.items()},
        reference='independent-from-initialization same F0/F3 skeleton, one excluded wall per shadow, all remaining factors original pseudo-Huber only',
        timing=dict(paced=False,scope='development_accelerated; validation uses measured paced output availability'),
        assumptions=['no independent ground truth or calibrated prediction covariance in shadow','engineering score, not NIS/PL/integrity guarantee',
                     'same upstream Odom/gyro and correlated wall failures can fool shadows','unknown holds last information multiplier; initial unknown keeps baseline1, not a healthy claim',
                     'new multiplier frozen once at factor creation; no history rollback or bias locking'])


def values(config):return {k:v['value'] for k,v in config['controller'].items()}


def validate(config):
    try:jsonschema.Draft202012Validator(json.loads(Path(__file__).with_name('config.schema.json').read_text())).validate(config)
    except jsonschema.ValidationError as error:raise ValueError('quality config schema: '+error.message) from error
    if config.get('interface_version')!='quality_fgo_v1' or config.get('schema_version')!=1 or config.get('group') not in GROUPS:raise ValueError('quality interface/group')
    if config['base'].get('arm','F0')!=GROUPS[config['group']]:raise ValueError('Q0/Q2 must F0; Q1/Q3 must F3')
    if type(config['quality_enabled']) is not bool or config['group'] in ('Q0','Q1') and config['quality_enabled']:raise ValueError('baseline quality disabled')
    base_config.validate(config['base']);v=values(config)
    if set(v)!=set(VALUES):raise ValueError('exact controller keys required')
    for key,item in config['controller'].items():
        expected_unit='m' if key=='score_scale_m' else 'count' if key in ('warn_count','disable_count','clear_count','recover_count','min_other_links') else 'dimensionless'
        if item['units']!=expected_unit:raise ValueError('controller units: '+key)
        if set(item)!={'value','units','source_kind','source','frozen_before_field_run'} or item['source_kind']!='engineering_assumption' or not item['source'] or item['frozen_before_field_run'] is not True:raise ValueError('controller provenance: '+key)
        if type(item['value']) not in (int,float) or not math.isfinite(item['value']):raise ValueError('finite controller parameter')
    if not 0<v['clear_score']<v['warn_score']<v['disable_score'] or v['score_scale_m']<=0:raise ValueError('score hysteresis ordering')
    if not 0<v['lowered_information']<v['recovery_information']<1:raise ValueError('information multiplier bounds')
    for k in ['warn_count','disable_count','clear_count','recover_count','min_other_links']:
        if type(v[k]) is not int or v[k]<1:raise ValueError('integer persistence/geometry')
    if not 0<v['min_xy_singular_ratio']<=1:raise ValueError('geometry condition ratio')
    if type(config['timing']['paced']) is not bool:raise ValueError('timing mode')
