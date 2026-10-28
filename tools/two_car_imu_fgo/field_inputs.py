#!/usr/bin/env python3
"""Allowlisted raw-bag rich input adapter; no estimation or endpoint fitting."""
import argparse
from collections import Counter,defaultdict
import dataclasses
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from configuration import default_config
from io_utils import ROOT,dump,external,sha,write_lines

sys.path.insert(0,str(ROOT/'tools/field_20261024_25'))
import bag_decoder

OLD={
 '015334':dict(name='TWO_CAR_C1_static_C2_auto_L_20261018_015334.bag',sha256='bb2f8cbfecf3e73cdf1b12f4c290b51d0c74215006746abba72c0b9c7a0946e6',
              initial={'car1':[1.5,4.,.17,0.],'car2':[2.,2.,.20,90.]}),
 '033248':dict(name='TWO_CAR_C2_static_C1_auto_straight_aligned_20261018_033248.bag',sha256='4e1283bbd58f9a64187a872cd9edeccaccdd5c438149d871761c6e2e11a67bbd',
              initial={'car1':[1.5,4.,.17,-90.],'car2':[2.95,3.04,.20,0.]})}


def plain(value,path='',flags=None):
    if flags is None:flags=[]
    if hasattr(value,'__msgtype__') and value.__msgtype__ in ('builtin_interfaces/msg/Time','builtin_interfaces/msg/Duration'):
        return dict(secs=int(value.sec),nsecs=int(value.nanosec))
    if dataclasses.is_dataclass(value):return {f.name:plain(getattr(value,f.name),path+'.'+f.name,flags) for f in dataclasses.fields(value) if not f.name.startswith('__')}
    if isinstance(value,(list,tuple,np.ndarray)):return [plain(x,path+'['+str(i)+']',flags) for i,x in enumerate(value)]
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not math.isfinite(value):flags.append(dict(path=path,source_nonfinite=repr(value)));return None
    return value


def yaw(message):
    q=message['pose']['pose']['orientation'];x,y,z,w=[q[k] for k in 'xyzw'];norm=math.sqrt(x*x+y*y+z*z+w*w)
    if not .5<norm<1.5:raise ValueError('Odom quaternion invalid')
    x,y,z,w=[v/norm for v in (x,y,z,w)]
    return math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))


