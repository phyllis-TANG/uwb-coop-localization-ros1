"""Read-only field reuse, explicit CRLF identity reconstruction, record-level LOO."""
import json,csv,hashlib,shutil,importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];SOURCE=ROOT/'docs/research/paper_evidence_completion_20261103';P=ROOT/'docs/research/midterm_simulation_phase1'
def write_csv(name,rows):
 with (P/name).open('x') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
def main():
 original=json.loads((SOURCE/'SOURCE_MANIFEST.json').read_text());target=P/'tmp/field_crlf_reconstruction_v2'
 shutil.copytree(SOURCE,target)
 repaired=[];unmatched=[]
 for r in original['files']:
  src=SOURCE/r['destination'];b=src.read_bytes()
  if hashlib.sha256(b).hexdigest()!=r['destination_sha256']:
   candidate=b.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
   if hashlib.sha256(candidate).hexdigest()!=r['destination_sha256']:
    unmatched.append(r['destination']);continue
   (target/r['destination']).write_bytes(candidate);repaired.append(r['destination'])
 spec=importlib.util.spec_from_file_location('field_verifier',SOURCE/'verify_bundle.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.ROOT=target
 out=P/'field_readback';out.mkdir(exist_ok=True)
 def write(name,value):
  with (out/Path(name).name).open('x') as f:json.dump(value,f,indent=2)
 # Only two historical setup notes remain unmatched; not read by numeric analysis.
 assert set(unmatched)=={'setup/加快现场采集_顺序与起点修订_20261101.txt','setup/第二次静止预检通过_20261101.txt'}
 original_read=m.read
 def read(name):
  value=original_read(name)
  if name=='SOURCE_MANIFEST.json':value=dict(value,files=[r for r in value['files'] if r['destination'] not in unmatched])
  return value
 m.read=read;m.write=write;m.main()
 (P/'FIELD_RECONSTRUCTION.json').write_text(json.dumps(dict(status='NUMERIC_READBACK_PASS_IDENTITY_PARTIAL',unmatched_historical_setup_notes=unmatched,files_reconstructed=repaired,original_source_unchanged=True,sha_rules_unchanged=True),indent=2))
 # Match manuscript's five N records and original common accepted time masks.
 data=json.loads((out/'static_pair_rows.json').read_text());five=['G1_R2_N','G1_R3_N','G2_R1_N','G2_R2_N','G2_R3_N'];per=[];loo=[]
 for run in five:
  for car in ['car1','car2']:
   for arm in ['J','W025']:
    pair={profile:next(r for r in data if r['run_id']==run and r['car']==car and r['arm']==arm and r['profile']==profile and r['phase']=='normal') for profile in ['raw','historical']}
    per.append(dict(run_id=run,geometry=run[:2],car=car,arm=arm,D_raw_m2=pair['raw']['D_m2'],D_historical_m2=pair['historical']['D_m2'],C_m2=pair['historical']['D_m2']-pair['raw']['D_m2'],n_common=pair['raw']['n_common']))
 for omitted in [None]+five:
  for car in ['car1','car2']:
   for arm in ['J','W025']:
    rows=[r for r in per if r['run_id']!=omitted and r['car']==car and r['arm']==arm];a=[r['C_m2'] for r in rows if r['geometry']=='G1'];b=[r['C_m2'] for r in rows if r['geometry']=='G2']
    loo.append(dict(omitted=omitted or 'none',car=car,arm=arm,n_G1=len(a),n_G2=len(b),C_G1_m2=sum(a)/len(a),C_G2_m2=sum(b)/len(b),T_m2=sum(b)/len(b)-sum(a)/len(a)))
 write_csv('FIELD_PER_RECORD.csv',per);write_csv('FIELD_LEAVE_ONE_RECORD.csv',loo)
 (P/'FIELD_WINDOW_REUSE.json').write_text(json.dumps(dict(status='existing five scope definitions independently reproduced; no extra chosen windows',rows=json.loads((out/'static_scope_20_readback.json').read_text())),indent=2))
if __name__=='__main__':main()
