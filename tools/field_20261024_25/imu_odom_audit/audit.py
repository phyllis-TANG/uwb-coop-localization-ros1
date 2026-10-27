"""Read-only source/data audit before choosing an IMU fusion model.

T08 and T10 development bags only; no estimator, truth, threshold fitting,
hardware access, implicit clock calibration or holdout decoding.
"""
import argparse
import bisect
from collections import Counter
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tarfile

import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
import bag_decoder as bag

PROTOCOL=HERE/'protocol.json'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def save(path,value):
    with Path(path).open('x') as f:
        json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n')


def stats(values):
    values=np.asarray(values,dtype=float)
    values=values[np.isfinite(values)]
    if not len(values):return dict(n=0)
    return dict(n=len(values),mean=float(np.mean(values)),std=float(np.std(values)),
        minimum=float(np.min(values)),median=float(np.median(values)),maximum=float(np.max(values)))


def yaw(q):
    v=np.array([q[k] for k in ('x','y','z','w')],dtype=float)
    norm=float(np.linalg.norm(v))
    if not math.isfinite(norm) or norm<=1e-12:raise ValueError('invalid quaternion')
    x,y,z,w=v/norm
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)),norm


def nearest_pairs(odom,imu,tolerance):
    """Offline nearest-header association, NOT a causal fusion admission rule."""
    sorted_imu=sorted(imu,key=lambda r:(r['header_ns'],r['record_index']))
    times=[r['header_ns'] for r in sorted_imu];candidates=[]
    for o in odom:
        i=bisect.bisect_left(times,o['header_ns'])
        options=[j for j in (i-1,i) if 0<=j<len(times)]
        if not options:continue
        j=min(options,key=lambda j:(abs(times[j]-o['header_ns']),sorted_imu[j]['record_index']))
        delta=times[j]-o['header_ns']
        if abs(delta)<=tolerance:candidates.append((abs(delta),o['record_index'],o,sorted_imu[j]))
    # A single sample never serves as multiple independent paired observations.
    result=[];used=set()
    for _,_,o,i in sorted(candidates,key=lambda r:r[:2]):
        if i['record_index'] in used:continue
        used.add(i['record_index']);result.append((o,i))
    return sorted(result,key=lambda p:p[0]['record_index'])


def regression(x,y):
    x,y=np.asarray(x),np.asarray(y)
    if len(x)<3 or np.std(x)<1e-12 or np.std(y)<1e-12:return dict(identifiable=False,correlation=None,slope=None,intercept=None)
    slope=float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean()))
    return dict(identifiable=True,correlation=float(np.corrcoef(x,y)[0,1]),slope=slope,
        intercept=float(y.mean()-slope*x.mean()),fit_is_calibration=False,correlation_proves_independence=False)


def intervals(rows):
    stamps=[r['header_ns'] for r in rows];d=[b-a for a,b in zip(stamps,stamps[1:])]
    return dict(count=len(rows),header_delta_ns=stats(d),nonpositive_header_steps=sum(x<=0 for x in d),
        gaps_over_100ms=sum(x>100000000 for x in d),nominal_header_rate_hz=(len(stamps)-1)*1e9/(stamps[-1]-stamps[0]) if len(stamps)>1 and stamps[-1]>stamps[0] else None)


def parse_selected(path):
    connections,messages=bag.load_bag(path)
    selected={car:{kind:[] for kind in ('imu','odom','cmd_vel')} for car in ('car1','car2')}
    decoders={}
    origin=min(receive for _,receive,_ in messages)
    for index,(identity,receive,raw) in enumerate(messages):
        c=connections[identity];parts=c['topic'].split('/')
        if len(parts)!=3 or parts[1] not in selected or parts[2] not in selected[parts[1]]:continue
        decoder=decoders.setdefault(identity,bag.Decoder(c['type'],c['definition']))
        m=decoder.decode(raw,c['type']);kind=parts[2]
        row=dict(record_index=index,receive_ns=receive,header_ns=bag.stamp(m) if kind!='cmd_vel' else None,
            topic=c['topic'],callerid=c['callerid'])
        if kind=='imu':
            angle,norm=yaw(m['orientation'])
            row.update(yaw=angle,quaternion_norm=norm,**{key:m[key] for key in ('orientation','angular_velocity','linear_acceleration','orientation_covariance','angular_velocity_covariance','linear_acceleration_covariance')})
            row['frame_id']=m['header']['frame_id']
        elif kind=='odom':
            angle,norm=yaw(m['pose']['pose']['orientation'])
            row.update(yaw=angle,quaternion_norm=norm,position=m['pose']['pose']['position'],
                velocity=m['twist']['twist']['linear'],angular_velocity=m['twist']['twist']['angular'],
                frame_id=m['header']['frame_id'],child_frame_id=m['child_frame_id'])
        else:row.update(linear=m['linear'],angular=m['angular'])
        selected[parts[1]][kind].append(row)
    return selected,origin,dict(bag_message_count=len(messages),selected_topics={c['topic']:dict(type=c['type'],md5sum=c['md5sum'],callerid=c['callerid']) for c in connections.values() if c['topic'] in {r['topic'] for v in selected.values() for rows in v.values() for r in rows}})


