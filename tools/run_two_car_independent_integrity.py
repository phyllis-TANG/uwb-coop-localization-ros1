#!/usr/bin/env python3
"""Freeze, execute six bounded independent replays, or audit without executing."""
from __future__ import annotations
import argparse
import collections
import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys
import time
import numpy as np
from single_car_integrity import IntegrityReplay
from single_car_sequential_replay import bag_events as p1_events
from two_car_independent_integrity import ROOT,CARS,ANCHORS,bag_events,make_config,odom_bracket
from two_car_updated_comparison import read_bag,fit_static_wall_bias

BASE = '5ced063043c264618d15ae6cd47b98d2487500b4'
PARENT = 'docs/field_tests/two_car_updated_comparison_20261022'
INTEGRITY = 'docs/field_tests/integrity_feasibility_v1_1_20261022'
SOURCE_NAMES = ['tools/'+x for x in (
    'two_car_independent_integrity.py','run_two_car_independent_integrity.py',
    'report_two_car_independent_integrity.py','test_two_car_independent_integrity.py',
    'single_car_integrity.py','single_car_fixed_lag.py','single_car_sequential_replay.py',
    'two_car_updated_comparison.py')]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def read(path): return json.loads(Path(path).read_text())


def write(path,value):
    path=Path(path)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    tmp.replace(path)


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def hashes(directory):
    return {str(p.relative_to(directory)):sha(p) for p in sorted(directory.rglob('*')) if p.is_file()}


def verify_lock(out):
    lock=read(out/'source_lock.json')
    for name,h in lock['repository_files'].items():
        if sha(ROOT/name)!=h:raise ValueError('Frozen source/data mismatch: '+name)
    for name,h in lock['experiment_files'].items():
        if sha(out/name)!=h:raise ValueError('Frozen configuration mismatch: '+name)
    return lock


def verify_record(out,record):
    if record['status']!='completed':raise ValueError('Not completed: '+record['id'])
    target=out/'runs'/record['id']/'output'
    if hashes(target)!=record['output_hashes']:raise ValueError('Output hash mismatch: '+record['id'])
    if record['source_lock_sha256']!=sha(out/'source_lock.json'):raise ValueError('Source lock changed')


def handoff(out,records):
    states=dict(collections.Counter(r['status'] for r in records))
    q=shlex.quote(str(out))
    text=f'''# 双车数据上的独立单车因果定位与完好性监测衔接试验

实际仓库：`{ROOT}`；冻结基点：`{BASE}`。
分支：`{git('branch','--show-current')}`。实际实验目录：`{out}`。
状态：{json.dumps(states,ensure_ascii=False)}；正式最多6条，不含单元测试夹具。

先读 README.md、protocol.json 和 results/CONCLUSION_ZH.md。原 PR38/39/40 产物不修改。
从实际仓库根目录恢复核对（只读，不重跑）：

```bash
env PYTHONPATH=/home/ubuntu22/uwb/offline-deps OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 python3 tools/run_two_car_independent_integrity.py --experiment {q} --resume-only
```

若存在 planned 项且源码/配置/输入哈希仍匹配，使用同一路径的 `--run` 只运行尚未开始项。
running/failed/timeout 项保留部分产物并停止自动重试；不得覆盖或增加运行预算。
报告复现仅用归档更新记录，不启动估计器：`python3 tools/report_two_car_independent_integrity.py --experiment {q} --output <项目内尚不存在的新目录>`。
源码/配置不匹配必须另起版本；不得重新选阈值、拟合动态终点、加入peer因子或真实车控制。
6项完成后停止扩展，提交指导窗口审核；没有推送或合并授权。
'''
    (out/'HANDOFF.md').write_text(text)


