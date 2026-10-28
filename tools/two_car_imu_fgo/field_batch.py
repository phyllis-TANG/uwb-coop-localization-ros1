#!/usr/bin/env python3
"""Exactly two registered old development bags x four models, once each."""
import argparse
import json
from pathlib import Path
import shutil
from io_utils import dump,external,git_state,sha,sources,utc,ROOT
from replay import run
from field_inputs import OLD

ARMS=('M0','M1','M2','M3')


def freeze(inputs,root,test_log):
    inputs=Path(inputs);root=external(root);root.mkdir(exist_ok=False)
    state=git_state()
    if state['worktree_dirty'] or not Path(test_log).read_text().rstrip().endswith('OK'):raise ValueError('clean committed tested source required')
    cells=[]
    for case in OLD:
        receipt=json.loads((inputs/(case+'_readback.json')).read_text())
        if receipt['status']!='PASS':raise ValueError('raw packet readback')
        for method in ARMS:
            cells.append(dict(case=case,method=method,run_id=case+'_'+method,status='PLANNED',
                input_sha256=sha(inputs/case/'events.jsonl.gz'),config_sha256=sha(inputs/case/'config.json'),
                original_bag_sha256=OLD[case]['sha256'],raw_readback_sha256=sha(inputs/(case+'_readback.json'))))
    plan=dict(stage='B',execution_level='conditional_development',strict_physical_branch='BLOCKED',status='FROZEN',
        inputs_root=str(inputs),**state,source_sha256=sources(),test_log_sha256=sha(test_log),created_at_utc=utc(),cells=cells,
        excluded=['T08/T10 not run in this index','no holdouts, no videos, no endpoint fitting'],
        timing='virtual recorder receipt-prefix; source sampling clock and physical synchronization unvalidated')
    dump(root/'RUN_PLAN.json',plan);dump(root/'RUN_INDEX.json',plan)
    for name in plan['source_sha256']:
        dst=root/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)


def execute(root):
    root=Path(root);plan=json.loads((root/'RUN_INDEX.json').read_text());cells=plan['cells'];inputs=Path(plan['inputs_root'])
    if len(cells)!=8 or {c['run_id'] for c in cells}!={c+'_'+m for c in OLD for m in ARMS}:raise ValueError('complete index')
    if any(c['status']!='PLANNED' for c in cells):raise ValueError('no retry/resume/overwrite')
    if git_state()['worktree_dirty'] or sources()!=plan['source_sha256']:raise ValueError('frozen source changed')
    for cell in cells:
        src=inputs/cell['case'];dst=root/'runs'/cell['run_id'];dst.parent.mkdir(exist_ok=True)
        if sha(src/'events.jsonl.gz')!=cell['input_sha256'] or sha(src/'config.json')!=cell['config_sha256']:raise ValueError('paired input changed')
        if sources()!=plan['source_sha256']:raise ValueError('source changed')
        cell['status']='IN_PROGRESS';dump(root/'RUN_INDEX.json',plan)
        try:
            result=run(src/'events.jsonl.gz',src/'config.json',cell['method'],dst)
            cell.update(status=result['status'],run_sha256=sha(dst/'run.json'),elapsed_s=result['elapsed_s'])
        except Exception as error:
            cell.update(status='FAILED',error=str(error));dump(root/'RUN_INDEX.json',plan);raise
        dump(root/'RUN_INDEX.json',plan);print(cell['run_id'],cell['status'],flush=True)
    plan['status']='DONE';dump(root/'RUN_INDEX.json',plan)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run']);p.add_argument('--root',type=Path,required=True);p.add_argument('--inputs',type=Path);p.add_argument('--test-log',type=Path)
    a=p.parse_args();freeze(a.inputs,a.root,a.test_log) if a.phase=='freeze' else execute(a.root)
