"""Historical Car2 input packet with actual IMU fields, integer ns and old view."""
import argparse
from collections import Counter,defaultdict
import dataclasses
import gzip
import hashlib
import io
import json
import math
from pathlib import Path

import numpy as np
from meta import HERE,LEGACY,ROOT,finish,save,sha,start


def plain(value,path='',invalid=None):
    invalid=[] if invalid is None else invalid
    if hasattr(value,'__msgtype__') and value.__msgtype__ in ('builtin_interfaces/msg/Time','builtin_interfaces/msg/Duration'):
        return {'secs':int(value.sec),'nsecs':int(value.nanosec)}
    if dataclasses.is_dataclass(value):return {f.name:plain(getattr(value,f.name),path+'.'+f.name,invalid) for f in dataclasses.fields(value) if not f.name.startswith('__')}
    if isinstance(value,(list,tuple,np.ndarray)):return [plain(x,path+'['+str(i)+']',invalid) for i,x in enumerate(value)]
    if isinstance(value,np.generic):value=value.item()
    if isinstance(value,float) and not math.isfinite(value):
        invalid.append({'path':path,'source_nonfinite':repr(value)});return None
    if isinstance(value,(str,int,float,bool)) or value is None:return value
    raise TypeError('unsupported serialized value '+str(type(value)))


def legacy_view(row):
    msg=row['message'];kind=row['kind'];value=None;header=None
    if kind=='odom':
        p,q=msg['pose']['pose']['position'],msg['pose']['pose']['orientation']
        norm=math.sqrt(sum(q[k]*q[k] for k in 'xyzw'))
        if not .5<=norm<=1.5:raise ValueError('legacy odom quaternion check')
        x,y,z,w=[q[k]/norm for k in 'xyzw']
        value=[p['x'],p['y'],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))];header=row['header_relative_s']
    elif kind=='uwb':
        groups=defaultdict(list)
        for r in msg['ranges']:groups[r['anchor_id']].append(r['range'])
        value={k:v[0] for k,v in groups.items() if len(v)==1};header=row['header_relative_s']
    return {'received_s':row['receive_relative_s'],'kind':kind,'header_s':header,'value':value}


def write_case(case,output):
    from rosbags.rosbag1 import Reader
    from rosbags.highlevel import AnyReader
    path=ROOT/case['bag']
    if case['id'] not in ('004023','005135') or sha(path)!=case['sha256']:raise ValueError('historical allowlist/source hash')
    output.mkdir()
    with Reader(path) as r:
        physical=sorted((x.chunk_pos,x.offset,cid,x.time) for cid,entries in r.indexes.items() for x in entries)
    identities={}
    for index,(_,_,cid,t) in enumerate(physical):
        if (cid,t) in identities:raise ValueError('ambiguous physical record mapping')
        identities[cid,t]=index
    counts=Counter();invalid_rows=[];origin=None;digest=hashlib.sha256();legacy_digest=hashlib.sha256();timing=defaultdict(list)
    events_path=output/'events.jsonl.gz';legacy_path=output/'legacy_events.jsonl.gz'
    with events_path.open('xb') as ef,legacy_path.open('xb') as lf,gzip.GzipFile(fileobj=ef,mode='wb',filename='',mtime=0) as out,gzip.GzipFile(fileobj=lf,mode='wb',filename='',mtime=0) as old,AnyReader([path]) as reader:
        for order,(conn,receive,raw) in enumerate(reader.messages()):
            if origin is None:origin=int(receive)
            m=reader.deserialize(raw,conn.msgtype);topic=conn.topic;header=None
            if hasattr(m,'header'):header=int(m.header.stamp.sec)*10**9+int(m.header.stamp.nanosec)
            kind={'/car2/odom':'odom','/car2/imu':'imu','/car2/uwb/ranges':'uwb'}.get(topic,'other')
            if kind=='uwb' and m.tag_id!='node_0':kind='other'
            invalid=[];message=plain(m,'message',invalid) if kind!='other' else None
            row={'schema_version':1,'case_id':case['id'],'vehicle_id':'car2' if topic.startswith('/car2/') else None,
                'source_file_sha256':case['sha256'],'record_index':identities[conn.id,int(receive)],'arrival_order_index':order,
                'connection_id':conn.id,'topic':topic,'message_type':conn.msgtype,'kind':kind,
                'receive_epoch_ns':int(receive),'header_epoch_ns':header,'receive_relative_s':(int(receive)-origin)/1e9,
                'header_relative_s':None if header is None else (header-origin)/1e9,
                'raw_message_sha256':hashlib.sha256(raw).hexdigest(),'message':message,
                'nonfinite_values':invalid,'numeric_status':'invalid_preserved' if invalid else 'finite_or_nonfusion',
                'payload_policy':'full_original_fields' if kind!='other' else 'nonfusion payload omitted; original identity and clock cadence retained'}
            encoded=(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();out.write(encoded);digest.update(encoded)
            view=legacy_view(row);encoded=(json.dumps(view,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode();old.write(encoded);legacy_digest.update(encoded)
            counts[kind]+=1
            if invalid:invalid_rows.append({'record_index':row['record_index'],'kind':kind,'nonfinite_values':invalid})
            if kind in ('odom','imu','uwb'):timing[kind].append({'record_index':row['record_index'],'header_epoch_ns':header,'receive_epoch_ns':int(receive)})
    save(output/'timing_identity.json',dict(timing))
    manifest={'schema_version':1,'case_id':case['id'],'source_bag_relative_path':case['bag'],'source_bag_sha256':case['sha256'],
        'origin_bag_receive_epoch_ns':origin,'records':sum(counts.values()),'kind_counts':dict(counts),
        'raw_IMU_fields_preserved':True,'old_IMU_placeholder_is_fusion_measurement':False,
        'event_uncompressed_sha256':digest.hexdigest(),'legacy_event_uncompressed_sha256':legacy_digest.hexdigest(),
        'nonfinite_rows':invalid_rows,'source_units':{'gyro':'published rad/s; may already have MCU compensation','linear_velocity':'published m/s','time':'integer ns plus centered s'},
        'physical_axes_clock_noise_bias_approved':False,
        'time_mapping':'none, inherits old uncorrected host header/receipt policy; not a calibrated physical time relation',
        'files':[{'relative_path':p.name,'sha256':sha(p),'bytes':p.stat().st_size} for p in (events_path,legacy_path,output/'timing_identity.json')]}
    save(output/'input_manifest.json',manifest);return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run=start(args.output,'single_car_IMU_FGO_input_preparation')
    try:
        p=json.loads((HERE/'protocol.json').read_text())
        if sha(LEGACY)!=p['legacy_protocol_sha256']:raise ValueError('inherited protocol changed')
        legacy=json.loads(LEGACY.read_text());selected={c['id']:c for c in legacy['cases']}
        results=[write_case(selected[c],args.output/c) for c in p['cases']]
        save(args.output/'protocol.json',p);save(args.output/'legacy_protocol.json',legacy)
        save(args.output/'input_index.json',{'schema_version':1,'status':'DONE','cases':results,'new_IMU_FGO_runs':0,
            'A_interface':'pending frozen FGO source/protocol; packet adapts input fields only, not optimizer'})
        run['inputs']=[{'relative_path':m['source_bag_relative_path'],'sha256':m['source_bag_sha256']} for m in results]
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
