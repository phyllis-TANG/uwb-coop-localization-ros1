"""Third-party ROS1 decoding crosscheck of selected IMU/Odom fields and identities.

Uses rosbags' index/chunk parser and ROS type deserializer, not PR45 bag_decoder,
normalize.convert, A's online kernel, Jacobian or evaluator. Decodes only T08/T10
motion topics. Original record_index is reconstructed from chunk/byte positions.
"""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'imu_field_prep'))
from provenance import finish,save,sha,start


def same_number(original,text,field,nonfinite_fields):
    value=float(original)
    if not math.isfinite(value):
        if text!='' or field not in nonfinite_fields:raise ValueError('nonfinite source provenance concealed: '+field)
    elif text=='' or float(text)!=value:
        raise ValueError('raw numeric mismatch: '+field)


def flat_motion(m,kind):
    result={}
    if kind=='odom':
        vectors={'position':m.pose.pose.position,'orientation':m.pose.pose.orientation,'linear':m.twist.twist.linear,'angular':m.twist.twist.angular}
        arrays={'pose_covariance':m.pose.covariance,'twist_covariance':m.twist.covariance}
    else:
        vectors={k:getattr(m,k) for k in ('orientation','angular_velocity','linear_acceleration')}
        arrays={k:getattr(m,k) for k in ('orientation_covariance','angular_velocity_covariance','linear_acceleration_covariance')}
    for name,v in vectors.items():
        for axis in ('xyzw' if name=='orientation' else 'xyz'):result[name+'_'+axis]=float(getattr(v,axis))
    for name,values in arrays.items():result[name]=[float(x) for x in values]
    return result


def verify_trial(packet,bag_path,writer):
    from rosbags.rosbag1 import Reader
    from rosbags.typesys import get_typestore,Stores
    manifest=json.loads((packet/'input_manifest.json').read_text());trial=manifest['experiment_id']
    if trial not in ('T08','T10') or sha(bag_path)!=manifest['source_file_sha256']:raise ValueError('selected bag allowlist/hash')
    expected={}
    for kind in ('odom','imu'):
        with (packet/'normalized'/(kind+'.csv')).open() as f:
            for row in csv.DictReader(f):
                index=int(row['record_index'])
                if index in expected:raise ValueError('record index is not unique')
                expected[index]=(kind,row)
    store=get_typestore(Stores.ROS1_NOETIC);verified=0;scalars=0;by_stream={}
    with Reader(bag_path) as reader:
        physical=sorted((x.chunk_pos,x.offset,cid,x.time) for cid,entries in reader.indexes.items() for x in entries)
        identities={}
        for index,(_,_,cid,t) in enumerate(physical):
            if (cid,t) in identities:raise ValueError('ambiguous connection/receive identity; no guessed record mapping')
            identities[cid,t]=index
        for conn,receive,raw in reader.messages():
            index=identities[conn.id,receive]
            if index not in expected:continue
            kind,row=expected.pop(index)
            if row['topic']!=conn.topic or int(row['receive_epoch_ns'])!=receive:raise ValueError('original record identity differs')
            m=store.deserialize_ros1(raw,conn.msgtype)
            header=int(m.header.stamp.sec)*10**9+int(m.header.stamp.nanosec)
            if header!=int(row['header_epoch_ns']) or m.header.frame_id!=row['frame_id'] or int(m.header.seq)!=int(row['header_seq']):raise ValueError('raw header/seq/frame changed')
            if kind=='odom' and m.child_frame_id!=row['child_frame_id']:raise ValueError('base frame changed')
            nonfinite=json.loads(row.get('nonfinite_fields') or '[]')
            values=flat_motion(m,kind)
            for key,value in values.items():
                if isinstance(value,list):
                    recorded=json.loads(row[key])
                    if len(value)!=len(recorded):raise ValueError('covariance shape changed')
                    for x,y in zip(value,recorded):
                        same_number(x,'' if y is None else str(y),key,nonfinite);scalars+=1
                else:same_number(value,row[key],key,nonfinite);scalars+=1
            stream=trial+':'+row['vehicle_id']+':'+kind;by_stream[stream]=by_stream.get(stream,0)+1;verified+=1
            writer.writerow([trial,row['vehicle_id'],kind,index,conn.id,header,receive,m.header.seq,m.header.frame_id,conn.ext.callerid,hashlib.sha256(raw).hexdigest()])
        if expected:raise ValueError('selected motion rows absent from raw bag')
    return {'experiment_id':trial,'bag_sha256':manifest['source_file_sha256'],'raw_records_indexed':len(physical),
        'motion_messages_verified':verified,'numeric_scalars_verified':scalars,'streams':by_stream,
        'index_mapping':'all message index entries sorted by (chunk_pos,offset), not by measurement/header time',
        'independent_library':'rosbags.rosbag1 + ROS1_NOETIC typestore',
        'range_payloads_redecoded':False,'nonselected_topics_deserialized':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'imu_independent_raw_motion_readback')
    try:
        checks=[]
        with gzip.open(args.output/'motion_identity_readback.csv.gz','wt',newline='') as f:
            writer=csv.writer(f);writer.writerow(['experiment_id','vehicle_id','kind','record_index','connection_id','header_epoch_ns','receive_epoch_ns','header_seq','frame_id','callerid','raw_message_sha256'])
            for trial in ('T08','T10'):
                packet=args.packets/trial;meta=json.loads((packet/'input_manifest.json').read_text())
                checks.append(verify_trial(packet,args.data_root/'extracted/bags'/meta['source_bag_relative_path'],writer))
        save(args.output/'verification.json',{'status':'DONE','all_passed':True,'checks':checks,
            'A_estimator_or_PR45_decoder_imported':False,'scope':'independent standard-motion payloads, all covariance/scalars/IDs; range bytes retain PR45 verified lineage',
            'deployed_MCU_or_physical_time_identified':False})
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
