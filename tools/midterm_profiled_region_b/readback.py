"""Portable all-record independent readback; no solve call."""
import argparse,time
from common import *
from certificate import audit,xy_contains,bias_reference
from profiled import recover_bias
from fractions import Fraction as F

def verify(directory):
 start=time.perf_counter();meta=read(directory/'RUN.json');m=meta['manifest']
 for f,h in m['files'].items():assert sha(ROOT/f)==h,f
 plan=read(DOC/'INPUTS.json.gz')[meta['stage']];cases={c['id']:c for c in plan};complete=[];cert_failed=[];nodes=0
 for file in sorted(directory.glob('*.receipt.json')):
  row=read(file);rp=directory/(row['id']+'.json.gz');assert sha(rp)==row['record_sha'];r=read(rp);c=cases[row['case']];method=row['method'];assert r['case']==c and r['identity']==dict(freeze=meta['freeze'],input_hash=digest(c),method=method,id=row['id'])
  if r['reused_legacy']:assert sha(ROOT/c['legacy_path'])==c['legacy_sha'];assert read(ROOT/c['legacy_path'])['result']==r['result']
  if row['certificate']=='PASS':z=audit(c['model'],c['settings'],r['result'],method);assert z==r['certificate'];nodes+=z['nodes']
  else:cert_failed.append(row['id'])
  assert OC.metrics(c['model'],r['result'])==r['metrics']
  assert xy_contains(r['result'],c['evaluation']['truth'][:2])==row['truth_contained']
  if c['evaluation'].get('mirror_truth'):assert xy_contains(r['result'],c['evaluation']['mirror_truth'][:2])==row['mirror_contained']
  # Independent reconstructed interval contains/rejects same actual known point.
  ref,inner=bias_reference(c['evaluation']['truth'][:2],c['model'],c['settings']['q']);v=r['evaluation']['bias_reconstruction_at_truth_xy']
  if ref is not None:assert v['outer'] and F(v['outer'][0])<=ref[0] and F(v['outer'][1])>=ref[1]
  complete.append(row['id'])
 expected={c['id']+'_'+method for c in plan for method in ['OLD','PROFILED']};assert set(complete)<=expected
 status=read(directory/'STATUS.json');assert status['completed_methods']==len(complete);assert set(status['unexecuted'])==expected-set(complete)
 return dict(status='PASS' if not cert_failed else 'CERTIFICATE_FAILURES_PRESERVED',planned=len(expected),completed=len(complete),unexecuted=sorted(expected-set(complete)),certificate_failures=cert_failed,nodes_checked=nodes,readback_seconds=time.perf_counter()-start,search_calls=0,optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=verify(a.results);write(a.out,z);print(json.dumps(z))
