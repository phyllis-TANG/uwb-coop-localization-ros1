#!/usr/bin/env python3
"""Read-only inventory of the two 20261018 development bags; no estimator."""
import collections
import datetime
import hashlib
import importlib.metadata
import json
import math
import statistics
import subprocess
import sys
from pathlib import Path
from rosbags.highlevel import AnyReader

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).with_name('historical_readiness.json')
BASE = '868349b543a03a6a713d1675e1d4ada7d905410c'
FILES = {
 '015334': ('TWO_CAR_C1_static_C2_auto_L_20261018_015334.bag', 'bb2f8cbfecf3e73cdf1b12f4c290b51d0c74215006746abba72c0b9c7a0946e6'),
 '033248': ('TWO_CAR_C2_static_C1_auto_straight_aligned_20261018_033248.bag', '4e1283bbd58f9a64187a872cd9edeccaccdd5c438149d871761c6e2e11a67bbd'),
}
SOURCES = [
 'docs/field_tests/20261018/README.md',
 'docs/field_tests/20261018/results/two_car_graph_summary.json',
 'docs/field_tests/20261017/session_config.json',
 'docs/field_tests/20261024_25/RESULT_CONTRACT.md',
 'docs/field_tests/20261024_25/geometry.json',
 'tools/two_car_offline_graph.py',
 'datasets/field_raw/20261018/README.md',
 'datasets/field_raw/20261018/metadata/live_field/BAG_SHA256SUMS.txt',
 'datasets/field_raw/20261018/notes/live_field/antenna_mount_survey_20261018.txt',
 'datasets/field_raw/20261018/notes/live_field/clock_status_end_20261018_055752.txt',
 'datasets/field_raw/provenance/user_confirmations_20261020.md',
]
for name, _ in FILES.values():
 SOURCES.append('datasets/field_raw/20261018/notes/live_field/'+name.replace('.bag','_notes.txt'))
SOURCES.append(str(Path(__file__).resolve().relative_to(ROOT)))

def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
 return h.hexdigest()

def summary(v):
 return {'min':min(v),'median':statistics.median(v),'max':max(v)} if v else None

def audit(key, name, expected):
 path=ROOT/'datasets/field_raw/20261018/bags'/name
 actual=digest(path)
 if actual!=expected:raise ValueError('input SHA mismatch '+name)
 rows={}
 with AnyReader([path]) as r:
  result={'asset_id':key,'relative_path':str(path.relative_to(ROOT)),
   'sha256':actual,'bytes':path.stat().st_size,'sha256_matches_source_manifest':True,
   'receive_start_epoch_ns':int(r.start_time),'receive_end_exclusive_epoch_ns':int(r.end_time),
   'duration_ns':int(r.duration),
   'topics':{c.topic:{'type':c.msgtype,'connection_count':c.msgcount} for c in r.connections},
   'raw_topics_present':[c.topic for c in r.connections if 'raw' in c.topic],
   'normalized_joint_events_status':'NOT_EXPORTED',
   'strict_D0_D1_execution_status':'BLOCKED','conditional_D0_D1_runs':0}
  for topic in [f'/{car}/{suffix}' for car in ['car1','car2'] for suffix in ['odom','uwb/ranges','imu']]:
   rows[topic]={'receive':[],'header':[],'offset':[],'frame_ids':set(),'child_frame_ids':set(),
    'identities':set(),'duplicate_header_seq_stamp':0,'duplicate_link_ids':0,
    'valid_link_counts':collections.Counter(),'nonfinite_quality_entries':0,'tag_ids':set(),
    'first_odom_pose':None,'last_odom_pose':None,'odom_xy_path_m':0.0}
  for c,receive,raw in r.messages():
   if c.topic not in rows:continue
   m=r.deserialize(raw,c.msgtype);d=rows[c.topic]
   receive=int(receive);header=int(m.header.stamp.sec)*10**9+int(m.header.stamp.nanosec)
   d['receive'].append(receive);d['header'].append(header);d['offset'].append(receive-header)
   d['frame_ids'].add(m.header.frame_id)
   identity=(int(m.header.seq),header)
   if identity in d['identities']:d['duplicate_header_seq_stamp']+=1
   d['identities'].add(identity)
   if c.topic.endswith('/odom'):
    d['child_frame_ids'].add(m.child_frame_id)
    p=m.pose.pose.position;q=m.pose.pose.orientation
    pose=[float(p.x),float(p.y),float(p.z),math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))]
    if d['last_odom_pose'] is not None:d['odom_xy_path_m']+=math.dist(pose[:2],d['last_odom_pose'][:2])
    if d['first_odom_pose'] is None:d['first_odom_pose']=pose
    d['last_odom_pose']=pose
   if c.topic.endswith('/ranges'):
    d['tag_ids'].add(m.tag_id);links=collections.Counter(x.anchor_id for x in m.ranges)
    d['duplicate_link_ids']+=sum(n>1 for n in links.values())
    for x in m.ranges:
     if links[x.anchor_id]==1 and math.isfinite(x.range) and x.range>0:d['valid_link_counts'][x.anchor_id]+=1
     if not math.isfinite(x.quality):d['nonfinite_quality_entries']+=1
  result['input_scan']={}
  for topic,d in rows.items():
   receive=d.pop('receive');header=d.pop('header');offset=d.pop('offset');d.pop('identities')
   d.update({'message_count':len(receive),'receive_range_epoch_ns':[min(receive),max(receive)],
    'header_range_epoch_ns':[min(header),max(header)],'receive_minus_header_ns':summary(offset),
    'header_backwards_count':sum(b<a for a,b in zip(header,header[1:])),
    'header_equal_count':sum(b==a for a,b in zip(header,header[1:])),
    'receive_backwards_count':sum(b<a for a,b in zip(receive,receive[1:])),
    'max_receive_gap_ns':max(b-a for a,b in zip(receive,receive[1:])),
    'max_header_gap_ns':max(b-a for a,b in zip(header,header[1:]))})
   for field in ['frame_ids','child_frame_ids','tag_ids']:d[field]=sorted(d[field])
   d['valid_link_counts']=dict(d['valid_link_counts'])
   if not topic.endswith('/odom'):
    for field in ['first_odom_pose','last_odom_pose','odom_xy_path_m']:d.pop(field)
   result['input_scan'][topic]=d
 return result

