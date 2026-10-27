"""Corrupt private copies, reseal hashes, require the raw readback to reject them."""
import argparse
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
import shutil

from meta import LEGACY,finish,save,sha,start
from verify_packets import verify_case


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'FGO_B_negative_packet_checks')
    try:
        source=args.packets/'004023';case=next(c for c in json.loads(LEGACY.read_text())['cases'] if c['id']=='004023')
        with gzip.open(source/'events.jsonl.gz','rt') as f:original=[json.loads(x) for x in f]
        with gzip.open(source/'legacy_events.jsonl.gz','rt') as f:old=[json.loads(x) for x in f]
        index=next(i for i,r in enumerate(original) if r['kind']=='imu' and abs(r['message']['angular_velocity']['z'])>1e-8)
        specs=('gyro_sign','gyro_degrees_as_radians','covariance','missing_IMU','duplicate_record','float_epoch','future_receive_identity','reordered_records')
        checks=[]
        for spec in specs:
            target=args.output/spec;target.mkdir();rows=copy.deepcopy(original);legacy=copy.deepcopy(old)
            if spec=='gyro_sign':rows[index]['message']['angular_velocity']['z']*=-1
            elif spec=='gyro_degrees_as_radians':rows[index]['message']['angular_velocity']['z']*=180/math.pi
            elif spec=='covariance':rows[index]['message']['angular_velocity_covariance'][8]+=1.
            elif spec=='missing_IMU':rows.pop(index);legacy.pop(index)
            elif spec=='duplicate_record':rows.insert(index,copy.deepcopy(rows[index]));legacy.insert(index,copy.deepcopy(legacy[index]))
            elif spec=='float_epoch':rows[index]['receive_epoch_ns']=float(rows[index]['receive_epoch_ns'])
            elif spec=='future_receive_identity':rows[index]['receive_epoch_ns']+=1000000000;rows[index]['receive_relative_s']+=1
            elif spec=='reordered_records':rows[index],rows[index+1]=rows[index+1],rows[index];legacy[index],legacy[index+1]=legacy[index+1],legacy[index]
            digest=hashlib.sha256();old_digest=hashlib.sha256()
            for name,content,h in [('events.jsonl.gz',rows,digest),('legacy_events.jsonl.gz',legacy,old_digest)]:
                with gzip.open(target/name,'wt') as f:
                    for row in content:
                        text=json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n';f.write(text);h.update(text.encode())
            shutil.copy2(source/'timing_identity.json',target/'timing_identity.json')
            manifest=json.loads((source/'input_manifest.json').read_text());manifest['event_uncompressed_sha256']=digest.hexdigest();manifest['legacy_event_uncompressed_sha256']=old_digest.hexdigest()
            for entry in manifest['files']:
                entry['sha256']=sha(target/entry['relative_path']);entry['bytes']=(target/entry['relative_path']).stat().st_size
            save(target/'input_manifest.json',manifest)
            try:verify_case(target,case)
            except (ValueError,KeyError,TypeError) as error:checks.append({'case':spec,'rejected':True,'reason':str(error),'file_hashes_resealed_to_test_payload_not_just_checksums':True})
            else:raise AssertionError('negative packet wrongly accepted: '+spec)
        save(args.output/'verification.json',{'status':'DONE','all_negative_copies_rejected':True,'checks':checks,
            'original_packet_modified':False,'A_F2_F3_causality_proved':False,'scope':'B readback guards only; no optimization or field parameter selection'})
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
