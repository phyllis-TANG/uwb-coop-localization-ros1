#!/usr/bin/env python3
"""Verify and copy ONLY the 27 matched baseline outputs and nine inputs."""
import argparse,json,shutil
from pathlib import Path
from common import ROOT,HERE,SCENARIOS,SEEDS,sha,dump,external

def prepare(old,out):
 old=Path(old);out=external(out);out.mkdir(exist_ok=False)
 old_index=json.loads((old/'matrix-v1/index.json').read_text())
 assert old_index['status']=='DONE' and len(old_index['cells'])==45
 files=old_index['frozen_source_sha256'];gate={str(Path('tools/cooperative_peer_gate_probe_20261028')/p):v for p,v in old_index['execution_source_sha256'].items()}
 for p,s in {**files,**gate}.items():assert sha(ROOT/p)==s,p
 archive=old/'archives-v1/cooperative_peer_gate_probe_20261028_74fa210e.tar.gz'
 assert sha(archive)=='a1c75087eb2a54ff0512e2065cca770d45f5b7d26dabf0e27d3d474c0f52a26f'
 cells=[];inputs={}
 for sc in SCENARIOS:
  for seed in SEEDS:
   case=f'{sc}_seed{seed}';inp=old/'inputs'/case;dst=out/'inputs'/case;dst.mkdir(parents=True,exist_ok=False)
   examples=[c for c in old_index['cells'] if c['scenario']==sc and c['seed']==seed];assert len(examples)==3
   for name,field in [('events.jsonl.gz','events_sha256'),('config.json','config_sha256'),('truth.jsonl','truth_sha256'),('labels.json','labels_sha256')]:
    assert len({c[field] for c in examples})==1 and sha(inp/name)==examples[0][field];shutil.copyfile(inp/name,dst/name)
   inputs[case]={p.name:sha(p) for p in dst.iterdir()}
   for c in examples:
    run=old/'matrix-v1/runs'/c['cell_id'];meta=json.loads((run/'run.json').read_text())
    assert c['status']=='DONE' and sha(run/'run.json')==c['run_manifest_sha256']
    assert meta['status']=='DONE' and meta['frozen_source_sha256']==files and meta['execution_source_sha256']==old_index['execution_source_sha256']
    for item in meta['outputs']:assert sha(run/item['path'])==item['sha256'] and (run/item['path']).stat().st_size==item['size_bytes']
    # Copy original bytes; method renaming happens only in the new evaluator/index.
    target=out/'reused'/c['cell_id'];shutil.copytree(run,target)
    cells.append(dict(scenario=sc,seed=seed,case=case,method='D'+c['method'][1],original_method=c['method'],status='REUSED_VERIFIED',
      run_id=case+'__D'+c['method'][1],run_path=str(target.relative_to(out)),run_sha256=sha(target/'run.json'),
      events_sha256=c['events_sha256'],config_sha256=c['config_sha256'],truth_sha256=c['truth_sha256'],labels_sha256=c['labels_sha256'],
      original_index_sha256=sha(old/'matrix-v1/index.json'),original_algorithm_git_HEAD=meta['algorithm_git_HEAD'],estimator_executed_this_task=False))
 receipt=dict(status='PASS',cells=cells,inputs=inputs,reused=27,new_estimator_runs=0,source_identity_unchanged=True,
              original_archive_sha256=sha(archive),baseline_source_sha256=files,gate_source_sha256=gate)
 dump(out/'REUSE_RECEIPT.json',receipt)
 for p in ('pre_execution_index.json','index.json'):
  (out/'original-index').mkdir(exist_ok=True);shutil.copyfile(old/'matrix-v1'/p,out/'original-index'/p)
 print('PASS 27 exact baseline cells, 9 exact matched inputs, unchanged F0 and gate source')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--old',type=Path,required=True);p.add_argument('--output',type=Path,required=True);v=p.parse_args();prepare(v.old,v.output)
