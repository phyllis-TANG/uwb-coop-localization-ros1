#!/usr/bin/env python3
"""Frozen 45-cell development index; checkpoint first, no implicit retry/resume."""
import argparse,copy,json,os,shutil,subprocess,sys,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from pinned import MANIFEST,io
from probe import execute,export_baseline
from records import sha,dump,read,write_gzip,Provenance
from index_contract import validate,SEEDS,SCENARIOS,METHODS
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
EXECUTION_FILES=('pinned.py','probe.py','records.py','prepare.py','index_contract.py','runner.py','frozen_manifest.json','test_probe.py','test_index.py','test_export.py')

def source_lock():return {name:sha(HERE/name) for name in EXECUTION_FILES}
def freeze(artifacts):
 if not (artifacts/'tests-v1/probe.log').read_text().rstrip().endswith('OK'):raise ValueError('Probe tests not PASS')
 if not (artifacts/'tests-v2/frozen.log').read_text().rstrip().endswith('OK'):raise ValueError('Frozen tests not PASS')
 if not (artifacts/'tests-v2/index.log').read_text().rstrip().endswith('OK'):raise ValueError('Index tests not PASS')
 if not (artifacts/'tests-v2/export.log').read_text().rstrip().endswith('OK'):raise ValueError('Baseline export tests not PASS')
 for name in ('pinned.py','probe.py','records.py','test_probe.py','frozen_manifest.json'):
  # export_baseline was added after numerical tests; only that non-estimator function is new.
  previous=artifacts/'tests-v1/source'/name
  if name=='probe.py':
   assert previous.read_text().rstrip()==(HERE/name).read_text().split('\ndef export_baseline(')[0].rstrip()
  elif sha(previous)!=sha(HERE/name):raise ValueError('Tested source changed: '+name)
 inputs=json.loads((artifacts/'input_index.json').read_text())['cases'];reuse=json.loads((artifacts/'reuse_evidence.json').read_text());assert reuse['reusable_cells']==24
 output=artifacts/'matrix-v1';output.mkdir(exist_ok=False);(output/'runs').mkdir();(output/'source').mkdir()
 for name in EXECUTION_FILES:shutil.copyfile(HERE/name,output/'source'/name)
 cells=[]
 for seed in SEEDS:
  for sc in SCENARIOS:
   inp=next(r for r in inputs if r['seed']==seed and r['scenario']==sc)
   for method in METHODS:
    old=next((r for r in reuse['cells'] if (r['scenario'],r['seed'],r['method'])==(sc,seed,method)),None)
    cells.append(dict(cell_id=f'{sc}_seed{seed}__{method}',scenario=sc,seed=seed,method=method,status='PLANNED',input_path=inp['path'],events_sha256=inp['files']['events.jsonl.gz'],config_sha256=inp['files']['config.json'],truth_sha256=inp['files']['truth.jsonl'],labels_sha256=inp['files']['labels.json'],mode='reuse_verified_original' if old else 'new_replay',original_run=old['original_run'] if old else None,original_run_manifest_sha256=old['run_manifest_sha256'] if old else None))
 index=dict(schema_version=1,status='FROZEN_NOT_STARTED',created_at_utc=datetime.now(timezone.utc).isoformat(),reading_commit=MANIFEST['commit'],base_main_HEAD='7b67c66f2470d23f6c876f45b6543f72fab66391',deadline_utc='2026-10-27T22:34:27+00:00',execution_source_sha256=source_lock(),frozen_source_sha256=MANIFEST['files'],gate=dict(q_threshold=3.,reject='q>3',unknown='reject new',missing='no new factor',history='retained'),cells=cells,expected_cells=45,independent_validation=False)
 validate(index,False);dump(output/'index.json',index);dump(output/'pre_execution_index.json',index)
 return output,index

