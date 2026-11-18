"""Extract/hash-check and independently recompute all saved numerical endpoints."""
import argparse,csv,gzip,json,tarfile,time
from pathlib import Path,PurePosixPath
import numpy as np
from pxr import Usd,UsdGeom
from checker import audit,metrics
from coverage import sha,write
from prepare import digest

def verify(archive,manifest,out,report):
 start=time.monotonic();m=json.loads(manifest.read_text());assert sha(archive)==m['archive_sha256'];out.mkdir(exist_ok=False);seen=set()
 with tarfile.open(archive) as tar:
  for member in tar:
   name=member.name;p=PurePosixPath(name);assert member.isfile() and not p.is_absolute() and '..' not in p.parts and name in m['files'] and name not in seen;seen.add(name);dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(member).read());assert sha(dest)==m['files'][name]
 assert seen==set(m['files']);f=json.loads((out/'FREEZE.json').read_text())
 for name,h in f['files'].items():assert sha(out/'frozen_source'/name)==h
 inp=json.loads(gzip.decompress((out/'INPUTS.json.gz').read_bytes()));by={r['observation']['id']:r for r in inp};count=accepted=calls=0;maxcost=maxgrad=0;keys=set()
 for stage in ['main','optional']:
  p=json.loads((out/'runs'/f'{stage}_PLAN.json').read_text());status=json.loads((out/'runs'/f'{stage}_STATUS.json').read_text());assert not status['unexecuted'];assert p['freeze_sha']==m['run_freeze_sha'];assert len(p['tasks'])==status['completed']==(120 if stage=='main' else 30)
  for task in p['tasks']:
   assert task['key'] not in keys;keys.add(task['key']);r=json.loads((out/'runs'/(task['key']+'.json')).read_text());attempt=json.loads((out/'runs'/(task['key']+'.attempt.json')).read_text());checkpoint=json.loads((out/'runs'/(task['key']+'.checkpoint.json')).read_text());i=by[task['id']]
   assert r['task']==task==attempt['task'] and r['input_sha256']==i['input_sha256']==digest(i['observation'])==attempt['input_sha256'];assert r['freeze_sha']==attempt['freeze_sha']==m['run_freeze_sha'];assert checkpoint['inflight'] is None and checkpoint['x']==r['x'];assert r['optimizer_calls_started']==2
   a=audit(i['observation'],r);assert metrics(i['observation'],i['reference'],r['x'],r['method'])==r['metrics'];count+=1;accepted+=r['state']=='ACCEPTED';calls+=r['optimizer_calls_started'];maxcost=max(maxcost,a['cost_error']);maxgrad=max(maxgrad,a['gradient_error'])
 # Actual portable USD world-space antenna transforms, using saved CPU records as reference.
 stage=Usd.Stage.Open(str(out/'continuous_route.usda'));assert stage.GetTimeCodesPerSecond()==50 and UsdGeom.GetStageMetersPerUnit(stage)==1 and UsdGeom.GetStageUpAxis(stage)=='Z';n=0;maxpos=0
 for row in csv.DictReader((out/'CPU_REPLAY.csv').open()):
  tc=float(row['time_code']);cache=UsdGeom.XformCache(Usd.TimeCode(tc));q=np.array([cache.GetLocalToWorldTransform(stage.GetPrimAtPath(f'/World/Car{c}/Antenna')).ExtractTranslation() for c in [1,2]]);expected=np.array([[float(row[f'car{c}_{k}']) for k in ['x','y','z']] for c in [1,2]]);error=float(np.max(abs(q-expected)));assert error<1e-10 and abs(np.linalg.norm(q[1]-q[0])-float(row['peer_distance_m']))<1e-10;maxpos=max(maxpos,error);n+=1
 result=dict(status='PASS',hashed_files=len(seen),endpoints=count,accepted=accepted,not_accepted=count-accepted,saved_optimizer_calls=calls,readback_optimizer_calls=0,max_cost_error=maxcost,max_gradient_error=maxgrad,usd_replay_queries=n,max_portable_position_error_m=maxpos,seconds=time.monotonic()-start,archive_sha256=m['archive_sha256']);write(report,result);print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();verify(a.archive,a.manifest,a.out,a.report)
