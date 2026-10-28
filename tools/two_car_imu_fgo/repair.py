#!/usr/bin/env python3
"""BUG01 only: freeze four necessary repair executions, preserve all v1 evidence."""
import argparse
import json
from pathlib import Path
import shutil
from io_utils import dump,external,git_state,sha,sources,utc,ROOT
from replay import run


def freeze(artifacts,root,test_log):
    a=Path(artifacts);root=external(root);root.mkdir(exist_ok=False);state=git_state()
    if state['worktree_dirty'] or not Path(test_log).read_text().rstrip().endswith('OK'):raise ValueError('clean tested commit required')
    cells=[]
    for original,inputs,ids in [
        ('synthetic-v1','synthetic-v1/inputs',[f'car1_gyro_gap_seed{s}_M2' for s in (101,211)]),
        ('old-matrix-v1','old-inputs-v2',['015334_M2','033248_M2'])]:
        index=json.loads((a/original/'RUN_INDEX.json').read_text())
        for rid in ids:
            old=next(c for c in index['cells'] if c['run_id']==rid);cell=dict(old)
            for k in ('run_sha256','elapsed_s'):cell.pop(k,None)
            cell.update(status='PLANNED',original_run=str(a/original/'runs'/rid),original_run_sha256=old['run_sha256'],
                        input_directory=str(a/inputs/old['case']),reason='BUG01 row-basis adaptation; same input/config')
            cells.append(cell)
    plan=dict(status='FROZEN',created_at_utc=utc(),**state,source_sha256=sources(),cells=cells,
              test_log_sha256=sha(test_log),new_experimental_conditions=0,bug='BUG01')
    dump(root/'RUN_PLAN.json',plan);dump(root/'RUN_INDEX.json',plan)
    for name in plan['source_sha256']:
        dst=root/'source'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)


def execute(root):
    root=Path(root);plan=json.loads((root/'RUN_INDEX.json').read_text())
    if len(plan['cells'])!=4 or any(c['status']!='PLANNED' for c in plan['cells']):raise ValueError('four planned repairs; no overwrite/retry')
    if git_state()['worktree_dirty'] or sources()!=plan['source_sha256']:raise ValueError('source changed')
    for c in plan['cells']:
        inp=Path(c['input_directory']);dst=root/'runs'/c['run_id'];dst.parent.mkdir(exist_ok=True)
        if sha(inp/'events.jsonl.gz')!=c['input_sha256'] or sha(inp/'config.json')!=c['config_sha256']:raise ValueError('input changed')
        if sha(Path(c['original_run'])/'run.json')!=c['original_run_sha256']:raise ValueError('v1 changed')
        c['status']='IN_PROGRESS';dump(root/'RUN_INDEX.json',plan)
        try:
            result=run(inp/'events.jsonl.gz',inp/'config.json',c['method'],dst)
            c.update(status=result['status'],run_sha256=sha(dst/'run.json'),elapsed_s=result['elapsed_s'])
        except Exception as error:
            c.update(status='FAILED',error=str(error));dump(root/'RUN_INDEX.json',plan);raise
        dump(root/'RUN_INDEX.json',plan);print(c['run_id'],c['status'],flush=True)
    plan['status']='DONE';dump(root/'RUN_INDEX.json',plan)


def select(artifacts,repair,original,output):
    """Portable selection manifest, no mutation/copy of prior runs or indices."""
    a=Path(artifacts);old=a/original;output=Path(output);output.mkdir(exist_ok=False)
    base=json.loads((old/'RUN_INDEX.json').read_text());fixed=json.loads((Path(repair)/'RUN_INDEX.json').read_text())
    eligible={c['run_id']:c for c in fixed['cells'] if Path(c['original_run']).parent.parent==old}
    for cell in base['cells']:
        rid=cell['run_id'];new=eligible.get(rid);source=fixed if new else base
        cell['original_run_path']=str((old/'runs'/rid).relative_to(a));cell['original_run_sha256']=cell['run_sha256']
        if new:cell.update(run_sha256=new['run_sha256'],elapsed_s=new['elapsed_s'],status=new['status'])
        cell['run_path']=str(((Path(repair) if new else old)/'runs'/rid).relative_to(a))
        cell['expected_source_sha256']=source['source_sha256'];cell['expected_code_commit']=source['code_commit']
        cell['selection']='BUG01 repaired' if new else 'unaffected v1'
        cell['input_path']=str(((old/'inputs'/cell['case']) if 'inputs' in base else a/'old-inputs-v2'/cell['case']).relative_to(a))
    base['artifact_root']='..';base['selection_policy']='Only four preregistered BUG01 replacements; original evidence immutable'
    base['original_index_sha256']=sha(old/'RUN_INDEX.json');base['repair_index_sha256']=sha(Path(repair)/'RUN_INDEX.json')
    dump(output/'RUN_INDEX.json',base)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['freeze','run','select']);p.add_argument('--artifacts',type=Path)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--test-log',type=Path);p.add_argument('--original');p.add_argument('--output',type=Path)
    v=p.parse_args()
    if v.phase=='freeze':freeze(v.artifacts,v.root,v.test_log)
    elif v.phase=='run':execute(v.root)
    else:select(v.artifacts,v.root,v.original,v.output)