def relation(odom,imu,tolerance):
    pairs=nearest_pairs(odom,imu,tolerance)
    ow=[o['angular_velocity']['z'] for o,i in pairs];gz=[i['angular_velocity']['z'] for o,i in pairs]
    differences=np.array(gz)-np.array(ow)
    result=dict(paired_rows=len(pairs),nearest_pairing_offline_only=True,
        imu_minus_odom_header_ns=stats([i['header_ns']-o['header_ns'] for o,i in pairs]),
        gyro_z_minus_odom_angular_z=stats(differences),gyro_z_on_odom_rate=regression(ow,gz),
        rate_equality_fraction=float(np.mean(np.abs(differences)<1e-9)) if pairs else None,
        physical_clock_offset_estimated=False,source_independence_confirmed=False)
    residuals=[];accepted=0;oyaw=0.;gyaw=0.
    for a,b in zip(odom,odom[1:]):
        dt=(b['header_ns']-a['header_ns'])/1e9
        if not 0<dt<=.1:continue
        delta=math.atan2(math.sin(b['yaw']-a['yaw']),math.cos(b['yaw']-a['yaw']))
        residuals.append(delta-b['angular_velocity']['z']*dt);oyaw+=delta;accepted+=1
    for a,b in zip(imu,imu[1:]):
        dt=(b['header_ns']-a['header_ns'])/1e9
        if 0<dt<=.1:gyaw+=.5*(a['angular_velocity']['z']+b['angular_velocity']['z'])*dt
    result.update(odom_yaw_increment_minus_current_rate_dt_rad=stats(residuals),accepted_odom_intervals=accepted,
        odom_accepted_increment_sum_rad=oyaw,gyro_trapezoid_sum_rad=gyaw,
        integral_comparison_is_ground_truth=False)
    return result,pairs


def vehicle_metrics(v,origin,p):
    imu,odom,commands=v['imu'],v['odom'],v['cmd_vel']
    if not imu or not odom:raise ValueError('missing required IMU/odom stream')
    quiet=[r for r in imu if origin<=r['receive_ns']<origin+p['quiet_candidate_duration_ns']]
    active=[r for r in commands if origin<=r['receive_ns']<origin+p['quiet_candidate_duration_ns']
            and any(abs(r[group][axis])>1e-9 for group in ('linear','angular') for axis in ('x','y','z'))]
    if active:quiet=[]
    relation_metrics,pairs=relation(odom,imu,p['nearest_header_tolerance_ns'])
    result=dict(imu_timing=intervals(imu),odom_timing=intervals(odom),
        imu_frames=sorted({r['frame_id'] for r in imu}),odom_frames=sorted({r['frame_id'] for r in odom}),
        odom_children=sorted({r['child_frame_id'] for r in odom}),
        quaternion_norm=stats([r['quaternion_norm'] for r in imu]),
        acceleration_norm_m_s2=stats([np.linalg.norm([r['linear_acceleration'][a] for a in ('x','y','z')]) for r in imu]),
        gyro_z_rad_s=stats([r['angular_velocity']['z'] for r in imu]),
        covariance_values={name:dict(Counter(json.dumps(r[name]) for r in imu)) for name in ('orientation_covariance','angular_velocity_covariance','linear_acceleration_covariance')},
        quiet_candidate=dict(scope='first recorder-domain 5s without recorded nonzero command; NOT independent proof of physical rest',
            accepted=len(quiet)>0,gyro_z=stats([r['angular_velocity']['z'] for r in quiet]),noise_calibration_accepted=False,bias_applied_to_any_estimator=False),
        relation=relation_metrics)
    return result,pairs