def export(case,bag_path,output,expected):
    from rosbags.highlevel import AnyReader
    if case not in ('015334','033248','T08','T10'):raise ValueError('holdout excluded')
    bag_path=Path(bag_path)
    if sha(bag_path)!=expected:raise ValueError('bag SHA mismatch')
    output=external(output);output.mkdir(parents=True,exist_ok=False)
    # Bag envelope parser exposes physical order; typed decoding uses rosbags.
    conns,messages=bag_decoder.load_bag(bag_path)
    rich=[];events=[];counts=Counter();frames={c:set() for c in ('car1','car2')};last=None;available=None;reversals=[]
    with AnyReader([bag_path]) as reader:
        typed={c.id:c for c in reader.connections}
        for index,(connection_id,receipt,raw) in enumerate(messages):
            if last is not None and receipt<last:reversals.append(dict(record_index=index,previous_receive_epoch_ns=last,receive_epoch_ns=receipt))
            available=receipt if available is None else max(available,receipt)
            last=receipt;conn=conns[connection_id];topic=conn['topic'];parts=topic.split('/');car=parts[1] if len(parts)>1 and parts[1] in frames else None
            kind={'odom':'odom','imu':'imu','uwb/ranges':'uwb'}.get('/'.join(parts[2:]),'other') if car else 'other'
            flags=[];header=None;value=None;m=None
            if kind!='other':
                m=plain(reader.deserialize(raw,typed[connection_id].msgtype),'message',flags)
                header=int(m['header']['stamp']['secs'])*10**9+int(m['header']['stamp']['nsecs'])
                if kind=='imu':
                    value=dict(angular_velocity_rad_s=[m['angular_velocity'][k] for k in 'xyz'],frame_id=m['header']['frame_id'],units='rad/s');frames[car].add(value['frame_id'])
                elif kind=='odom':
                    p=m['pose']['pose']['position'];value=dict(pose=[p['x'],p['y'],yaw(m)],angular_z_rad_s=m['twist']['twist']['angular']['z'])
                else:
                    grouped=defaultdict(list)
                    for r in m['ranges']:grouped[r['anchor_id']].append(r['range'])
                    value={k:v[0] for k,v in grouped.items() if len(v)==1}
            identity=dict(case_id=case,vehicle_id=car,kind=kind,record_index=index,receive_epoch_ns=receipt,availability_epoch_ns=available,
                header_epoch_ns=header,source_file_sha256=expected,raw_message_sha256=hashlib.sha256(raw).hexdigest(),
                source_observation_id=f'{expected}:{index}:{connection_id}',topic=topic)
            e=dict(identity,value=value)
            if kind=='uwb':e['representation']='bridge'
            events.append(e);counts[(car or 'other')+'/'+kind]+=1
            rich.append(dict(identity,message=m,nonfinite_values=flags,connection_id=connection_id,callerid=conn['callerid'],message_type=conn['type']))
    write_lines(output/'events.jsonl.gz',events);write_lines(output/'rich_messages.jsonl.gz',rich)
    manifest=dict(case_id=case,bag_name=bag_path.name,bag_sha256=expected,records=len(events),kind_counts=dict(counts),
        imu_frames={c:sorted(v) for c,v in frames.items()},source_units='ROS angular_velocity in rad/s; fixed covariance not calibration',
        physical_clock_and_installation_approved=False,raw_order_preserved=True,receive_reversals=reversals,
        availability_policy='physical original order, monotonic prefix max(receive_ns); original receive/header unmodified; never header sort',raw_bridge_policy='only bridge canonical is fusion; raw topic retained as other clock/identity',
        files={p.name:sha(p) for p in output.iterdir()},adapter_sha256=sha(__file__),bag_envelope_parser_sha256=sha(bag_decoder.__file__))
    dump(output/'manifest.json',manifest)
    if case in OLD:
        c=default_config();c.update(scope='field',execution_level='conditional_development',case_id=case)
        for car in ('car1','car2'):
            v=OLD[case]['initial'][car];m=c['models'][car];m['start_antenna_xyz_m']=v[:3];m['initial_heading_deg']=v[3]
            m['base_to_antenna_body_xy_m']=[.08,-.06] if car=='car1' else [.12,-.08]
            if len(frames[car])!=1:raise ValueError('missing/variable per-car IMU frame')
            for name,item in c['angular'][car].items():
                item.update(source_kind='engineering_assumption',source='single_car_imu_fgo frozen F3 engineering values; no per-car/day calibration')
            c['angular'][car]['imu_frame_id'].update(value=next(iter(frames[car])),source_kind='measured',source=f'{case} {car} original observed frame label only; not a rotation calibration')
            c['angular'][car]['body_z_in_imu_frame'].update(value=[0.,0.,1.],source=f'{car} independently declared +published-Z hypothesis; physical installation unverified; not inferred from other car')
            c['clock_policy'][car]={k:dict(kind='bag_receipt_association',source='20261018 frozen old dual-car receipt-association candidate; header clocks unverified; no identity or fitted offset',
                approval='conditional_engineering_hypothesis_only',physical_uncertainty_ns=None,
                integration_dt='actual differences on common recorder receipt clock; not calibrated sensor-sampling dt') for k in ('odom','uwb','imu')}
        c['provenance']=dict(scope='conditional_development',geometry='20261018 same-day survey approximate-center lever assumes odom origin=center, unverified',
            initial='same-day notes / frozen historical placement-heading hypotheses at first keyframe, not manual endpoint fit',
            clock='per-stream bag receipt association on recorder clock; NOT physical synchronization or source sampling time validation',
            weights='unchanged F0 and single-car F3 engineering model; no P1 correction',
            strict_physical_branch='BLOCKED',physical_clock_uncertainty_ns=None,continuous_truth=None)
        dump(output/'config.json',c)
    return manifest


def old_inputs(output):
    output=external(output);output.mkdir(parents=True,exist_ok=False);entries=[]
    for case,item in OLD.items():entries.append(export(case,ROOT/'datasets/field_raw/20261018/bags'/item['name'],output/case,item['sha256']))
    dump(output/'INPUT_INDEX.json',dict(stage='B',status='EXPORTED_NOT_YET_RUN',cases=entries,source_sha256=sha(__file__)))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--old-output',type=Path,required=True);a=p.parse_args();old_inputs(a.old_output)