def freeze(out):
    if git('rev-parse','HEAD')!=BASE:raise ValueError('Expected frozen PR40 base')
    if out.exists():raise FileExistsError('Inspect existing checkpoint; never overwrite '+str(out))
    for commit in ('21d3d48476579837caa6aee4e1027cf57b9d18e3','e9df610','e813d8f'):
        subprocess.run(['git','merge-base','--is-ancestor',commit,'HEAD'],cwd=ROOT,check=True)
    parent=read(ROOT/PARENT/'protocol.json'); calibration=read(ROOT/PARENT/'results/calibration.json')
    template=read(ROOT/INTEGRITY/'estimator_config.json')
    threshold=read(ROOT/INTEGRITY/'thresholds.json')
    assert threshold['values']==dict(M1=1.,M2=.062191200771030145)
    data={c['path']:c['sha256'] for c in parent['cases']}
    source=parent['calibration']['car1'];data[source['path']]=source['sha256']
    p1='datasets/field_raw/20261017/bags/CAR2_P1_REINSTALL_STATIC_20261017_045257.bag'
    data[p1]='f7250698ae484b7ace3bf152b1ff216f5470b5d75f0b90a66483edb402d1ec33'
    for name,h in data.items():
        if sha(ROOT/name)!=h:raise ValueError('Data hash mismatch: '+name)
    fit=fit_static_wall_bias(read_bag(ROOT/source['path'],source['sha256']),'car1',
        source['reference_antenna_xyz_m'],parent['anchors_xyz_m'])
    for k in ANCHORS:
        assert fit[k]['samples']==calibration['car1_link_fit'][k]['samples']
        for field in ['raw_median_m','geometry_m','bias_m','raw_iqr_m']:
            assert abs(fit[k][field]-calibration['car1_link_fit'][k][field])<=1e-12,(k,field,fit[k])
    samples=collections.defaultdict(list)
    for e in p1_events(ROOT/p1):
        if e.kind=='uwb':
            for k,v in e.value.items():
                if k in ANCHORS and np.isfinite(v) and v>0:samples[k].append(v)
    p1fit={k:float(np.median(samples[k])-np.linalg.norm(np.array([2,2,.2])-parent['anchors_xyz_m'][k])) for k in ANCHORS}
    assert all(abs(p1fit[k]-calibration['applied_biases_m']['car2'][k])<=1e-12 for k in ANCHORS),p1fit
    out.mkdir(parents=True);(out/'configs').mkdir();(out/'runs').mkdir()
    (out/'cache').mkdir();(out/'cache/.gitignore').write_text('*\n!.gitignore\n')
    cases=[{k:v for k,v in c.items() if k!='evaluation_only'} for c in parent['cases']]
    evaluation={}
    records=[]
    for case,original in zip(cases,parent['cases']):
        archived=read(ROOT/PARENT/'results'/case['id']/'per_car_walls_inputs.json')
        evaluation[case['id']]=dict(original['evaluation_only'],state_times_s=archived['times'][-5:])
        for car in CARS:
            rid=case['id']+'_'+car
            write(out/'configs'/(rid+'.json'),make_config(template,parent,calibration,case,car))
            records.append(dict(id=rid,bag_id=case['id'],car=car,status='planned'))
    protocol=dict(schema_version=1,experiment='two-car-independent-integrity-bridge-v1',
        frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_head=BASE,
        cases=cases,thresholds=threshold['values'],monitor_rules=template['monitor_rules'],
        association=dict(version='bag-receipt-v1',origin='first receipt of ALL bag messages, shared by both cars',
            odom_and_uwb='association = (bag_receipt_ns-origin_ns)/1e9; original header_ns retained',
            internal_Event_header_s='association coordinate only; never the original physical measurement header',
            half_width_s=.4,minimum_samples_per_link=5,release_delay_s=1.,
            first_state='ceil(max(first selected Odom receipt, first selected UWB receipt)+1s)',
            equal_receipt_per_stream='fail explicitly if nonincreasing; no jitter or reordering',
            closed_bins='immutable; no late remeasurement rewrite',eof='no advancement beyond last actual bag receipt'),
        model=dict(lag_s=20.,state_step_s=1.,max_solve_states=21,max_nfev=50,
            near_zero_motion_covariance=False,range_confidence_policy=False,peer_factors=0,imu_factors=0),
        budgets=dict(per_run_wall_s=180.,total_formal_wall_s=1800.,formal_replays=6,automatic_retries=0),
        timing_model='Two independent virtual workers. Each serializes ingest, full solve, M1, four exclusion solves and logging. Actual runs serial, not a measured dual-worker platform.',
        timing_exclusions='Bag decode, input trace disk IO and process startup outside virtual model; inside actual per-run budget. Per-output delivery log includes current output enrichment/JSON flush; timing log write itself excluded.',
        evaluation='Fixed PR38 last five state times, never replace with a new last-five window; record missing output/stop support explicitly.',
        odom_phase_diagnostic=dict(translation_speed_threshold_m_s=.005,yaw_speed_threshold_deg_s=1.,
            note='diagnostic using consecutive interpolated Odom states only; no covariance/weight feedback'),
        assumptions=parent['assumptions']+['Frozen M1/M2 thresholds are transfer diagnostics, not true fault labels.',
            'No continuous truth; no trajectory error, true false-alarm or missed-detection rate.',
            'M1 stored residual = prediction minus corrected; signed innovation = corrected minus prediction.',
            'Largest exclusion separation is sensitivity attribution, not confirmed faulty-anchor isolation.'])
    write(out/'protocol.json',protocol);write(out/'evaluation.json',evaluation)
    write(out/'calibration.json',dict(pr38=calibration,car1_recomputed=fit,car2_p1_recomputed=p1fit,
        car2_p1_input=dict(path=p1,sha256=data[p1]),dynamic_endpoints_used=False,
        applied_values='exact archived PR38 values, NOT recomputed platform-rounded numbers',
        recomputation_verification_tolerance_m=1e-12,
        recomputed_minus_archived_bias_m=dict(car1={k:fit[k]['bias_m']-calibration['applied_biases_m']['car1'][k] for k in ANCHORS},
            car2={k:p1fit[k]-calibration['applied_biases_m']['car2'][k] for k in ANCHORS})))
    frozen_paths=[PARENT+'/protocol.json',PARENT+'/results/calibration.json',
        PARENT+'/results/trajectories.csv',PARENT+'/results/wall_reference_diagnostics.csv',
        PARENT+'/results/INTERPRETATION.md',INTEGRITY+'/estimator_config.json',INTEGRITY+'/thresholds.json',
        'docs/field_tests/two_car_stationary_confidence_20261023/results/REPORT.md',
        'datasets/field_raw/provenance/user_confirmations_20261020.md']
    frozen_paths += [PARENT+'/results/'+c['id']+'/per_car_walls_inputs.json' for c in cases]
    frozen_paths += ['datasets/field_raw/20261018/notes/live_field/'+name for name in (
        'TWO_CAR_C1_static_C2_auto_L_20261018_015334_notes.txt',
        'TWO_CAR_C2_static_C1_auto_straight_aligned_20261018_033248_notes.txt',
        'TWO_CAR_both_motion_clear_repeat_20261018_050447_notes.txt',
        'antenna_mount_survey_20261018.txt')]
    write(out/'source_lock.json',dict(repository_files={p:sha(ROOT/p) for p in SOURCE_NAMES+frozen_paths+list(data)},
        experiment_files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*.json'))},
        data_sha256=data))
    write(out/'environment.json',dict(repository=str(ROOT),branch=git('branch','--show-current'),head=BASE,
        pre_freeze_worktree=git('status','--porcelain=v1'),python=platform.python_version(),
        packages={n:importlib.metadata.version(n) for n in ['numpy','scipy','rosbags','matplotlib']},
        dependency_path='/home/ubuntu22/uwb/offline-deps',
        process_visibility='PID namespace contains command only; host analysis/ROS processes not observable',
        visible_process_names=subprocess.check_output(['ps','-eo','pid,ppid,comm'],text=True),
        network_used=False,new_dependencies_installed=False,thread_limits={'OPENBLAS_NUM_THREADS':1,'OMP_NUM_THREADS':1}))
    write(out/'run_inventory.json',records);handoff(out,records)
    print('Frozen six run configs, inputs, calibration, source and evaluation windows',flush=True)


