#!/usr/bin/env python3
"""Bounded, resumable v1 experiment; source/config hashes gate every run."""
from __future__ import annotations
import argparse
import csv
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import numpy as np
import scipy
from single_car_integrity_sim import save_generated
from single_car_integrity_compat import (VERSION, compatibility_manifest, verify_execution_state,
                                        verify_record, handoff_text)

ROOT=Path(__file__).resolve().parents[1]
DEFAULT=ROOT/'docs/field_tests/integrity_feasibility_v1_1_20261022'
CORE=['tools/single_car_integrity.py','tools/single_car_integrity_sim.py',
      'tools/run_single_car_integrity_worker.py','tools/run_single_car_integrity_experiment.py',
      'tools/test_single_car_integrity.py','tools/single_car_fixed_lag.py',
      'tools/single_car_sequential_replay.py','tools/run_single_car_fixed_lag.py',
      'tools/run_single_car_sequential_baseline.py','tools/test_single_car_fixed_lag.py',
      'tools/test_single_car_sequential_replay.py',
      'docs/field_tests/single_car_historical_L_20261021/results/evidence/new_graph.py']


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def write(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    temporary.replace(path)


def read_rows(path):
    with path.open() as f:return [json.loads(line) for line in f]


def source_state(out):
    return dict(protocol_sha256=sha(out/'protocol.json'),
                config_sha256=sha(out/'estimator_config.json'),
                sources={name:sha(ROOT/name) for name in CORE})


def verify(out):
    current=source_state(out)
    verify_execution_state(out,ROOT,current)
    return current


def checkpoint(out,stage):
    records=[json.loads(path.read_text()) for path in sorted((out/'runs').glob('*/run.json'))]
    registered=sha(out/'source_lock.json') in compatibility_manifest(ROOT)['supported_execution_source_lock_sha256']
    # Frozen run inventories and the historical root HANDOFF stay untouched.
    metadata=out/'compatibility'/'v1_2_0'/'checkpoints' if registered else out
    metadata.mkdir(parents=True,exist_ok=True)
    write(metadata/'run_inventory.json',records)
    fields=['id','group','status','seed','scenario','wall_s','output_count','input_sha256','source_lock_sha256','threshold_sha256','error']
    with (metadata/'run_inventory.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    (metadata/'HANDOFF.md').write_text(handoff_text(out,ROOT,stage,records))
    return records


def resume_existing(out,p,phase='all',handoff_output=None):
    """Hash audit only: cannot generate inputs, select thresholds or start workers."""
    verify(out)
    expected=[]
    if phase in ('baseline','all'):
        expected.extend('history_'+case['id'] for case in p['historical_cases'])
    if phase in ('develop','all'):
        expected.extend('dev_nominal_'+str(seed) for seed in p['development_seeds'])
    if phase in ('diagnostics','all'):
        expected.extend('test_'+scene['id']+'_'+str(seed) for scene in p['scenarios'] for seed in scene['seeds'])
        frozen=json.loads((out/'thresholds.json').read_text())
        if frozen['source_lock_sha256']!=sha(out/'source_lock.json'):
            raise ValueError('Frozen threshold execution-lock mismatch')
    records=[];resolutions=[]
    for run_id in expected:
        path=out/'runs'/run_id/'run.json'
        if not path.is_file():raise FileNotFoundError('Resume-only run missing: '+run_id)
        record=json.loads(path.read_text())
        if record['id']!=run_id or record['status']!='completed':
            raise ValueError('Resume-only requires an existing completed run: '+run_id)
        resolutions.append(verify_record(out,ROOT,record,p));records.append(record)
    if handoff_output is not None:
        handoff_output=Path(handoff_output)
        handoff_output.parent.mkdir(parents=True,exist_ok=True)
        with handoff_output.open('x') as stream:
            stream.write(handoff_text(out,ROOT,'全部已有项校验完成；未启动估计器',records))
    return dict(status='verified_existing_only',compatibility_version=VERSION,runs_verified=len(records),
                estimator_runs_started=0,thresholds_reselected=False,input_resolutions=resolutions)


def initialize(out,p):
    config={k:p[k] for k in ['model','replay','lag_s','max_nfev','max_sensor_samples']}
    config['monitor_rules']={k:p['threshold_selection'][k] for k in ['consecutive_exceedances','rank_rtol','condition_limit']}
    configpath=out/'estimator_config.json'
    if configpath.exists():
        if json.loads(configpath.read_text())!=config:raise ValueError('Config differs')
    else:write(configpath,config)
    (out/'runs').mkdir(exist_ok=True)
    if not (out/'source_lock.json').exists():
        write(out/'source_lock.json',dict(locked=source_state(out),created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            baseline_commit=p['baseline_commit'],python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,
            rosbags=importlib.metadata.version('rosbags'),platform=platform.platform(),
            thread_env={k:os.environ.get(k) for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']},
            dependency_directory='/home/ubuntu22/uwb/offline-deps',
            archive_environment=json.loads((ROOT/'docs/field_tests/single_car_fixed_lag_20261022/results/input_manifest.json').read_text())))
    verify(out)


def run_one(out,p,run_id,group,scenario=None,seed=None,bag=None,expected_hash=None):
    verify(out)
    target=out/'runs'/run_id
    config=out/'estimator_config.json'
    threshold=out/'thresholds.json' if group=='diagnostic' else None
    if threshold and not threshold.exists():raise ValueError('Diagnostic thresholds not frozen')
    if target.exists():
        previous=json.loads((target/'run.json').read_text())
        verify_record(out,ROOT,previous,p)
        print('Preserving existing run',run_id,previous['status'],flush=True)
        return previous
    inventory=checkpoint(out,'准备 '+run_id)
    consumed=sum(r.get('wall_s',0) for r in inventory)
    if consumed>=p['budget']['total_compute_wall_budget_s']:
        print('Registered total budget reached; checkpoint saved',flush=True); return None
    if bag is None:
        # Only generator/evaluator has the full experiment protocol and labels.
        save_generated(target,p,scenario,seed)
        input_path=target/'sensors.jsonl';mode='--sensors'
    else:
        target.mkdir();input_path=ROOT/bag;mode='--bag'
    input_hash=sha(input_path)
    if expected_hash and input_hash!=expected_hash:raise ValueError('Raw bag hash mismatch')
    record=dict(id=run_id,group=group,status='running',scenario=scenario['id'] if scenario else None,
                seed=seed,input_path=str(input_path),input_sha256=input_hash,
                source_lock_sha256=sha(out/'source_lock.json'),threshold_sha256=sha(threshold) if threshold else None,
                config_sha256=sha(config),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),wall_s=0.)
    write(target/'run.json',record);checkpoint(out,'运行 '+run_id)
    cmd=[sys.executable,str(ROOT/'tools/run_single_car_integrity_worker.py'),'--config',str(config),mode,str(input_path),'--output',str(target/'output')]
    if threshold:cmd.extend(['--thresholds',str(threshold)])
    record['command']=cmd
    print('Starting',run_id,flush=True)
    start=time.perf_counter()
    try:
        with (target/'worker.log').open('x') as log:
            done=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,
                                timeout=min(p['budget']['per_run_wall_timeout_s'],p['budget']['total_compute_wall_budget_s']-consumed),check=False)
        record['status']='completed' if done.returncode==0 else 'failed'
        record['exit_code']=done.returncode
        if done.returncode:record['error']='Worker exit '+str(done.returncode)+'; see worker.log'
    except subprocess.TimeoutExpired:
        record.update(status='timed_out',error='Registered wall-time budget exceeded; partial updates retained')
    except KeyboardInterrupt:
        record.update(status='interrupted',error='Interrupted; partial updates retained')
        raise
    finally:
        record['wall_s']=time.perf_counter()-start
        record['output_count']=sum(1 for _ in (target/'output/updates.jsonl').open()) if (target/'output/updates.jsonl').exists() else 0
        record['output_files']={str(path.relative_to(target)):sha(path) for path in target.rglob('*') if path.is_file() and path.name!='run.json'}
        record['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        write(target/'run.json',record);checkpoint(out,'已记录 '+run_id)
    verify(out)
    print(record['status'],run_id,'wall_s=',round(record['wall_s'],3),'outputs=',record['output_count'],flush=True)
    return record


def freeze_thresholds(out,p):
    evidence=[]; values={key:[] for key in ['M1','M2']}
    for seed in p['development_seeds']:
        run=out/'runs'/('dev_nominal_'+str(seed))
        status=json.loads((run/'run.json').read_text())
        if status['status']!='completed':raise ValueError('All 5 nominal development runs required to freeze thresholds')
        rows=read_rows(run/'output/updates.jsonl')
        evidence.append(dict(run_id=status['id'],updates_sha256=sha(run/'output/updates.jsonl'),input_sha256=status['input_sha256']))
        for key in values:values[key].extend(r[key]['statistic'] for r in rows if r[key]['available'])
    if not all(values.values()):raise ValueError('No available development statistics')
    selected={key:max(floor,1.25*float(np.quantile(values[key],.995,method='linear'))) for key,floor in [('M1',1.),('M2',.05)]}
    frozen=dict(values=selected,rule=p['threshold_selection'],development_evidence=evidence,
                sample_counts={k:len(v) for k,v in values.items()},source_lock_sha256=sha(out/'source_lock.json'))
    path=out/'thresholds.json'
    if path.exists():
        if json.loads(path.read_text())!=frozen:raise ValueError('Frozen thresholds/evidence changed')
    else:write(path,frozen)
    print('Frozen thresholds',selected,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--phase',choices=['baseline','develop','diagnostics','all'],default='all')
    parser.add_argument('--resume-only',action='store_true',help='Verify completed runs only; never start an estimator or reselect thresholds')
    parser.add_argument('--handoff-output',type=Path,help='New handoff file for --resume-only; must not already exist')
    args=parser.parse_args()
    if args.handoff_output and not args.resume_only:parser.error('--handoff-output requires --resume-only')
    out=args.experiment.resolve();p=json.loads((out/'protocol.json').read_text())
    for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']:
        if os.environ.get(key)!='1':raise ValueError(key+' must be 1')
    if args.resume_only:
        print(json.dumps(resume_existing(out,p,args.phase,args.handoff_output),ensure_ascii=False),flush=True)
        return
    initialize(out,p)
    if args.phase in ['baseline','all']:
        for case in p['historical_cases']:
            run_one(out,p,'history_'+case['id'],'historical',bag=case['bag'],expected_hash=case['sha256'])
    if args.phase in ['develop','all']:
        nominal=p['scenarios'][0]
        for seed in p['development_seeds']:
            run_one(out,p,'dev_nominal_'+str(seed),'development',nominal,seed)
        freeze_thresholds(out,p)
    if args.phase in ['diagnostics','all']:
        frozen=json.loads((out/'thresholds.json').read_text())
        if frozen['source_lock_sha256']!=sha(out/'source_lock.json'):raise ValueError('Threshold/source mismatch')
        for scenario in p['scenarios']:
            for seed in scenario['seeds']:
                if run_one(out,p,'test_'+scenario['id']+'_'+str(seed),'diagnostic',scenario,seed) is None:
                    checkpoint(out,'预算已到；剩余项未运行');return
    checkpoint(out,'请求阶段已完成：'+args.phase)
    verify(out)


if __name__=='__main__':main()