def run_cell(cell,root,source):
 out=root/'runs'/cell['cell_id'];out.mkdir(exist_ok=False);start=time.perf_counter();inp=Path(cell['input_path']);info=dict(cell,status='IN_PROGRESS',execution_source_sha256=source,frozen_source_sha256=MANIFEST['files'],command_argv=sys.argv,timing_mode='virtual',algorithm_git_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
 dump(out/'run.json',info)
 try:
  assert sha(inp/'events.jsonl.gz')==cell['events_sha256'] and sha(inp/'config.json')==cell['config_sha256'];config=json.loads((inp/'config.json').read_text());events=list(read(inp/'events.jsonl.gz'));rows=[];current=time.perf_counter();worker=None
  if cell['mode']=='reuse_verified_original':
   old=Path(cell['original_run']);assert sha(old/'run.json')==cell['original_run_manifest_sha256'];meta=json.loads((old/'run.json').read_text());assert meta['source_sha256']==MANIFEST['files']
   for r in meta['outputs']:assert sha(old/r['relative_path'])==r['sha256']
   rows=[export_baseline(r,cell['method']) for r in read(old/'updates.jsonl.gz')];info['original_runtime_s']=meta['elapsed_s'];info['estimator_executed_this_cell']=False;info['original_estimator_execution_commit']=meta['code_commit'];info['timing_origin']='historical_original_run'
  else:
   worker=execute(events,config,cell['method'],rows.append);info['estimator_executed_this_cell']=True;info['timing_origin']='current_development_replay'
  processing=time.perf_counter()-current;prov=Provenance(events[0]['receive_epoch_ns'])
  for r in rows:prov.add(r)
  assert len(rows)==63 and len({r['state_epoch_ns'] for r in rows})==63
  write_gzip(out/'updates.jsonl.gz',rows);shutil.copyfile(inp/'config.json',out/'config.json')
  dump(out/'summary.json',dict(publications=len(rows),accepted=sum(r['accepted_graph'] for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),gate_states=dict(Counter(r['gate']['state'] for r in rows)),actual_peer_factors=sum(r['peer_factor_used'] for r in rows),main_update_wall_total_s=sum(r['main_update_wall_s'] for r in rows),auxiliary_update_wall_total_s=sum(r['auxiliary_update_wall_s'] for r in rows),frozen_emit_wall_total_s=sum(r['update_wall_s'] for r in rows),peak_main_states=max(r['graph_states'] for r in rows),peak_auxiliary_states=max([r['auxiliary']['graph_states'] for r in rows if r['auxiliary'] is not None],default=0),recording_excluded_from_emit_timing=True))
  info.update(status='DONE',processing_wall_s=processing,elapsed_with_current_IO_s=time.perf_counter()-start,outputs=[dict(path=p.name,sha256=sha(p),size_bytes=p.stat().st_size) for p in sorted(out.iterdir()) if p.is_file() and p.name!='run.json'])
  assert source_lock()==source
  dump(out/'run.json',info);return dict(status='DONE',run_path=str(out),run_manifest_sha256=sha(out/'run.json'),estimator_executed_this_cell=info['estimator_executed_this_cell'])
 except BaseException as error:
  info.update(status='FAILED',error=type(error).__name__+': '+str(error));dump(out/'run.json',info);raise

def advance(artifacts,phase):
 root=artifacts/'matrix-v1';path=root/'index.json';index=json.loads(path.read_text());validate(index,False)
 if source_lock()!=index['execution_source_sha256']:raise ValueError('Execution source changed since freeze')
 if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():raise ValueError('Commit execution files before running the comparison matrix')
 selected=[r for r in index['cells'] if r['seed']==101 and r['scenario'] in ('nominal','peer_bias')]
 if phase=='checkpoint':
  if index['status']!='FROZEN_NOT_STARTED':raise ValueError('Checkpoint already attempted; no automatic rerun')
  work=selected
 else:
  if index['status']!='CHECKPOINT_PASS' or any(r['status']!='DONE' for r in selected):raise ValueError('First six-cell checkpoint required')
  work=[r for r in index['cells'] if r not in selected]
 index['status']='RUNNING';dump(path,index)
 for cell in work:
  if datetime.now(timezone.utc)>=datetime.fromisoformat(index['deadline_utc']):
   index['status']='TIME_LIMIT_PARTIAL';dump(path,index);return
  if cell['status']!='PLANNED':raise ValueError('Existing or failed cell; no overwrite/retry')
  cell['status']='IN_PROGRESS';dump(path,index)
  try:cell.update(run_cell(cell,root,index['execution_source_sha256']))
  except BaseException as error:
   cell.update(status='FAILED',error=type(error).__name__+': '+str(error));index['status']='FAILED';dump(path,index);raise
  dump(path,index);print(cell['cell_id'],cell['status'],cell['mode'],flush=True)
 index['status']='CHECKPOINT_PASS' if phase=='checkpoint' else 'DONE';dump(path,index)
 if phase=='complete':validate(index,True)
 else:dump(root/'checkpoint_101.json',copy.deepcopy(index))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--artifacts',type=Path,required=True);ap.add_argument('--phase',choices=['freeze','checkpoint','complete'],required=True);a=ap.parse_args()
 if a.phase=='freeze':root,index=freeze(a.artifacts);print(root)
 else:advance(a.artifacts,a.phase)
if __name__=='__main__':main()
