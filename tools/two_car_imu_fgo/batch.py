#!/usr/bin/env python3
"""Freeze complete bounded index before execution; no overwrite/resume/retry."""
import argparse
import json
from pathlib import Path
import shutil
import time
from configuration import default_config
from io_utils import dump,external,git_state,sha,sources,utc
from simulate import save,SCENARIOS,SEEDS
from replay import run

ARMS=('M0','M1','M2','M3')


def freeze(root,test_log):
    root=external(root);root.mkdir(exist_ok=False)
    receipt=Path(test_log).read_text()
    if not receipt.rstrip().endswith('OK'):raise ValueError('tests not PASS')
    state=git_state()
    if state['worktree_dirty']:raise ValueError('freeze committed clean source')
    inputs={}
    for s in SCENARIOS:
        for seed in SEEDS:
            key=f'{s}_seed{seed}';save(root/'inputs'/key,seed,s);inputs[key]={p.name:sha(p) for p in (root/'inputs'/key).iterdir()}
    index=dict(schema_version=1,status='FROZEN',created_at_utc=utc(),**state,source_sha256=sources(),
        test_receipt_sha256=sha(test_log),inputs=inputs,cells=[])
    for s in SCENARIOS:
        for seed in SEEDS:
            for arm in ARMS:index['cells'].append(dict(case=f'{s}_seed{seed}',scenario=s,seed=seed,method=arm,
                run_id=f'{s}_seed{seed}_{arm}',status='PLANNED',input_sha256=inputs[f'{s}_seed{seed}']['events.jsonl.gz'],
                config_sha256=inputs[f'{s}_seed{seed}']['config.json']))
    dump(root/'RUN_PLAN.json',index);dump(root/'RUN_INDEX.json',index)
    for name in index['source_sha256']:
        src=Path(__file__).resolve().parents[2]/name;dst=root/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    return index


def execute(root):
    root=Path(root);index=json.loads((root/'RUN_INDEX.json').read_text());require={f'{s}_seed{seed}_{a}' for s in SCENARIOS for seed in SEEDS for a in ARMS}
    if len(index['cells'])!=40 or {c['run_id'] for c in index['cells']}!=require:raise ValueError('full 40 index required')
    if any(c['status']!='PLANNED' for c in index['cells']):raise ValueError('no resume/retry; preserve old outputs')
    if git_state()['worktree_dirty'] or sources()!=index['source_sha256']:raise ValueError('frozen source changed')
    for cell in index['cells']:
        if sources()!=index['source_sha256']:raise ValueError('source changed')
        src=root/'inputs'/cell['case'];out=root/'runs'/cell['run_id'];out.parent.mkdir(exist_ok=True)
        if sha(src/'events.jsonl.gz')!=cell['input_sha256'] or sha(src/'config.json')!=cell['config_sha256']:raise ValueError('input/config changed')
        cell.update(status='IN_PROGRESS',started_at_utc=utc());dump(root/'RUN_INDEX.json',index)
        try:
            result=run(src/'events.jsonl.gz',src/'config.json',cell['method'],out)
            cell.update(status=result['status'],run_sha256=sha(out/'run.json'),elapsed_s=result['elapsed_s'])
        except Exception as error:
            cell.update(status='FAILED',error=str(error));dump(root/'RUN_INDEX.json',index);raise
        dump(root/'RUN_INDEX.json',index);print(cell['run_id'],cell['status'],flush=True)
    index['status']='DONE';dump(root/'RUN_INDEX.json',index)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--root',type=Path,required=True);p.add_argument('--test-log',type=Path)
    a=p.parse_args();freeze(a.root,a.test_log) if a.phase=='freeze' else execute(a.root)
