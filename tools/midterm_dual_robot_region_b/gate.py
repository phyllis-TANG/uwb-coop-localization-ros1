"""Exactly the predeclared random admission conditions; no threshold tuning."""
import argparse,statistics
from common import *
from runtime import *

def assess(out,readback,freeze):
 lock,inputs=formal_context(freeze);plan=plans(inputs,'deterministic');reasons=[];main={m:[] for m in ('P4','N4')};term={m:[] for m in main};records=0
 if readback['status']!='PASS' or readback['completed']!=44:reasons.append('INDEPENDENT_READBACK_NOT_COMPLETE_PASS')
 wall={r['id']:r['wall_seconds'] for r in map(json.loads,(out/'WALL_COSTS.jsonl').read_text().splitlines())}
 for job in plan:
  row=inspect_unit(out,job,identity(job,freeze,lock))
  if row is None or row['status']!='COMPLETED':reasons.append('MISSING_OR_FAILED:'+job['id']);continue
  record=read(out/(job['id']+'.result.json.gz'));records+=1
  if record['certificate_b']['status']!='PASS' or record['certificate_a']['status']!='PASS':reasons.append('CERTIFICATE_NOT_PASS:'+job['id'])
  ev=record['evaluation']
  if ev['truth_in_declared_domain'] and ev['noise_event'] and ev['noise_event']['holds'] and not ev['finite_joint_outer_contains']:reasons.append('NOISE_EVENT_CONTAINMENT_FAILED:'+job['id'])
  if job['case']['group']=='main' and job['method'] in main:
   m=job['method'];main[m].append(wall[job['id']]);term[m].append(record['result']['termination'])
 med={}
 for m in main:
  med[m]=statistics.median(main[m]) if main[m] else None
  if len(main[m])!=12:reasons.append(m+'_MAIN_DENOMINATOR_NOT_12')
  if any(x!='RESOLUTION_COMPLETE' for x in term[m]):reasons.append(m+'_MAIN_SEARCH_NOT_COMPLETE')
  if med[m] is None or med[m]>2:reasons.append(m+'_MEDIAN_FULL_COST_EXCEEDS_2_SECONDS')
 return dict(status='PASS' if not reasons else 'FAIL',reasons=reasons,main_cost_median_seconds=med,main_terminations=term,formal_records=records,freeze_sha=freeze,a_sha=lock['a_sha'],random_planned=240,random_authorized_to_execute=not reasons)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--readback',type=Path,required=True);p.add_argument('--freeze',required=True);a=p.parse_args();z=assess(a.results,read(a.readback),a.freeze);write(DOC/'GATE.json',z);print(json.dumps(z))