def source_audit(archive,output):
    with tarfile.open(archive,'r:gz') as t:
        members=[m for m in t.getmembers() if m.isfile()]
        named=next(m for m in members if m.name.endswith('/car2_base_source.tar.gz'))
        raw=t.extractfile(named).read()
        if hashlib.sha256(raw).hexdigest()!='1075a2dc3cb47bd260a9de34199e484e8256898eeb26f14b07ae65240c47f211':raise ValueError('car2 source archive mismatch')
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as child:
            selected={n:child.extractfile(n).read() for n in ('src/wheeltec_robot.cpp','src/Quaternion_Solution.cpp','include/wheeltec_robot.h')}
    cpp=selected['src/wheeltec_robot.cpp'].decode();quat=selected['src/Quaternion_Solution.cpp'].decode()
    required=['Robot_Pos.Z+=Robot_Vel.Z * Sampling_Time','Robot_Vel.Z = Odom_Trans(Receive_Data.rx[6],Receive_Data.rx[7])',
              'Mpu6050_Data.gyros_z_data = IMU_Trans(Receive_Data.rx[18],Receive_Data.rx[19])','odom_quat = tf::createQuaternionMsgFromYaw(Robot_Pos.Z)']
    if not all(x in cpp for x in required):raise ValueError('source paths changed; manual audit needed')
    evidence=dict(car2_archive_sha256=hashlib.sha256(raw).hexdigest(),files={n:hashlib.sha256(v).hexdigest() for n,v in selected.items()},
        findings=dict(host_odom_heading='integral of serial Robot_Vel.Z; separate packet field from gyro_z',
            host_imu_orientation='gyro+accelerometer attitude; fixed 20Hz timestep; integral feedback gain zero',
            upstream_board_fusion='UNKNOWN: MCU firmware not present; different fields do not prove statistical independence',
            car1_host_source='NOT_IN_REGISTERED_ARCHIVE',deployed_binary_source_binding='UNKNOWN for both vehicles',
            gravity_removal='not performed in archived host publisher',covariance='hardcoded placeholders; no calibration accepted',
            fast_inverse_sqrt='uses long pointer reinterpretation; target-width and aliasing portability risk requires deployed-source/compiler/sizeof evidence; not diagnosed as a field failure'))
    snippets={}
    selections={'src/wheeltec_robot.cpp':[(258,280),(287,304),(596,622),(663,696)],'src/Quaternion_Solution.cpp':[(1,27),(70,102)],'include/wheeltec_robot.h':[(64,74)]}
    for name,windows in selections.items():
        lines=selected[name].decode().splitlines();snippets[name]=[dict(line=i,text=lines[i-1]) for lo,hi in windows for i in range(lo,min(hi,len(lines))+1)]
    evidence['line_excerpts']=snippets
    save(output/'source_audit.json',evidence)
    return evidence


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv);protocol=json.loads(PROTOCOL.read_text())
    if sha(args.archive)!=protocol['archive_sha256']:raise ValueError('registered archive mismatch')
    if args.output.resolve().is_relative_to(ROOT):raise ValueError('results outside Git only')
    args.output.mkdir(parents=True,exist_ok=False);inputs=args.output/'selected_inputs';inputs.mkdir()
    source=source_audit(args.archive,args.output)
    manifest=json.loads((ROOT/'docs/field_tests/20261024_25/manifest.json').read_text())
    result=dict(scope='source/data readiness audit only; no IMU fusion implemented',base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={str(f.relative_to(ROOT)):sha(f) for f in list(HERE.glob('*.py'))+[PROTOCOL,Path(bag.__file__)]},
        protocol=protocol,archive_sha256=sha(args.archive),source_findings=source['findings'],experiments={},field_accuracy_evaluated=False)
    with tarfile.open(args.archive,'r:gz') as t,gzip.open(args.output/'pair_observations.csv.gz','xt') as pairfile:
        columns=['experiment','vehicle','odom_record','imu_record','odom_header_ns','imu_header_ns','odom_rate_z','gyro_z','odom_yaw','imu_yaw']
        writer=csv.writer(pairfile);writer.writerow(columns)
        for experiment in protocol['experiments']:
            if experiment not in ('T08','T10'):raise ValueError('development-only audit: holdout refused')
            item=next(r for r in manifest['formal_bags'] if r['id']==experiment)
            if item['split']!='development':raise ValueError('holdout refused')
            name=Path(item['relative_path']).name
            member=next(m for m in t.getmembers() if m.isfile() and m.name.endswith('/'+name))
            data=t.extractfile(member).read()
            if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('bag hash mismatch')
            path=inputs/name;path.write_bytes(data)
            vehicles,origin,inventory=parse_selected(path);result['experiments'][experiment]=dict(input_sha256=item['sha256'],origin_receive_ns=origin,inventory=inventory,vehicles={})
            for car,streams in vehicles.items():
                metrics,pairs=vehicle_metrics(streams,origin,protocol);result['experiments'][experiment]['vehicles'][car]=metrics
                for o,i in pairs:writer.writerow([experiment,car,o['record_index'],i['record_index'],o['header_ns'],i['header_ns'],o['angular_velocity']['z'],i['angular_velocity']['z'],o['yaw'],i['yaw']])
            print(experiment,'SOURCE_AND_STREAMS_AUDITED',flush=True)
    result['output_sha256']={str(f.relative_to(args.output)):sha(f) for f in args.output.rglob('*') if f.is_file()}
    save(args.output/'audit.json',result)


if __name__=='__main__':main()
