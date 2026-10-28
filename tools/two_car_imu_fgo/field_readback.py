#!/usr/bin/env python3
"""Raw-packet readback uses embedded-schema decoder, not rosbags or online code."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
from independent import lines,require,wrap

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/field_20261024_25'))
import bag_decoder as bag


def clean(value):
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    if isinstance(value,float) and not math.isfinite(value):return None
    return value


def stats(v):
    v=np.asarray(v,float)
    return dict(n=len(v),min=None if not len(v) else float(v.min()),median=None if not len(v) else float(np.median(v)),max=None if not len(v) else float(v.max()))


def verify(path,packet):
    path=Path(path);packet=Path(packet);manifest=json.loads((packet/'manifest.json').read_text())
    digest=hashlib.sha256(path.read_bytes()).hexdigest();require(digest==manifest['bag_sha256'],'raw bag SHA')
    conns,messages=bag.load_bag(path);rich=lines(packet/'rich_messages.jsonl.gz');events=lines(packet/'events.jsonl.gz')
    require(len(messages)==len(rich)==len(events),'all message denominator')
    decoders={};counts=Counter();streams={c:{k:[] for k in ('imu','odom','uwb')} for c in ('car1','car2')};available=None
    for index,((cid,receive,raw),r,e) in enumerate(zip(messages,rich,events)):
        available=receive if available is None else max(available,receive);conn=conns[cid]
        require(index==r['record_index']==e['record_index'],'physical record order')
        for key,want in [('topic',conn['topic']),('receive_epoch_ns',receive),('availability_epoch_ns',available),('source_file_sha256',digest),('raw_message_sha256',hashlib.sha256(raw).hexdigest())]:
            require(r[key]==e[key]==want,'raw identity '+key)
        kind=e['kind'];counts[kind]+=1
        if kind=='other':continue
        decoder=decoders.setdefault(cid,bag.Decoder(conn['type'],conn['definition']));message=decoder.decode(raw,conn['type'])
        require(clean(message)==r['message'],'full original gyro/Odom/UWB fields/quality/covariance')
        require(e['header_epoch_ns']==bag.stamp(message),'raw header changed')
        if kind=='imu':
            expected=dict(angular_velocity_rad_s=[message['angular_velocity'][k] for k in 'xyz'],frame_id=message['header']['frame_id'],units='rad/s')
            require(e['value']==expected,'gyro fields/frame/units')
        elif kind=='odom':
            q=message['pose']['pose']['orientation'];v=[q[k] for k in 'xyzw'];norm=math.sqrt(sum(x*x for x in v));x,y,z,w=[a/norm for a in v];p=message['pose']['pose']['position']
            expected=[p['x'],p['y'],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
            require(np.allclose(e['value']['pose'],expected,atol=1e-15,rtol=0),'odom pose quaternion conversion')
            require(e['value']['angular_z_rad_s']==message['twist']['twist']['angular']['z'],'odom angular preserved')
        else:
            multiplicity=Counter(x['anchor_id'] for x in message['ranges']);expected={x['anchor_id']:x['range'] for x in message['ranges'] if multiplicity[x['anchor_id']]==1}
            require(e['value']==expected,'canonical wall/peer ranges')
        streams[e['vehicle_id']][kind].append(e)
    timing={}
    for car,parts in streams.items():
        timing[car]={}
        for kind,rs in parts.items():
            h=[r['header_epoch_ns'] for r in rs];r=[r['receive_epoch_ns'] for r in rs];a=[r['availability_epoch_ns'] for r in rs]
            dh=np.diff(h);dr=np.diff(r)
            timing[car][kind]=dict(messages=len(rs),header_first_last_ns=[h[0],h[-1]],receive_first_last_ns=[r[0],r[-1]],
                header_dt_ns=stats(dh),receive_dt_ns=stats(dr),receive_minus_header_ns=stats(np.array(r)-np.array(h)),
                duplicate_header=sum(int(x==0) for x in dh),backward_header=sum(int(x<0) for x in dh),source_gaps_over_100ms=sum(int(x>10**8) for x in dh),
                receive_gaps_over_100ms=sum(int(x>10**8) for x in dr),mapped_dt_semantics='receipt differences under registered old candidate; physical sample clock not accepted')
        imu=parts['imu'];gz=[r['value']['angular_velocity_rad_s'][2] for r in imu]
        timing[car]['gyro_signal']=dict(frame_labels=sorted({r['value']['frame_id'] for r in imu}),published_units='rad/s',
            z_rate_rad_s=stats(gz),native_header_left_hold_angle_rad=sum(a['value']['angular_velocity_rad_s'][2]*(b['header_epoch_ns']-a['header_epoch_ns'])/1e9 for a,b in zip(imu,imu[1:]) if 0<b['header_epoch_ns']-a['header_epoch_ns']<=10**8),
            physical_axis_approved=False,bias_calibrated=False,shared_controller_independence_approved=False,
            covariance_semantics='fixed publisher fields only, not calibrated noise',quaternion_is_absolute_room_yaw=False)
    return dict(status='PASS',case_id=manifest['case_id'],raw_bag_sha256=digest,packets_checked=len(rich),counts=dict(counts),timing=timing,
        decoder_sha256=hashlib.sha256(Path(bag.__file__).read_bytes()).hexdigest(),online_optimizer_or_Jacobian_imported=False,
        sharing='bag-envelope traversal shared with adapter; ROS field decoding independent (rosbags producer vs embedded-schema reader)',
        strict_physical_branch='BLOCKED',conditional_model_inputs='ready only if separately frozen numeric geometry/clock/axis assumptions exist')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bag',type=Path,required=True);p.add_argument('--packets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    result=verify(a.bag,a.packets);a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':result['status'],'packets_checked':result['packets_checked']}))
