"""Additional existing-file consistency tests; no hardware or localization.

These tests describe reported signal relationships, not firmware identification,
independent angle truth, clock calibration or an independence guarantee.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import sys

import numpy as np
import audit


HISTORICAL=(
    'TWO_CAR_C2_static_C1_keyboard_return_20261018_025148.bag',
    'TWO_CAR_both_motion_20261018_045116.bag',
)


def rms(values):
    values=np.asarray(values,dtype=float)
    return float(np.sqrt(np.mean(values**2))) if len(values) else None


def reported_relationship(streams):
    pairs=audit.nearest_pairs(streams['odom'],streams['imu'],2000000)
    if not pairs:raise ValueError('no same-host diagnostic pairs')
    odom_yaw=np.unwrap([o['yaw'] for o,i in pairs]);imu_yaw=np.unwrap([i['yaw'] for o,i in pairs])
    relative_difference=(imu_yaw-imu_yaw[0])-(odom_yaw-odom_yaw[0])
    yaw_residual=[];xy_residual=[];gyro_euler_residual=[];eligible=0
    for (a,ia),(b,ib) in zip(pairs,pairs[1:]):
        dt=(b['header_ns']-a['header_ns'])/1e9;idt=(ib['header_ns']-ia['header_ns'])/1e9
        if not (0<dt<=.1 and 0<idt<=.1):continue
        dyaw=math.atan2(math.sin(b['yaw']-a['yaw']),math.cos(b['yaw']-a['yaw']))
        yaw_residual.append(dyaw-b['angular_velocity']['z']*dt)
        gyro_euler_residual.append(dyaw-ib['angular_velocity']['z']*idt)
        vx,vy=b['velocity']['x'],b['velocity']['y'];c,s=math.cos(a['yaw']),math.sin(a['yaw'])
        expected=np.array([c*vx-s*vy,s*vx+c*vy])*dt
        actual=np.array([b['position']['x']-a['position']['x'],b['position']['y']-a['position']['y']])
        xy_residual.append(float(np.linalg.norm(actual-expected)));eligible+=1
    rate_difference=[i['angular_velocity']['z']-o['angular_velocity']['z'] for o,i in pairs]
    return dict(paired_rows=len(pairs),eligible_adjacent_intervals=eligible,
        relative_published_IMU_minus_odom_yaw_rad=audit.stats(relative_difference),
        rate_difference_rad_s=audit.stats(rate_difference),
        odom_yaw_current_reported_rate_step_residual_rad=dict(rms=rms(yaw_residual),stats=audit.stats(yaw_residual)),
        odom_xy_current_body_velocity_step_residual_m=dict(rms=rms(xy_residual),stats=audit.stats(xy_residual)),
        odom_yaw_raw_IMU_current_rate_step_residual_rad=dict(rms=rms(gyro_euler_residual),stats=audit.stats(gyro_euler_residual)),
        odom_heading_net_change_rad=float(odom_yaw[-1]-odom_yaw[0]),
        IMU_heading_net_change_rad=float(imu_yaw[-1]-imu_yaw[0]),
        firmware_identified=False,independent_sensors_proven=False,actual_attitude_error_evaluated=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous-selection',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    with (audit.ROOT/'datasets/field_raw/catalog.csv').open() as f:catalog=list(csv.DictReader(f))
    selected=[]
    for name in HISTORICAL:
        item=next(r for r in catalog if r['filename']==name)
        path=audit.ROOT/'datasets/field_raw'/item['archive_path']
        if audit.sha(path)!=item['sha256']:raise ValueError('historical catalog SHA mismatch')
        selected.append((name,path,item['sha256'],'historical source-diagnostic example; no localization evaluation'))
    manifest=json.loads((audit.ROOT/'docs/field_tests/20261024_25/manifest.json').read_text())
    for name in ('T08','T10'):
        item=next(r for r in manifest['formal_bags'] if r['id']==name)
        if item['split']!='development':raise ValueError('holdout forbidden')
        path=args.previous_selection/Path(item['relative_path']).name
        if audit.sha(path)!=item['sha256']:raise ValueError('selected development SHA mismatch')
        selected.append((name,path,item['sha256'],'development source diagnostic'))
    result=dict(scope='passive reported-signal consistency only; no firmware/accuracy claim',
        execution_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=audit.ROOT,text=True).strip(),
        source_sha256=audit.sha(Path(__file__)),base_audit_source_sha256=audit.sha(Path(audit.__file__)),inputs={})
    for name,path,sha,scope in selected:
        streams,origin,inventory=audit.parse_selected(path)
        result['inputs'][name]=dict(sha256=sha,scope=scope,inventory=inventory,vehicles={})
        for car,v in streams.items():result['inputs'][name]['vehicles'][car]=reported_relationship(v)
    audit.save(args.output,result)
    print(json.dumps(dict(status='DONE',inputs=len(selected),vehicles_checked=sum(len(r['vehicles']) for r in result['inputs'].values()))))


if __name__=='__main__':main()
