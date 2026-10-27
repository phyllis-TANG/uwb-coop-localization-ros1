#!/usr/bin/env python3
"""Finite F0-F3 source-locked matrix; no automatic retries or result overwrites."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from configuration import ARMS
from io_utils import ROOT,HERE,dump,external_path,git_state,packages,sha,sources,utc
from simulate import save
from evaluate import evaluate_case,csv_write


def fingerprint():return dict(source_sha256=sources(),protocol_sha256=sha(HERE/'protocol.json'))


def verify_completed(root,cell):
    for entry in cell['inputs']+cell['outputs']:
        p=root/entry['relative_path']
        if not p.is_file() or sha(p)!=entry['sha256']:raise ValueError('indexed evidence SHA mismatch: '+str(p))


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--smoke',action='store_true');a=p.parse_args();started=time.monotonic();root=external_path(a.output);protocol=json.loads((HERE/'protocol.json').read_text());lock=fingerprint()
    if a.resume:
        state=json.loads((root/'checkpoint.json').read_text())
        if state['fingerprint']!=lock or state['smoke']!=a.smoke:raise ValueError('source/protocol lock mismatch')
        for cell in state['cells']:verify_completed(root,cell)
    else:
        root.mkdir(parents=True,exist_ok=False);state=dict(status='IN_PROGRESS',created_at_utc=utc(),**git_state(),fingerprint=lock,smoke=a.smoke,cells=[],elapsed_s=0.,environment=dict(python=sys.version,packages=packages()),command_argv=[sys.executable,__file__]+sys.argv[1:])
        for path in lock['source_sha256']:
            target=root/'source'/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
        dump(root/'protocol.json',protocol);dump(root/'checkpoint.json',state)
    scenes=['nominal','imu_gap'] if a.smoke else protocol['scenarios'];seeds=[101] if a.smoke else protocol['seeds'];duration=26_000_000_000 if a.smoke else protocol['duration_ns'];done={c['cell_id'] for c in state['cells']};prior_elapsed=state['elapsed_s']
    for scene in scenes:
        for seed in seeds:
            input_dir=root/'inputs'/f'{scene}_seed{seed}'
            if not input_dir.exists():save(input_dir,scene,seed,duration)
            template=json.loads((input_dir/'template.json').read_text())
            for arm in ARMS:
                cid=f'{scene}_seed{seed}__{arm}'
                if cid in done:continue
                if time.monotonic()-started+prior_elapsed>protocol['budgets']['max_batch_seconds']:
                    state.update(status='TIMEOUT',elapsed_s=time.monotonic()-started+prior_elapsed);dump(root/'checkpoint.json',state);return 3
                output=root/'runs'/cid
                if output.exists():raise ValueError('unindexed partial cell preserved; inspect: '+str(output))
                config_path=input_dir/(arm+'.json');cfg=dict(template,arm=arm);dump(config_path,cfg);logs=root/'logs';logs.mkdir(exist_ok=True);log=logs/(cid+'.log')
                command=[sys.executable,str(HERE/'replay.py'),'--events-jsonl',str(input_dir/'events.jsonl.gz'),'--config',str(config_path),'--output',str(output),'--max-seconds',str(protocol['budgets']['max_cli_seconds'])]
                before=time.monotonic()
                with log.open('x') as stream:
                    try:r=subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,timeout=protocol['budgets']['max_cli_seconds']+5);code=r.returncode
                    except subprocess.TimeoutExpired:code=124
                meta=json.loads((output/'run.json').read_text()) if (output/'run.json').exists() else {};elapsed=time.monotonic()-before
                cell=dict(cell_id=cid,scenario=scene,seed=seed,arm=arm,status=meta.get('status','FAILED'),returncode=code,elapsed_s=elapsed,output=str(output.relative_to(root)),command_argv=command,finished_at_utc=utc(),log=str(log.relative_to(root)),
                    inputs=[dict(relative_path=str(f.relative_to(root)),sha256=sha(f)) for f in [input_dir/'events.jsonl.gz',input_dir/'truth.jsonl.gz',input_dir/'labels.json',config_path]],
                    outputs=[dict(relative_path=str(f.relative_to(root)),sha256=sha(f)) for f in sorted(output.rglob('*')) if f.is_file()])
                state['cells'].append(cell);state.update(updated_at_utc=utc(),elapsed_s=time.monotonic()-started+prior_elapsed);dump(root/'checkpoint.json',state)
                print(json.dumps({k:cell[k] for k in ['cell_id','status','returncode','elapsed_s']}),flush=True)
    metrics=[];errors=[]
    for scene in scenes:
        for seed in seeds:
            try:
                rows,series=evaluate_case(root,scene,seed);metrics+=rows
                for arm,points in series.items():
                    target=root/'runs'/f'{scene}_seed{seed}__{arm}'/'synthetic_timeseries.csv'
                    if not target.exists():csv_write(target,points)
            except Exception as error:errors.append(dict(scenario=scene,seed=seed,error=repr(error)))
    if not(root/'metrics.csv').exists():csv_write(root/'metrics.csv',metrics)
    state.update(status='DONE' if all(c['status']=='DONE' for c in state['cells']) and not errors else 'COMPLETED_WITH_FAILURES',evaluation_errors=errors,metric_rows=len(metrics),elapsed_s=time.monotonic()-started+prior_elapsed,finished_at_utc=utc());dump(root/'checkpoint.json',state)
    print(json.dumps(dict(status=state['status'],cells=len(state['cells']),metric_rows=len(metrics),elapsed_s=state['elapsed_s'])));return 0 if state['status']=='DONE' else 1


if __name__=='__main__':raise SystemExit(main())
