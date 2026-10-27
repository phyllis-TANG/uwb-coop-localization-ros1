#!/usr/bin/env python3
"""Finite development/previously-unseen paced validation, four independent Q runs."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from qconfig import default
from qsimulate import save
from qevaluate import evaluate_case,csv_write
from qio import ROOT,HERE,dump,external_path,git_state,packages,sha,sources,utc


def fingerprint():return dict(source_sha256=sources(),protocol_sha256=sha(HERE/'protocol.json'))


def verify(root,cell):
    for entry in cell.get('inputs',[])+cell.get('outputs',[]):
        p=root/entry['relative_path']
        if not p.is_file() or sha(p)!=entry['sha256']:raise ValueError('completed evidence SHA mismatch: '+str(p))


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['development','validation'],required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();start=time.monotonic();root=external_path(a.output);protocol=json.loads((HERE/'protocol.json').read_text());plan=protocol[a.stage];lock=fingerprint()
    if a.resume:
        state=json.loads((root/'checkpoint.json').read_text())
        if state['fingerprint']!=lock or state['stage']!=a.stage:raise ValueError('resume source/protocol mismatch')
        for c in state['cells']:verify(root,c)
    else:
        root.mkdir(parents=True,exist_ok=False);state=dict(status='IN_PROGRESS',created_at_utc=utc(),stage=a.stage,**git_state(),fingerprint=lock,cells=[],elapsed_s=0.,environment=dict(python=sys.version,packages=packages()),command_argv=[sys.executable,__file__]+sys.argv[1:])
        for relative in lock['source_sha256']:
            target=root/'source'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/relative,target)
        shutil.copyfile(HERE/'protocol.json',root/'protocol.json');dump(root/'checkpoint.json',state)
    completed={c['cell_id'] for c in state['cells']};prior_elapsed=state['elapsed_s'];logs=root/'logs';logs.mkdir(exist_ok=True)
    for scene in plan['scenarios']:
        for seed in plan['seeds']:
            if time.monotonic()-start+prior_elapsed>protocol['budgets']['max_validation_batch_seconds']:
                state.update(status='TIMEOUT',elapsed_s=time.monotonic()-start+prior_elapsed);dump(root/'checkpoint.json',state);return 3
            inp=root/'inputs'/f'{scene}_seed{seed}'
            if not inp.exists():save(inp,scene,seed,protocol['duration_ns'])
            base=json.loads((inp/'base.template.json').read_text());jobs=[];anchor=time.monotonic_ns()+2_000_000_000;epoch=time.time_ns()+2_000_000_000
            for group in ['Q0','Q1','Q2','Q3']:
                cid=f'{scene}_seed{seed}__{group}'
                if cid in completed:continue
                output=root/'runs'/cid
                if output.exists():raise ValueError('unindexed partial run preserved; no implicit restart: '+str(output))
                config=default(group);config['base']=json.loads(json.dumps(base));config['base']['arm']='F3' if group in ('Q1','Q3') else 'F0';config['timing']['paced']=plan['paced'];config['timing']['scope']=a.stage
                config_path=inp/(group+'.json');dump(config_path,config)
                command=[sys.executable,str(HERE/'qrun.py'),'--events-jsonl',str(inp/'events.jsonl.gz'),'--config',str(config_path),'--output',str(output),'--max-seconds',str(protocol['budgets']['max_cli_seconds'])]
                if plan['paced']:command+=['--anchor-monotonic-ns',str(anchor),'--anchor-host-epoch-ns',str(epoch)]
                stream=(logs/(cid+'.log')).open('x');process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1'));jobs.append((cid,group,process,stream,command,config_path,time.monotonic()))
            for cid,group,process,stream,command,cfg,before in jobs:
                try:code=process.wait(timeout=max(1,protocol['budgets']['max_cli_seconds']+5-(time.monotonic()-before)))
                except subprocess.TimeoutExpired:process.kill();process.wait();code=124
                stream.close();output=root/'runs'/cid;meta=json.loads((output/'run.json').read_text()) if (output/'run.json').exists() else {};cell=dict(cell_id=cid,scenario=scene,seed=seed,group=group,returncode=code,status=meta.get('status','FAILED'),elapsed_s=meta.get('elapsed_s',time.monotonic()-before),coordinator_waited_elapsed_s=time.monotonic()-before,
                    output=str(output.relative_to(root)),command_argv=command,finished_at_utc=utc(),inputs=[dict(relative_path=str(p.relative_to(root)),sha256=sha(p)) for p in [inp/'events.jsonl.gz',inp/'truth.jsonl.gz',inp/'labels.json',cfg]],
                    outputs=[dict(relative_path=str(p.relative_to(root)),sha256=sha(p)) for p in sorted(output.rglob('*')) if p.is_file()])
                state['cells'].append(cell);state.update(elapsed_s=time.monotonic()-start+prior_elapsed,updated_at_utc=utc());dump(root/'checkpoint.json',state);print(json.dumps({k:cell[k] for k in ['cell_id','status','returncode','elapsed_s']}),flush=True)
    metrics=[];links=[];events=[];diagnostics=[];errors=[]
    for scene in plan['scenarios']:
        for seed in plan['seeds']:
            try:
                m,l,e,series,d=evaluate_case(root,scene,seed);metrics+=m;links+=l;events+=e;diagnostics+=d
                for group,rows in series.items():
                    target=root/'runs'/f'{scene}_seed{seed}__{group}'/'truth_evaluation.csv'
                    if not target.exists():csv_write(target,rows)
            except Exception as error:errors.append(dict(scenario=scene,seed=seed,error=repr(error)))
    for name,rows in [('metrics.csv',metrics),('quality_link_metrics.csv',links),('fault_events.csv',events),('factor_timeline.csv',diagnostics)]:
        if not(root/name).exists():csv_write(root/name,rows)
    state.update(status='DONE' if not errors and all(c['status']=='DONE' for c in state['cells']) else 'COMPLETED_WITH_FAILURES',evaluation_errors=errors,metric_rows=len(metrics),elapsed_s=time.monotonic()-start+prior_elapsed,finished_at_utc=utc());dump(root/'checkpoint.json',state);print(json.dumps(dict(status=state['status'],cells=len(state['cells']),metric_rows=len(metrics),elapsed_s=state['elapsed_s'])));return 0 if state['status']=='DONE' else 1


if __name__=='__main__':raise SystemExit(main())
