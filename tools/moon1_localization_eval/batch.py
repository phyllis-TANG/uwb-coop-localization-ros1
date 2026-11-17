#!/usr/bin/env python3
"""Freeze-gated 180-run smoke batch; generation and solver use separate files/processes."""
import argparse,subprocess,sys,importlib.metadata,time
from pathlib import Path
from common import ROOT,DOC,read,write,git,sources,filehash,digest
from generate import tracks,make_input

def run(scene,out,acceptance,freeze):
 if git('rev-parse','HEAD')!=freeze or git('status','--porcelain'):raise ValueError('Requires exact clean freeze checkout')
 acc=read(acceptance)
 if not acc['passed'] or acc['source_sha256']!=sources():raise ValueError('Acceptance/source mismatch')
 cfg=read(DOC/'CONFIG.json');tt,asset=tracks(scene,cfg)
 if asset!=acc['asset']:raise ValueError('Asset identity mismatch')
 if len(cfg['seeds'])!=5 or len(set(cfg['seeds']))!=5:raise ValueError('Exactly five distinct seeds required')
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 write(out/'FREEZE.json',dict(commit=freeze,source_sha256=sources(),config=cfg,solver_config=read(DOC/'SOLVER.json'),acceptance_sha256=filehash(acceptance),asset=asset,argv=sys.argv,python=sys.version,packages={k:importlib.metadata.version(k) for k in ['numpy','scipy','matplotlib']},scope='smoke, not formal coverage confirmation'))
 plan=[]
 for track in tt:
  for seed in cfg['seeds']:
   for condition in cfg['conditions']:
    plan.append(dict(id=f'u{len(plan):03}',window=track['window'],seed=seed,condition=condition['id'],methods=cfg['methods']))
 assert len(plan)*3==180;write(out/'PLAN.json',plan)
 commands=[];calls=0;began=time.perf_counter()
 for item in plan:
  condition=next(c for c in cfg['conditions'] if c['id']==item['condition'])
  obs,ref=make_input(tt[item['window']],cfg,condition,item['seed'])
  measurement=out/'measurements'/f"{item['id']}.json";write(measurement,obs);write(out/'reference'/f"{item['id']}.json",ref)
  for method in item['methods']:
   target=out/'estimates'/f"{item['id']}-{method}.json"
   cmd=[sys.executable,str(ROOT/'tools/moon1_localization_eval/solve.py'),'--measurement',str(measurement),'--method',method,'--solver-config',str(DOC/'SOLVER.json'),'--out',str(target)]
   result=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
   if result.returncode or not target.exists():
    write(target,dict(method=method,status='PROCESS_FAILURE',accepted=False,estimate=None,optimizer_calls=None,stderr=result.stderr,returncode=result.returncode))
   record=read(target);calls+=record.get('optimizer_calls') or 0
   commands.append(dict(argv=cmd,returncode=result.returncode,unit=item['id'],method=method,optimizer_calls=record.get('optimizer_calls')))
   with (out/'EVENTS.jsonl').open('a') as f:
    import json
    f.write(json.dumps(dict(unit=item['id'],method=method,status=record['status'],completed=True))+'\n')
 write(out/'COMMANDS.json',commands)
 assert filehash(scene)==asset['sha256'],'PR114 source changed'
 write(out/'RUN.json',dict(commit=freeze,units=len(plan),planned_methods=180,completed_methods=len(commands),optimizer_calls=calls,unknown_call_count=sum(c['optimizer_calls'] is None for c in commands),elapsed_s=time.perf_counter()-began,formal_runs=0,smoke_runs=len(commands),source_unchanged=True,source_sha256=sources(),files={str(p.relative_to(out)):filehash(p) for p in out.rglob('*.json')},measurements_reference_estimates_separate=True))
 print('Completed',len(commands),'smoke methods;',calls,'optimizer calls')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scene',required=True,type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--acceptance',required=True,type=Path);p.add_argument('--freeze',required=True);a=p.parse_args();run(a.scene,a.out,a.acceptance,a.freeze)
