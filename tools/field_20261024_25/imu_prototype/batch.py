#!/usr/bin/env python3
"""Finite frozen matrix with exact-source resume and per-CLI checkpoints."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from configuration import MODES, with_mode
from io_utils import ROOT,HERE,dump,external_path,git_state,outputs,packages,sha,sources,utc
from simulate import save
from evaluate import summarize,csv_write


def fingerprint():
    return dict(source_sha256=sources(), protocol_sha256=sha(HERE/'protocol.json'))


def verify_completed(root,cell):
    for entry in cell.get('outputs',[]):
        p=root/entry['relative_path']
        if not p.is_file() or sha(p)!=entry['sha256']: raise ValueError('completed evidence changed: '+str(p))
    for entry in cell.get('inputs',[]):
        p=root/entry['relative_path']
        if sha(p)!=entry['sha256']: raise ValueError('input changed: '+str(p))


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--resume',action='store_true'); parser.add_argument('--smoke',action='store_true'); a=parser.parse_args(argv)
    started=time.monotonic(); root=external_path(a.output); protocol=json.loads((HERE/'protocol.json').read_text()); lock=fingerprint()
    if a.resume:
        state=json.loads((root/'checkpoint.json').read_text())
        if state['fingerprint']!=lock or state['smoke']!=a.smoke: raise ValueError('resume source/protocol fingerprint mismatch')
        for cell in state['cells']: verify_completed(root,cell)
    else:
        root.mkdir(parents=True,exist_ok=False)
        state=dict(role='A_IMU_synthetic_matrix',status='IN_PROGRESS',created_at_utc=utc(),**git_state(),fingerprint=lock,smoke=a.smoke,cells=[],commands=[],environment=dict(python=sys.version,packages=packages()),elapsed_s=0.)
        for path in lock['source_sha256']:
            target=root/'source'/path; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(ROOT/path,target)
        dump(root/'protocol.json',protocol); dump(root/'checkpoint.json',state)
    scenes=['nominal'] if a.smoke else protocol['scenarios']; seeds=[101] if a.smoke else protocol['seeds']; duration=2_000_000_000 if a.smoke else protocol['duration_ns']
    complete={c['cell_id'] for c in state['cells']}; prior_elapsed=state['elapsed_s']; budget=protocol['budgets']['max_batch_seconds']
    for scene in scenes:
        for seed in seeds:
            input_dir=root/'inputs'/f'{scene}_seed{seed}'
            if not input_dir.exists(): save(input_dir,scene,seed,duration)
            cfg=json.loads((input_dir/'config.template.json').read_text())
            for mode in MODES:
                cell_id=f'{scene}_seed{seed}__{mode}'
                if cell_id in complete: continue
                if time.monotonic()-started+prior_elapsed>budget:
                    state.update(status='TIMEOUT',elapsed_s=time.monotonic()-started+prior_elapsed); dump(root/'checkpoint.json',state); return 3
                output=root/'runs'/cell_id; config_path=input_dir/(mode+'.json')
                if output.exists(): raise ValueError('unindexed partial cell; inspect and preserve: '+str(output))
                dump(config_path,with_mode(cfg,mode))
                command=[sys.executable,str(HERE/'replay.py'),'--events-jsonl',str(input_dir/'events.jsonl.gz'),'--config',str(config_path),'--output',str(output),'--max-seconds',str(protocol['budgets']['max_cli_seconds'])]
                before=time.monotonic(); logfile=root/'logs'/(cell_id+'.log'); logfile.parent.mkdir(exist_ok=True)
                with logfile.open('x') as log:
                    try: result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=protocol['budgets']['max_cli_seconds']+5); code=result.returncode
                    except subprocess.TimeoutExpired: code=124
                elapsed=time.monotonic()-before
                run_json=json.loads((output/'run.json').read_text()) if (output/'run.json').exists() else {}
                cell=dict(cell_id=cell_id,scenario=scene,seed=seed,motion_mode=mode,returncode=code,status=run_json.get('status','FAILED'),elapsed_s=elapsed,
                    output=str(output.relative_to(root)),command_argv=command,log=str(logfile.relative_to(root)),
                    inputs=[dict(relative_path=str(p.relative_to(root)),sha256=sha(p)) for p in [input_dir/'events.jsonl.gz',input_dir/'truth.jsonl.gz',input_dir/'labels.json',config_path]],
                    outputs=[dict(relative_path=str(p.relative_to(root)),sha256=sha(p)) for p in sorted(output.rglob('*')) if p.is_file()])
                state['cells'].append(cell); state['commands'].append(dict(argv=command,returncode=code,elapsed_s=elapsed,finished_at_utc=utc()))
                state.update(elapsed_s=time.monotonic()-started+prior_elapsed,updated_at_utc=utc()); dump(root/'checkpoint.json',state)
                print(json.dumps({k:cell[k] for k in ['cell_id','status','returncode','elapsed_s']}),flush=True)
    metrics=[]; evaluation_errors=[]
    for cell in state['cells']:
        if cell['status']!='DONE': continue
        try:
            source=root/'inputs'/f"{cell['scenario']}_seed{cell['seed']}"
            m,series=summarize(root/cell['output'],source/'truth.jsonl.gz',cell['scenario'],cell['seed']); metrics+=m
            target=root/cell['output']/'synthetic_timeseries.csv'
            if not target.exists(): csv_write(target,series)
        except Exception as error: evaluation_errors.append(dict(cell_id=cell['cell_id'],error=repr(error)))
    if not (root/'metrics.csv').exists(): csv_write(root/'metrics.csv',metrics)
    state.update(status='DONE' if all(c['status']=='DONE' for c in state['cells']) and not evaluation_errors else 'COMPLETED_WITH_FAILURES',
                 evaluation_errors=evaluation_errors,metric_rows=len(metrics),elapsed_s=time.monotonic()-started+prior_elapsed,finished_at_utc=utc())
    dump(root/'checkpoint.json',state); print(json.dumps(dict(status=state['status'],cells=len(state['cells']),metric_rows=len(metrics),elapsed_s=state['elapsed_s'])))
    return 0 if state['status']=='DONE' else 1


if __name__=='__main__': raise SystemExit(main())
