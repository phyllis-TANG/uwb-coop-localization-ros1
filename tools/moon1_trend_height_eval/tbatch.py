"""One-pass pre-frozen A+B plan, no duplicate sigma=0 solves or automatic retries."""
import argparse,time,importlib.metadata
from tcommon import *
from tinputs import tracks,make,verify,plan

def run(out,mode,freeze,acceptance):
 cfg=read(DOC/'CONFIG.json');seeds=read(DOC/'SEEDS.json');sc=read(DOC/'SOLVER.json')
 if mode=='explore':
  assert git('rev-parse','HEAD')==freeze and not git('status','--porcelain')
  acc=read(acceptance);assert acc['passed'] and acc['source_sha256']==sources()
 allplan=plan(seeds['seeds'] if mode=='explore' else [seeds['development_seed']])
 if mode=='development':allplan=[r for r in allplan if r['window']==0]
 assert len(allplan)*4==(1920 if mode=='explore' else 32)
 if mode=='explore':assert allplan==read(DOC/'INPUT_PLAN.json')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);tt,source=tracks();began=time.perf_counter()
 with lock(out/'RUN_LOCK'):
  write(out/'FREEZE.json',dict(commit=git('rev-parse','HEAD'),source_sha256=sources(),config=cfg,seeds=seeds,solver=sc,input_source=source,mode=mode,python=sys.version,packages={p:importlib.metadata.version(p) for p in ['numpy','scipy','matplotlib']},argv=sys.argv,acceptance_sha256=filehash(acceptance) if acceptance else None))
  write(out/'EXECUTION.json',dict(commit=git('rev-parse','HEAD'),source_sha256=sources(),solver=sc))
  write(out/'PLAN.json',allplan);write(out/'BUDGET.json',dict(limit=3840 if mode=='explore' else 64,development_overall_limit=192,exploration_limit=3840,total_authorized_limit=4032))
  for item in allplan:
   condition=next(c for c in cfg['conditions'] if c['id']==item['condition']);o,r=make(tt[item['window']],cfg,condition,item['seed'],item['height_sigma_m']);verify(o,r)
   mp=out/'measurements'/(item['id']+'.json');write(mp,o);write(out/'reference'/(item['id']+'.json'),r)
   cmd=[sys.executable,str(ROOT/'tools/moon1_trend_height_eval/tengine.py'),'--measurement',str(mp),'--root',str(out),'--unit',item['id']]
   write(out/'dispatch'/(item['id']+'.attempt.json'),dict(argv=cmd,input_sha256=filehash(mp),code_sha=git('rev-parse','HEAD')))
   proc=subprocess.run(cmd,capture_output=True,text=True,cwd=ROOT);write(out/'dispatch'/(item['id']+'.result.json'),dict(returncode=proc.returncode,stdout=proc.stdout,stderr=proc.stderr))
   if proc.returncode:write(out/'failures'/(item['id']+'.json'),dict(status='PROCESS_FAILURE',no_retry=True))
  attempts=list((out/'attempts').glob('*.json'));results=list((out/'estimates').glob('*/P?.json'));assert len(attempts)<=read(out/'BUDGET.json')['limit']
  write(out/'RUN.json',dict(planned_methods=len(allplan)*4,unique_methods=len({(r['window'],r['seed'],r['condition'],r['height_sigma_m'],m) for r in allplan for m in cfg['methods']}),completed_methods=len(list((out/'estimates').glob('*/FINAL.json'))),reserved_calls=len(attempts),completed_calls=len(results),orphan_attempts=len(attempts)-len(results),formal_runs=0,elapsed_s=time.perf_counter()-began,source_unchanged=sources()==read(out/'FREEZE.json')['source_sha256']))
  print('Completed',mode,len(allplan)*4,'methods',len(attempts),'calls')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--mode',choices=['development','explore'],required=True);p.add_argument('--freeze');p.add_argument('--acceptance');a=p.parse_args();run(a.out,a.mode,a.freeze,a.acceptance)
