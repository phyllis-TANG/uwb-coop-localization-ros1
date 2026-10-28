#!/usr/bin/env python3
"""Immutable preregistered 16 cells: 4 reuse + 4 derived + 8 new main replays."""
import argparse,copy,json,shutil,time
from collections import Counter
from pathlib import Path
import numpy as np
from common import ROOT,HERE,ART,CONFIG,METHODS,SCENARIOS,sha,dump,read,write,state,sources
from core import clip_pose,antennas
from replay_control import execute

def validate(index,complete=False):
 expected={f'{s}_seed101__{m}' for s in SCENARIOS for m in METHODS};cells=index['cells']
 if len(cells)!=16 or {c['id'] for c in cells}!=expected:raise ValueError('Must contain every preregistered cell exactly once')
 for c in cells:
  if c['id']!=c['case']+'__'+c['method']:raise ValueError('Identity mismatch')
  if c['status'] not in (['REUSED_VERIFIED','DONE'] if complete else ['REUSED_VERIFIED','PLANNED','RUNNING','DONE']):raise ValueError('Incomplete/failed cell')
 if complete and index['status']!='DONE':raise ValueError('Incomplete matrix')

def freeze(root):
 if state()['dirty']:raise ValueError('Clean source commit required')
 for p in [ART/'tests-v3/contracts.log',ART/'tests-v3/frozen.log',ART/'tests-v3/phase0.log',ART/'tests-v3/index.log']:
  if not p.read_text().rstrip().endswith('OK'):raise ValueError('Tests must pass first')
 if (root/'RUN_PLAN.json').exists():raise FileExistsError('Immutable plan exists')
 binding=json.loads((root/'INPUT_BINDINGS.json').read_text());cells=[]
 for s in SCENARIOS:
  case=s+'_seed101'
  for m in METHODS:
   reuse=m in ['I','J'];derived=m.startswith('C');path=('reused/' if reuse else 'derived/' if derived else 'runs/')+case+'__'+m
   c=dict(id=case+'__'+m,case=case,scenario=s,seed=101,method=m,status='REUSED_VERIFIED' if reuse else 'PLANNED',kind='reuse' if reuse else 'derived' if derived else 'new',path=path,input_sha256=binding['cases'][case])
   if reuse:c['run_sha256']=sha(root/path/'run.json')
   cells.append(c)
 index=dict(status='FROZEN',**state(),config=CONFIG,source_sha256=sources(),cells=cells,input_bindings_sha256=sha(root/'INPUT_BINDINGS.json'),tests={p.name:sha(p) for p in [ART/'tests-v3/contracts.log',ART/'tests-v3/frozen.log',ART/'tests-v3/phase0.log',ART/'tests-v3/index.log']})
 validate(index);dump(root/'RUN_PLAN.json',index);dump(root/'RUN_INDEX.json',index)
 for p in index['source_sha256']:
  dst=root/'source'/p;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/p,dst)

def derive(root,case,method,config):
 j=read(root/f'reused/{case}__J/updates.jsonl.gz');i=read(root/f'reused/{case}__I/updates.jsonl.gz');out=[];budget=.04 if method=='C004' else 1.
 for joint,ref in zip(j,i):
  start=time.perf_counter();assert joint['state_epoch_ns']==ref['state_epoch_ns'] and joint['availability_cutoff_epoch_ns']==ref['availability_cutoff_epoch_ns'];row=copy.deepcopy(joint)
  known=ref['accepted_graph'] and ref['pose'] is not None;main=joint['pose'];published=None if main is None else clip_pose(main,ref['pose'],config,budget);changed=main is not None and not np.array_equal(main,published)
  mode='post_clip' if changed else 'normal_joint';reason='RADIAL_ANTENNA_XY_CLIP' if changed else 'UNCHANGED'
  if not known:mode='unknown';reason='REFERENCE_NOT_ACCEPTED';published=ref['pose']
  elif not joint['accepted_graph']:mode='reference_fallback';reason='SOURCE_JOINT_FAILURE';published=ref['pose']
  success=bool(known and joint['accepted_graph'] and not changed)
  row.update(method_id=method,reference=copy.deepcopy(ref),main_pose=main,main_accepted_graph=joint['accepted_graph'],main_status=joint['status'],pose=published,
   accepted_graph=success,joint_optimization_success=success,publication_mode=mode,publication_reason=reason,reference_accepted=bool(known),budget_m=budget,budget_certified=bool(known and published is not None),
   published_separation_m=None if published is None else np.linalg.norm(antennas(published,config)-antennas(ref['pose'],config),axis=1).tolist(),covariance=None,peer_information_weight=1.,
   clip_wall_s=time.perf_counter()-start,main_update_wall_s=joint['update_wall_s'],reference_update_wall_s=ref['update_wall_s'],timing_origin='historical_J_and_I_plus_current_clip_only')
  out.append(row)
 return out

def run(root):
 index=json.loads((root/'RUN_INDEX.json').read_text());validate(index)
 if index['status']!='FROZEN' or state()['dirty'] or sources()!=index['source_sha256']:raise ValueError('Freeze/check source; no retries or changed source')
 index['status']='RUNNING';dump(root/'RUN_INDEX.json',index)
 for c in index['cells']:
  if c['kind']=='reuse':continue
  inp=root/'inputs'/c['case'];out=root/c['path'];out.mkdir(parents=True,exist_ok=False);started=time.perf_counter();c['status']='RUNNING';dump(root/'RUN_INDEX.json',index)
  for name,s in c['input_sha256'].items():assert sha(inp/name)==s
  config=json.loads((inp/'config.json').read_text());rows=[]
  meta=dict(status='RUNNING',**state(),id=c['id'],kind=c['kind'],input_sha256=c['input_sha256'],source_sha256=index['source_sha256'],timing='virtual; not ROS real-time latency',test_only_fault_injection=False)
  dump(out/'run.json',meta)
  try:
   if c['kind']=='derived':rows=derive(root,c['case'],c['method'],config);meta['estimator_runs']=0
   else:
    worker=execute(read(inp/'events.jsonl.gz'),config,c['method'],rows.append);meta.update(estimator_runs=1,private_independent_reference_runs=1,peak_solve_states=worker.graph.peak_solve_states,peak_transient_states=worker.graph.peak_transient_states)
   assert len(rows)==63;write(out/'updates.jsonl.gz',rows);shutil.copyfile(inp/'config.json',out/'config.json');dump(out/'summary.json',dict(publications=len(rows),publication_modes=dict(Counter(r['publication_mode'] for r in rows)),reasons=dict(Counter(r['publication_reason'] for r in rows)),joint_optimization_success=sum(r['joint_optimization_success'] for r in rows)))
   meta.update(status='DONE',elapsed_wall_s=time.perf_counter()-started,outputs={p.name:dict(sha256=sha(p),size_bytes=p.stat().st_size) for p in out.iterdir() if p.name!='run.json'})
   dump(out/'run.json',meta);c.update(status='DONE',run_sha256=sha(out/'run.json'));print(c['id'],meta['kind'],'DONE',flush=True)
  except BaseException as err:
   meta.update(status='FAILED',error=str(err));dump(out/'run.json',meta);c['status']='FAILED';index['status']='FAILED';dump(root/'RUN_INDEX.json',index);raise
  assert sources()==index['source_sha256'];dump(root/'RUN_INDEX.json',index)
 index['status']='DONE';validate(index,True);dump(root/'RUN_INDEX.json',index)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--root',type=Path,default=ART/'evidence-v1');a=p.parse_args();freeze(a.root) if a.phase=='freeze' else run(a.root)
