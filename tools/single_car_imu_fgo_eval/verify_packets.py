"""Independent raw-bag and rich-packet readback. No optimizer/Jacobian imports."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

from meta import LEGACY,ROOT,finish,save,sha,start
sys.path.insert(0,str(ROOT/'tools/field_20261024_25'))
import bag_decoder as rawbag


def equal_raw(actual,expected,path='message'):
    if isinstance(expected,dict):
        if not isinstance(actual,dict) or set(actual)!=set(expected):raise ValueError('raw object shape '+path)
        for key,value in expected.items():equal_raw(actual[key],value,path+'.'+key)
    elif isinstance(expected,list):
        if not isinstance(actual,list) or len(actual)!=len(expected):raise ValueError('raw array shape '+path)
        for i,value in enumerate(expected):equal_raw(actual[i],value,path+'['+str(i)+']')
    elif isinstance(expected,float) and not math.isfinite(expected):
        if actual is not None:raise ValueError('nonfinite source was replaced by numeric value '+path)
    elif isinstance(expected,int):
        if type(actual) is not type(expected) or actual!=expected:raise ValueError('integer/bool changed '+path)
    elif actual!=expected:raise ValueError('raw field changed '+path)


def independent_old_view(row,raw):
    kind=row['kind'];value=None;header=None
    if kind=='odom':
        p=raw['pose']['pose']['position'];q=raw['pose']['pose']['orientation'];norm=math.sqrt(sum(q[k]**2 for k in 'xyzw'))
        x,y,z,w=(q[k]/norm for k in 'xyzw')
        value=[p['x'],p['y'],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))];header=row['header_relative_s']
    elif kind=='uwb':
        groups=defaultdict(list)
        for entry in raw['ranges']:groups[entry['anchor_id']].append(entry['range'])
        value={k:v[0] for k,v in groups.items() if len(v)==1};header=row['header_relative_s']
    return {'received_s':row['receive_relative_s'],'kind':kind,'header_s':header,'value':value}


def verify_case(directory,case):
    manifest=json.loads((directory/'input_manifest.json').read_text());bag=ROOT/case['bag']
    if case['id'] not in ('004023','005135') or sha(bag)!=case['sha256'] or manifest['source_bag_sha256']!=case['sha256']:raise ValueError('raw allowlist/hash mismatch')
    for item in manifest['files']:
        rel=Path(item['relative_path'])
        if rel.is_absolute() or '..' in rel.parts or sha(directory/rel)!=item['sha256']:raise ValueError('packet changed')
    connections,messages=rawbag.load_bag(bag);seen=set();decoders={};counts=defaultdict(int);previous=-1;stream_digest=hashlib.sha256();old_digest=hashlib.sha256()
    origin=manifest['origin_bag_receive_epoch_ns']
    with gzip.open(directory/'events.jsonl.gz','rt') as events,gzip.open(directory/'legacy_events.jsonl.gz','rt') as legacy:
        for order,(line,oldline) in enumerate(itertools.zip_longest(events,legacy)):
            if line is None or oldline is None:raise ValueError('rich/old stream length mismatch')
            stream_digest.update(line.encode());old_digest.update(oldline.encode());r=json.loads(line);old=json.loads(oldline)
            if r['case_id']!=case['id'] or r['source_file_sha256']!=case['sha256']:raise ValueError('case/source mix')
            for key in ('record_index','arrival_order_index','receive_epoch_ns'):
                if type(r[key]) is not int:raise ValueError('float/bool record or epoch')
            index=r['record_index']
            if index in seen or not 0<=index<len(messages):raise ValueError('duplicate/absent physical record')
            seen.add(index);identity,receive,payload=messages[index];c=connections[identity]
            if r['receive_epoch_ns']!=receive or r['topic']!=c['topic'] or r['connection_id']!=identity:raise ValueError('physical identity changed')
            if r['arrival_order_index']!=order or receive<previous:raise ValueError('receive stream order changed')
            previous=receive
            if r['raw_message_sha256']!=hashlib.sha256(payload).hexdigest():raise ValueError('raw payload identity')
            if r['receive_relative_s']!=(receive-origin)/1e9:raise ValueError('float epoch conversion or wrong origin')
            decoder=decoders.setdefault(identity,rawbag.Decoder(c['type'],c['definition']));m=decoder.decode(payload,c['type'])
            header=rawbag.stamp(m) if 'header' in m else None
            if r['header_epoch_ns']!=header or header is not None and type(r['header_epoch_ns']) is not int:raise ValueError('header integer identity')
            if r['header_relative_s']!=(None if header is None else (header-origin)/1e9):raise ValueError('centered header time changed')
            expected_kind={'/car2/odom':'odom','/car2/imu':'imu','/car2/uwb/ranges':'uwb'}.get(c['topic'],'other')
            if expected_kind=='uwb' and m['tag_id']!='node_0':expected_kind='other'
            if r['kind']!=expected_kind:raise ValueError('wrong measurement kind')
            if r['kind']!='other':equal_raw(r['message'],m)
            if r['kind']=='uwb' and all(math.isfinite(entry['range']) for entry in m['ranges']):
                if r.get('measurement_numeric_status')!='required_values_finite':raise ValueError('unknown quality incorrectly invalidated finite ranges')
            if old!=independent_old_view(r,m):raise ValueError('old input view differs')
            if r['kind']=='imu' and ('angular_velocity' not in r['message'] or 'orientation_covariance' not in r['message']):raise ValueError('placeholder IMU instead of actual fields')
            counts[r['kind']]+=1
    if len(seen)!=len(messages) or dict(counts)!=manifest['kind_counts']:raise ValueError('records omitted')
    if stream_digest.hexdigest()!=manifest['event_uncompressed_sha256'] or old_digest.hexdigest()!=manifest['legacy_event_uncompressed_sha256']:raise ValueError('uncompressed stream identity')
    return {'case_id':case['id'],'all_records_verified':len(seen),'kind_counts':dict(counts),'raw_decoder':'existing field_20261024_25/bag_decoder.py, separate from exporter rosbags',
            'all_motion_and_UWB_fields_covariances_and_integer_identities':True,'old_placeholder_view_preserved_but_not_used_as_IMU':True,
            'online_optimizer_or_jacobian_imported':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'single_car_IMU_FGO_independent_raw_packet_readback')
    try:
        cases={c['id']:c for c in json.loads(LEGACY.read_text())['cases']}
        checks=[verify_case(args.packets/c,cases[c]) for c in ('004023','005135')]
        save(args.output/'verification.json',{'status':'DONE','all_passed':True,'checks':checks,'shared_code':'IO/hash only; rosbags exporter vs independent field bag decoder and own old-view formulas','field_accuracy_evaluated':False})
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
