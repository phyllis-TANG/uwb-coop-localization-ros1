#!/usr/bin/env python3
"""Re-export saved D1/D2 numerical solutions without importing any optimizer."""
import argparse,csv,json,shutil
from pathlib import Path
from analyze_logs import read,dump,write_csv,error,state_row
from verify_evidence import sha

def table(p):
 with p.open() as f:return list(csv.DictReader(f))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--experiment',type=Path,required=True);ap.add_argument('--saved',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False)
 saved=a.saved/'full_intervention_results.json.gz'
 import gzip
 with gzip.open(saved,'rt') as f:records=json.load(f)
 truths={}
 def truth(sc,seed,ep):
  key=(sc,seed)
  if key not in truths:truths[key]={r['epoch_ns']:r for r in read(a.experiment/'inputs'/f'{sc}_seed{seed}'/'truth.jsonl.gz')}
  return truths[key][ep]
 d1={(int(r['seed']),r['arm'],int(r['state_epoch_ns'])):r for r in table(a.saved/'D1_series.csv')}
 d2={(r['scenario'],int(r['seed']),r['group'],r['role'],r['arm'],int(r['state_epoch_ns'])):r for r in table(a.saved/'D2_snapshots.csv')}
 one=[];two=[]
 for r in records:
  if r['kind']=='D1':
   key=(r['seed'],r['arm'],r['epoch']);old=d1.pop(key);row=r['result'];updated=dict(old,**error(row,truth('multi_common_uwb',r['seed'],r['epoch'])),bias=row.get('bias_rad_s'));one.append(updated)
  elif r['kind']=='D2':
   prefix=(r['scenario'],r['seed'],r['group'],r['role'],r['arm'])
   # The snapshot epoch is retained in the original CSV, whereas saved x has no epoch.
   candidates=[k for k in d2 if k[:5]==prefix];assert len(candidates)==1;key=candidates[0];old=d2.pop(key);row=state_row(r['x'][-1]);updated=dict(old,**error(row,truth(r['scenario'],r['seed'],key[-1])),bias=row['bias_rad_s']);two.append(updated)
 assert len(one)==354 and len(two)==28 and not d1 and not d2
 write_csv(a.output/'D1_series.csv',one);write_csv(a.output/'D2_snapshots.csv',two);dump(a.output/'D1_series.json',one);dump(a.output/'D2_snapshots.json',two)
 for name in ('D1_controls.json','jacobian_checks.json','receipt.json'):shutil.copyfile(a.saved/name,a.output/name)
 dump(a.output/'reexport_receipt.json',dict(status='PASS',saved_solutions=str(saved),saved_solutions_sha256=sha(saved),D1_rows=354,D2_rows=28,formal_matrix_restarts=0,main_reconstructions_this_revision=0,snapshot_solves_this_revision=0,bias_semantics='Absent bias -> null/CSV empty; valid zero -> estimate minus truth',original_solve_receipt='receipt.json retained unchanged'))
 print('PASS: exported 354 saved D1 rows and 28 saved D2 rows; zero solves')

if __name__=='__main__':main()
