#!/usr/bin/env python3
"""Exact read-only PR70 revision bindings; select two already exposed inputs."""
import json,shutil,subprocess
from pathlib import Path
from common import ROOT,ART,SCENARIOS,sha,dump,sources
PR70='d946bdcb457f7f51f93a116a359dcabf7647134c'
def prepare(out):
 out.mkdir(exist_ok=False);old=Path('/home/ubuntu22/uwb-peer-dcs-minimal-20261028-artifacts/evidence-v1')
 named='docs/field_tests/20261024_25/cooperative_dcs_probe_20261028/RUN_INDEX.json'
 expected=subprocess.check_output(['git','show',PR70+':'+named],cwd=ROOT)
 assert (old/'RUN_INDEX.json').read_bytes()==expected
 index=json.loads(expected);sources();bindings=[]
 for s in SCENARIOS:
  case=s+'_seed101';src=old/'inputs'/case;dst=out/'inputs'/case;shutil.copytree(src,dst)
  for method in ['D0','D1']:
   c=next(c for c in index['cells'] if c['case']==case and c['method']==method);run=old/c['run_path'];meta=json.loads((run/'run.json').read_text())
   for name,k in [('events.jsonl.gz','events_sha256'),('config.json','config_sha256'),('truth.jsonl','truth_sha256'),('labels.json','labels_sha256')]:assert sha(dst/name)==c[k]==meta[k]
   assert sha(run/'run.json')==c['run_sha256']
   for p in meta['outputs']:assert sha(run/p['path'])==p['sha256']
   target=out/'reused'/f"{case}__{'I' if method=='D0' else 'J'}"
   shutil.copytree(run,target);bindings.append(dict(case=case,method='I' if method=='D0' else 'J',path=str(target.relative_to(out)),original_cell=c))
 dump(out/'INPUT_BINDINGS.json',dict(PR70_head=PR70,PR70_index_sha256=sha(old/'RUN_INDEX.json'),cases={s+'_seed101':{p.name:sha(p) for p in (out/'inputs'/(s+'_seed101')).iterdir()} for s in SCENARIOS},baseline_runs=bindings))
 print('Verified two inputs and four baseline outputs against exact PR70 commit')
if __name__=='__main__':prepare(ART/'evidence-v1')
