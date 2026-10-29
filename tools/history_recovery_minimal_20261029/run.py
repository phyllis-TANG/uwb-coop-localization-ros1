"""Explicit freeze -> two replays + eight snapshots + one prefix contract. No retries."""
import argparse, copy, json, time
from support import *

def freeze():
 index=json.loads((EVIDENCE/'RUN_INDEX.json').read_text());assert index['commit']=='312180ef51c6ea4ba394bc85618674ec36ff786d'
 archive=EVIDENCE.parents[2]/'cooperative_influence_probe_20261028_v1.tar.gz'
 assert archive.stat().st_size==54249275 and sha(archive)=='50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320'
 for p,h in index['source_sha256'].items():assert sha(EVIDENCE/'source'/p)==h,p
 cells=[];inputs={}
 for case in SET['cases']:
  for method in SET['reuse_methods']:
   c=next(c for c in index['cells'] if c['case']==case and c['method']==method);run=EVIDENCE/c['path'];assert sha(run/'run.json')==c['run_sha256']
   meta=json.loads((run/'run.json').read_text());out=meta['outputs'];out=[dict(path=k,**v) for k,v in out.items()] if isinstance(out,dict) else out
   for o in out:assert sha(run/o['path'])==o['sha256']
   for p,h in c['input_sha256'].items():assert sha(EVIDENCE/'inputs'/case/p)==h
   inputs[case]=c['input_sha256'];cells.append(dict(id=c['id'],mode='verified_reuse',status='VERIFIED',source_path=c['path'],manifest_sha256=c['run_sha256']))
  cells.append(dict(id=case+'__N',mode='new_replay',status='PLANNED'))
  for p in SET['snapshot_priors']:
   for x in SET['snapshot_initializations']:cells.append(dict(id=case+'__prior'+p+'__init'+x,mode='snapshot',status='PLANNED'))
 cells.append(dict(id='nominal_prefix46',mode='contract_only',status='PLANNED'))
 spec=dict(base_commit=head(),archive_path=str(archive),archive_sha256=sha(archive),old_execution_commit=index['commit'],old_source_sha256=index['source_sha256'],source_sha256=source_lock(),settings=SET,inputs=inputs,cells=cells,status='FROZEN_NOT_RUN')
 out=OUT/'v1';out.mkdir(exist_ok=False);dump(out/'PRE_EXECUTION.json',spec);dump(DOC/'FROZEN_INDEX.json',spec);print('Verified archive, sources, inputs and 10 reused cells')

def run():
 from engine import execute,solve_snapshot
 spec=json.loads((OUT/'v1/PRE_EXECUTION.json').read_text());assert source_lock()==spec['source_sha256'];assert not (OUT/'v1/RUN_INDEX.json').exists()
 idx=copy.deepcopy(spec);idx.update(status='RUNNING',execution_commit=head());dump(OUT/'v1/RUN_INDEX.json',idx)
 def save(id,value,elapsed):
  c=next(c for c in idx['cells'] if c['id']==id);p=OUT/'v1'/(id+'.jsonl.gz');write(p,value);c.update(status='DONE',path=p.name,sha256=sha(p),elapsed_wall_s=elapsed);dump(OUT/'v1/RUN_INDEX.json',idx);print(id,'DONE',round(elapsed,3),flush=True)
 for case in SET['cases']:
  cfg=config(case);events=read(EVIDENCE/'inputs'/case/'events.jsonl.gz');start=time.perf_counter();rows=execute(events,cfg);save(case+'__N',rows,time.perf_counter()-start)
  t=SET['snapshot_state_s'];n=next(r['snapshot'] for r in rows if r['state_time_s']==t);i=next(r['snapshot'] for r in old(case,'I') if r['state_time_s']==t)
  assert n['times_s']==i['times_s'] and n['local']==i['local'] and n['observations']==i['observations'];assert all(p is None for p in n['peers_m'])
  packs={'N':n,'I':i}
  for pn in SET['snapshot_priors']:
   for xn in SET['snapshot_initializations']:
    start=time.perf_counter();r=solve_snapshot(n,packs[pn],packs[xn],cfg);r.update(case=case,prior_source=pn,initial_source=xn,initial_snapshot_sha256=digest(packs[xn]),prior_snapshot_sha256=digest(packs[pn]),retained_factors_sha256=digest({k:n[k] for k in ('times_s','local','observations','peers_m')}));save(case+'__prior'+pn+'__init'+xn,[r],time.perf_counter()-start)
 case=SET['cases'][0];events=read(EVIDENCE/'inputs'/case/'events.jsonl.gz');origin=events[0]['receive_epoch_ns'];prefix=[e for e in events if e['receive_epoch_ns']<=origin+int(SET['prefix_contract_last_receive_s']*1e9)]
 start=time.perf_counter();rows=execute(prefix,config(case));save('nominal_prefix46',rows,time.perf_counter()-start)
 idx['status']='DONE';dump(OUT/'v1/RUN_INDEX.json',idx);dump(DOC/'RUN_INDEX.json',idx)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=('freeze','run'));a=p.parse_args();globals()[a.phase]()
