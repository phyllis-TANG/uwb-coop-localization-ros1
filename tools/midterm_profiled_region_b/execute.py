"""Paired execution with all-in time receipts and conservative stop bookkeeping."""
import argparse,time,os,fcntl,subprocess,traceback
from common import *
from profiled import solve as profile_solve,recover_bias
from certificate import audit,xy_contains,bias_reference,rational_profile
from fractions import Fraction as F

def evaluate(case,result,method):
 m=case['model'];e=case['evaluation'];truth=e['truth'];pos=truth[:2]
 out=dict(truth_xy_contained=xy_contains(result,pos),mirror_xy_contained=xy_contains(result,e['mirror_truth'][:2]) if e.get('mirror_truth') else None)
 lo,hi=OC.rational_bound(tuple(OC.point(v) for v in truth),m)
 out.update(true_parameter_noise_event=hi<=F(case['settings']['q']),truth_residual_lower=str(lo),truth_residual_upper=str(hi))
 # Reconstruction is evaluation only, never used to select a branch or prune.
 z=recover_bias(pos,m,case['settings']['q']);ref,inner=bias_reference(pos,m,case['settings']['q'])
 if ref is None:assert z['outer'] is None or z['status']=='UNDECIDED'
 else:
  assert z['outer'] is not None
  assert F(z['outer'][0])<=ref[0] and F(z['outer'][1])>=ref[1]
 out['bias_reconstruction_at_truth_xy']=z
 return out

def process(case,method,out,freeze):
 unit=case['id']+'_'+method;record_path=out/(unit+'.json.gz');attempt=out/(unit+'.attempt.json');receipt=out/(unit+'.receipt.json')
 identity=dict(freeze=freeze,input_hash=digest(case),method=method,id=unit)
 if record_path.exists():
  r=read(record_path);assert r['identity']==identity
  if not receipt.exists():raise RuntimeError('Completed result but timing receipt absent; record complete, timing unavailable; manual audit required, no retry')
  return read(receipt)
 if attempt.exists():raise RuntimeError('Attempt without result: uncertain execution, no automatic repeat')
 start=time.perf_counter();write(attempt,identity);search_start=time.perf_counter();reused=case.get('legacy_path') and method=='OLD'
 if reused:
  source=ROOT/case['legacy_path'];assert sha(source)==case['legacy_sha'];r0=read(source);assert r0['model']==case['model'];result=r0['result'];search_cost=None;load_cost=time.perf_counter()-search_start
 else:
  result=OLD.solve(case['model'],case['settings']) if method=='OLD' else profile_solve(case['model'],case['settings'])
  search_cost=time.perf_counter()-search_start;load_cost=0
 cert_start=time.perf_counter();certificate_failure=None
 try:cert=audit(case['model'],case['settings'],result,method)
 except Exception as e:cert=dict(status='FAIL',error=repr(e));certificate_failure=traceback.format_exc()
 cert_cost=time.perf_counter()-cert_start
 metric_start=time.perf_counter();metrics=OC.metrics(case['model'],result);ev=evaluate(case,result,method);metric_cost=time.perf_counter()-metric_start
 record=dict(identity=identity,case=case,result=result,metrics=metrics,certificate=cert,evaluation=ev,reused_legacy=bool(reused),certificate_failure=certificate_failure)
 io_start=time.perf_counter();write(record_path,record);io_cost=time.perf_counter()-io_start
 # total includes durable attempt creation, search/loading, certificate, projection/evaluation, compressed result IO.
 total=time.perf_counter()-start
 row=dict(id=unit,case=case['id'],group=case['group'],condition=case['condition'],seed=case.get('seed'),method=method,reused=bool(reused),old_state_dimension=len(case['model']['domain']),record_sha=sha(record_path),certificate=cert['status'],search_seconds=search_cost,legacy_search_seconds=result['elapsed_seconds'] if reused else None,load_seconds=load_cost,certificate_seconds=cert_cost,metrics_evaluation_seconds=metric_cost,result_io_seconds=io_cost,total_seconds=total,processed=result['processed'],pending=result['counts'].get('PENDING',0),undecided=result['counts'].get('UNDECIDED',0),inside=result['counts'].get('INSIDE',0),termination=result['termination'],empty=result['empty_proved'],numerical_failure=result['failure'],truth_contained=ev['truth_xy_contained'],mirror_contained=ev['mirror_xy_contained'],noise_event=ev['true_parameter_noise_event'],radius=metrics['radius_upper_m'],area_upper=metrics['area_upper_m2'],area_lower=metrics['area_lower_m2'])
 write(receipt,row);return row