def worker(out,rid):
    verify_lock(out)
    protocol=read(out/'protocol.json');case=next(c for c in protocol['cases'] if rid.startswith(c['id']+'_'))
    car=rid.split('_')[1];config=read(out/'configs'/(rid+'.json'))
    target=out/'runs'/rid/'output';target.mkdir(parents=True,exist_ok=False)
    trace=[];diagnostics={};started=time.perf_counter();write_seconds=0.
    with (target/'sensor_provenance.jsonl').open('x') as provenance, (target/'updates.jsonl').open('x') as updates, (target/'delivery_times.jsonl').open('x') as delivery:
        def sensor(row):
            trace.append(row)
            provenance.write(json.dumps(row,allow_nan=False)+'\n')
        def sink(row):
            nonlocal write_seconds
            begin=time.perf_counter()
            t=row['state_time_s'];cutoff=row['availability_cutoff_s']
            bracket=odom_bracket(trace,t,cutoff)
            assert (bracket is None)==(row['pose'] is None)
            row.update(bag_id=case['id'],car=car,association_version='bag-receipt-v1',
                odom_endpoint_provenance=bracket,
                cumulative_frontend_counters=dict(replay.full.counters),
                actual_output_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
            if bracket:assert max(b['bag_receipt_s'] for b in bracket)<=cutoff
            assert row['graph_states']<=21
            updates.write(json.dumps(row,allow_nan=False)+'\n');updates.flush()
            delivery.write(json.dumps(dict(state_time_s=t,
                result_available_receipt_s=replay._stamp(),
                actual_log_complete_elapsed_s=time.perf_counter()-started))+'\n');delivery.flush()
            write_seconds += time.perf_counter()-begin
        replay=IntegrityReplay(config,sink,protocol['thresholds'])
        for event in bag_events(ROOT/case['path'],car,diagnostics,sensor):replay.ingest(event)
        replay.finish()
    counters=dict(replay.full.counters)
    for key in ['late_packets_for_closed_bins','missing_odom_bracket','invalid_raw_ranges',
                'nonpositive_corrected_ranges','bootstrap_skipped_deadlines']:
        counters.setdefault(key,0)
    result=dict(run_id=rid,wall_s=time.perf_counter()-started,output_count=replay.monitored_outputs,
        frontend_counters=counters,sensor_buffer_peaks=replay.full.sensor_peaks,
        peak_solve_states=replay.full.graph.peak_solve_states,marginalizations=replay.full.graph.marginalizations,
        exclusion_peak_states={k:g.peak_solve_states for k,g in replay.hypotheses.items()},
        external_output_logging_wall_s=write_seconds,input_diagnostics=diagnostics,
        config_sha256=sha(out/'configs'/(rid+'.json')))
    write(target/'worker_summary.json',result)
    verify_lock(out)
    print(json.dumps({k:result[k] for k in ['run_id','wall_s','output_count']}),flush=True)


def run(out,resume_only=False):
    verify_lock(out);records=read(out/'run_inventory.json');p=read(out/'protocol.json')
    assert len(records)==6 and len({r['id'] for r in records})==6
    spent=sum(r.get('process_wall_s',0) for r in records)
    for record in records:
        if record['status']=='completed':verify_record(out,record);continue
        if resume_only or record['status']!='planned':raise ValueError('Refusing to launch/retry '+record['id']+' '+record['status'])
        remaining=p['budgets']['total_formal_wall_s']-spent
        if remaining<=0:raise TimeoutError('Total formal budget exhausted')
        target=out/'runs'/record['id'];target.mkdir(exist_ok=False)
        record.update(status='running',source_lock_sha256=sha(out/'source_lock.json'),
            config_sha256=sha(out/'configs'/(record['id']+'.json')),
            started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        write(out/'run_inventory.json',records);write(target/'run.json',record);handoff(out,records)
        command=[sys.executable,str(Path(__file__).resolve()),'--experiment',str(out),'--worker',record['id']]
        record['command']=command
        begin=time.perf_counter()
        with (target/'stdout.log').open('x') as stdout,(target/'stderr.log').open('x') as stderr:
            try:
                result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,
                    timeout=min(180.,remaining),check=False)
                record.update(status='completed' if result.returncode==0 else 'failed',returncode=result.returncode)
            except subprocess.TimeoutExpired:
                record.update(status='timeout',error='180s per-run or remaining total budget reached')
        record['process_wall_s']=time.perf_counter()-begin;spent+=record['process_wall_s']
        record['output_hashes']=hashes(target/'output') if (target/'output').exists() else {}
        write(target/'run.json',record);write(out/'run_inventory.json',records);handoff(out,records)
        verify_lock(out)
        print(record['id'],record['status'],round(record['process_wall_s'],3),'s',flush=True)
    print(json.dumps(dict(status='verified',runs=6,process_wall_s_total=spent,new_estimators=0 if resume_only else 'see inventory timestamps')),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    choice=parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--freeze',action='store_true');choice.add_argument('--run',action='store_true')
    choice.add_argument('--resume-only',action='store_true');choice.add_argument('--worker')
    a=parser.parse_args();out=a.experiment.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('Experiment must be inside authorized project')
    for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS']:
        if os.environ.get(key)!='1':raise ValueError(key+' must be 1')
    if a.freeze:freeze(out)
    elif a.worker:worker(out,a.worker)
    else:run(out,a.resume_only)


if __name__=='__main__':main()