def main():
 evidence={p:{'sha256':digest(ROOT/p),'source_commit':BASE} for p in SOURCES if not p.endswith('historical_input_audit.py')}
 evidence[SOURCES[-1]]={'sha256':digest(Path(__file__)),'source_commit':'this task; see delivery commit'}
 report={'schema_version':1,'status':'BLOCKED','inventory_status':'DONE','strict_field_execution_status':'BLOCKED',
  'run_id':'historical-readiness-015334-033248-v1','role':'two_car_input_readiness',
  'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
  'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
  'command_argv':[sys.executable,str(Path(__file__).relative_to(ROOT))],
  'environment':{'python':sys.version,'rosbags':importlib.metadata.version('rosbags')},
  'common_base_commit':BASE,'reader':{'rosbags':importlib.metadata.version('rosbags'),'mode':'read-only; no optimizer/ROS process'},
  'inputs':[audit(k,*v) for k,v in FILES.items()], 'evidence':evidence,
  'historical_assumptions':{
   'room_anchor_source':'docs/field_tests/20261017/session_config.json; user confirmed October 17 wall placements unchanged',
   'initial_antenna_xyz_m':{'015334':{'car1':[1.5,4.0,0.17],'car2':[2,2,0.20]},'033248':{'car1':[1.5,4.0,0.17],'car2':[2.95,3.04,0.20]}},
   'initial_yaw_deg':{'015334':{'car1':0,'car2':90},'033248':{'car1':-90,'car2':0}},
   'initial_yaw_status':'placement hypotheses, not independent surveyed yaw; no endpoint-based initialization',
   'historical_body_antenna_xy_m':{'car1':[0.08,-0.06],'car2':[0.12,-0.08]},
   'later_car2_body_antenna_xy_m':[-0.12,0.08],
   'later_car2_status':'operator correction in 20261024_25 geometry.json; odom-origin transform unverified; do not silently transplant',
   'clock_policy_old_batch':'common bag receipt time for all association; headers unsynchronized; not causal-prefix acceptance',
   'raw_bridge_policy':'only /carN/uwb/ranges present in these bags; no raw topic to independently pair; do not count bridge+raw twice if later added',
   'primary_peer_direction':'Car1 node_1 to Car2 node_0; reverse diagnostic only',
   'correction_policy':'first proposed historical diagnostic raw wall and peer; historical Car2-only P1 explicitly separate, not for Car1 or 20261024_25',
   'car2_only_P1':{'source_asset_id':'CAR2_P1_REINSTALL_STATIC_20261017_045257.bag','source_sha256':'f7250698ae484b7ace3bf152b1ff216f5470b5d75f0b90a66483edb402d1ec33','source_antenna_xyz_m':[2.0,2.0,0.2],'bias_m':{'node_10':0.608864,'node_2':0.449738,'node_3':0.201286,'node_8':0.368514},'status':'historical diagnostic correction only; no transfer validation; not applied by inventory'},
   'manual_endpoint_antenna_xyz_m':{'015334':{'car1':[1.5,4.0,0.17],'car2':[2.95,3.04,0.20]},'033248':{'car1':[1.45,2.98,0.17],'car2':[2.95,3.04,0.20]}},
   'manual_endpoint_tape_m':{'015334':1.743,'033248':1.54},
   'manual_reference_uncertainty':'unknown; not continuous truth; endpoint never estimator input'},
  'blocked_reasons':[
   'No accepted per-car odom/base-to-survey-center transform; Car2 lever sign conflicts with later operator correction.',
   'Global initial yaws are only historical hypotheses; strict provenance/uncertainty configuration not frozen for this joint causal runner.',
   'No validated per-stream header-to-common-clock mapping with uncertainty; NTP status and receipt pairing do not prove synchronized measurement.',
   'No normalized joint receive-order event bundle/config with dependency and raw/bridge identity validation has been exported or accepted.',
   'Only manual stop/checkpoint references with unknown uncertainty; no accepted continuous truth. Field trajectory RMSE/ATE remains forbidden.'],
  'run_policy':{'four_conditional_diagnostic_runs':'NOT_RUN; no strict validator bypass','held_out_sessions':'T09/T11/T13/T15 untouched','video':'no download/read/accuracy use','hardware':'no ROS, serial or vehicle start'},
  'storage':{'new_large_files_created':False,'existing_bags':'read in place from base commit; not copied or modified','local_future_large_outputs':'I drive required; no I-drive alias inferred here','cloud_future_outputs':'separate Git-external directory required'}}
 OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'output':str(OUT.relative_to(ROOT)),'inputs':len(report['inputs']),'status':report['strict_field_execution_status']}))
if __name__=='__main__':main()