def gate(case,rows):
 for r in rows:
  assert r['certificate']=='PASS' and r['numerical_failure'] is None
  if r['noise_event']:assert r['truth_contained'];assert r['mirror_contained'] in (None,True)
  if case['id']=='legacy_s1_empty':assert r['empty']
  if case['id']=='legacy_s2_budget':assert r['termination']=='BOX_BUDGET' and r['pending']>0

def run(out,stage,freeze):
 manifest=read(DOC/'FREEZE_MANIFEST.json')
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==freeze
 for f,h in manifest['files'].items():assert sha(ROOT/f)==h,f
 c=config();inputs=read(DOC/'INPUTS.json.gz')[stage]
 out.mkdir(parents=True,exist_ok=True)
 with (out/'LOCK').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  for a in out.glob('*.attempt.json'):
   if not (out/(a.name.removesuffix('.attempt.json')+'.json.gz')).exists():raise RuntimeError('Uncertain attempt blocks automatic execution')
  if stage=='random':
   g=read(out.parent/'deterministic'/'GATE.json');assert g['status']=='PASS' and g['freeze']==freeze and g['planned_inputs']==26
  start=time.time();meta=out/'RUN.json'
  if not meta.exists():write(meta,dict(freeze=freeze,stage=stage,manifest=manifest,versions=versions(),start_epoch=start,planned_inputs=len(inputs),planned_methods=len(inputs)*2,paired_order=c['method_order']))
  if (out/'STATUS.json').exists():print(json.dumps(read(out/'STATUS.json')));return
  start=read(meta)['start_epoch'];summary=[];unrun=[];stop_reason=None
  planned=[(case,method) for i,case in enumerate(inputs) for method in (['OLD','PROFILED'] if i%2==0 else ['PROFILED','OLD'])]
  for idx,(case,method) in enumerate(planned):
   if stage=='random' and time.time()-start>=c['random_total_seconds']:
    stop_reason='TOTAL_BUDGET';unrun=[x['id']+'_'+m for x,m in planned[idx:] if not (out/(x['id']+'_'+m+'.json.gz')).exists()];break
   existed=(out/(case['id']+'_'+method+'.receipt.json')).exists();wall_start=time.perf_counter()
   row=process(case,method,out,freeze);wall=time.perf_counter()-wall_start;summary.append(row)
   if not existed:
    with (out/'WALL_COSTS.jsonl').open('a') as f:
     f.write(json.dumps(dict(id=row['id'],wall_seconds=wall))+'\n');f.flush();os.fsync(f.fileno())
   if row['certificate']!='PASS':stop_reason='CERTIFICATE_FAILURE';unrun=[x['id']+'_'+m for x,m in planned[idx+1:]];break
   if stage=='deterministic' and idx%2==1:gate(case,summary[-2:])
   if len(summary)%20==0:print(stage,len(summary),'/',len(planned),'elapsed',round(time.time()-start,2),flush=True)
  status=dict(planned_methods=len(planned),completed_methods=len(summary),unexecuted=unrun,stop_reason=stop_reason,elapsed_including_io_seconds=time.time()-start)
  write(out/'STATUS.json',status)
  if stage=='deterministic':
   assert len(summary)==len(planned) and stop_reason is None
   write(out/'GATE.json',dict(status='PASS',freeze=freeze,planned_inputs=len(inputs),methods=len(summary)))
  print(json.dumps(status),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--stage',choices=['deterministic','random'],required=True);p.add_argument('--freeze',required=True);a=p.parse_args();run(a.out,a.stage,a.freeze)
