#!/usr/bin/env python3
"""Exact three-case small controlled reproduction; immutable, resumable by phase."""
import argparse
import csv
import gzip
import json
import time
from pathlib import Path
import numpy as np
from binding import MANIFEST, frontend, numeric, semantic
from common import ROOT, SPEC, canonical, digest, sha, source_lock, head, new_output, write_json, csv_write, size_guard
from inputs import make
from engine import run
from evaluate import evaluate
from independent import verify_input_prefix


def compact(row):
    return dict(state_epoch_ns=row['state_epoch_ns'],state_time_s=row['state_time_s'],
        availability_cutoff_epoch_ns=row['availability_cutoff_epoch_ns'],
        pose=row['pose'],accepted_graph=row['accepted_graph'],status=row['status'],
        bins=row['bins'],peer_median_m=row['peer_median_m'],dependency_receipt_max_s=row['dependency_receipt_max_s'],
        peer_dependencies=row['peer_dependencies'],reverse_diagnostic_dependencies=row['reverse_diagnostic_dependencies'],
        main_snapshot_sha256=digest(row['snapshot']),marginalizations=row['marginalizations'],
        monitor_available_time_virtual_s=row['monitor_available_time_virtual_s'],
        total_monitored_emit_wall_s=row['total_monitored_emit_wall_s'], monitor=row['monitor'],
        marginal_evidence=row['marginal_evidence'],linear_evidence=row.get('linear_evidence'))


def regression(scenario, rows):
    path=ROOT/'docs/field_tests/20261024_25/cooperative_peer_gate_probe_20261028/review/timeline.csv.gz'
    assert sha(path)=='c72ac4d6c160476051b42fbe9c698a9dac520e4dac741f0ff0599b234e9117aa'
    old=[r for r in csv.DictReader(gzip.open(path,'rt')) if r['seed']=='101' and r['scenario']==scenario]
    assert len(old)==189
    max_delta=0.; max_median_delta=0.; max_q_delta=0.
    for method in ('G0','G1'):
        for row in rows:
            previous=next(r for r in old if r['method']==method and int(r['state_epoch_ns'])==row['state_epoch_ns'])
            pose=row['pose'] if method=='G1' else row['monitor']['subset_results']['peer']['pose']
            target=[float(previous[f'{car}_{key}']) for car in ('car1','car2') for key in ('base_x_m','base_y_m','yaw_rad')]
            delta=float(np.max(np.abs(np.asarray(pose)-target)));max_delta=max(max_delta,delta)
            np.testing.assert_allclose(pose,target,atol=1e-6,rtol=0)
            max_median_delta=max(max_median_delta,abs(row['peer_median_m']-float(previous['peer_measured_m'])))
            if method=='G0':
                gate=next(r for r in old if r['method']=='G2' and int(r['state_epoch_ns'])==row['state_epoch_ns'])
                if gate['q']:
                    deltaq=abs(row['monitor']['b0']['engineering_q']-float(gate['q']));max_q_delta=max(max_q_delta,deltaq)
                    assert deltaq<1e-6
            assert (previous['accepted']=='True') == (row['accepted_graph'] if method=='G1' else row['monitor']['subset_results']['peer']['accepted'])
    return dict(status='PASS',compared_state_rows=126,maximum_pose_component_difference=max_delta,
                maximum_peer_median_difference_m=max_median_delta,maximum_q_difference=max_q_delta,atol_m_rad=1e-6,timeline_sha256=sha(path),scope='numeric saved poses/status only, not reconstruction of archived graphs')


def one(scenario, root):
    out=root/scenario;out.mkdir(exist_ok=False)
    start=time.perf_counter();config,events,truth,input_receipt=make(scenario)
    write_json(out/'INPUT.json',input_receipt);write_json(out/'config.json',config)
    rows=[];worker=run(events,config,rows.append)
    assert len(rows)==63 and len({r['state_epoch_ns'] for r in rows})==63
    # Exact no-feedback control, same host and inputs; no extra scenario or seed.
    baseline=[];plain=frontend.JointReplay(config,'D1',baseline.append,events[0]['receive_epoch_ns'])
    for e in events:plain.ingest(e)
    plain.finish()
    assert [numeric(r) for r in rows]==[numeric(r) for r in baseline]
    check=regression(scenario,rows)
    write_json(out/'RAW_PREFIX_CHECK.json',verify_input_prefix(rows,events,config))
    prefix_proof=None
    if scenario=='nominal':
        prefix=[]
        prefix_events=[e for e in events if e['receive_epoch_ns']<=events[0]['receive_epoch_ns']+46_000_000_000]
        run(prefix_events,config,prefix.append)
        reference={r['state_epoch_ns']:r for r in rows}
        for p in prefix:
            f=reference[p['state_epoch_ns']]
            assert numeric(p)==numeric(f)
            for key in ('ss','b0','b1','declarations','subset_history_hashes'):
                assert p['monitor'][key]==f['monitor'][key]
        assert len(prefix)>=25
        prefix_proof=dict(status='PASS',receive_cutoff_s=46,publications=len(prefix),after_actual_marginalization=True,checks='main snapshots, three subset histories and all statistics/declarations exact; timing excluded')
        write_json(out/'PREFIX.json',prefix_proof)
    evaluation=evaluate(scenario,rows,truth,config)
    for name,values in evaluation.items():
        if values:csv_write(out/(name+'.csv'),values)
    # Compressed compact numerical evidence; no full source/raw cache or repeated full snapshots.
    with (out/'monitor.jsonl.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z:
        for row in rows:z.write((canonical(compact(row))+'\n').encode())
    # Required shared-noise and QR evidence: selected first/mid/late points only.
    selected=[]
    for row in rows:
        if row['state_time_s'] in (3.,23.,24.,37.,38.,48.,59.,63.):
            selected.append(dict(t_s=row['state_time_s'],snapshot=row['snapshot'],
                marginalization_details=row['marginalization_details'],monitor=row['monitor']))
    write_json(out/'selected_evidence.json',selected)
    status=dict(status='DONE',scenario=scenario,seed=101,publications=len(rows),accepted=sum(r['accepted_graph'] for r in rows),
        main_no_feedback_control='EXACT_ALL_SNAPSHOTS_POSES_H_G_CONSTANTS',regression=check,prefix=prefix_proof,
        total_elapsed_s=time.perf_counter()-start,measured_emit_total_s=sum(r['total_monitored_emit_wall_s'] for r in rows),
        maximum_delay_virtual_s=max(r['monitor_available_time_virtual_s']-r['state_time_s'] for r in rows),
        input=input_receipt,source_sha256=source_lock(),kernel_sha256=MANIFEST['files'],execution_commit=head(),
        artifacts={p.name:sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    write_json(out/'RUN.json',status)
    print(scenario,'DONE',status['total_elapsed_s'],'seconds',flush=True)
    size_guard(root)
    return status


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--phase',choices=['pair','peer'],required=True)
    args=ap.parse_args();before=source_lock()
    if args.phase=='pair':
        root=new_output(args.output)
        write_json(root/'FROZEN_INDEX.json',dict(spec=SPEC,source_sha256=before,kernel=MANIFEST,
            execution_commit=head(),scenarios=SPEC['scenarios_in_execution_order'],created_before_first_case=True))
        cases=['nominal','car1_common_wall_bias']
    else:
        root=args.output.resolve();frozen=json.loads((root/'FROZEN_INDEX.json').read_text())
        assert frozen['source_sha256']==before
        for s in ('nominal','car1_common_wall_bias'):
            assert json.loads((root/s/'RUN.json').read_text())['status']=='DONE'
        cases=['peer_bias']
    try:
        for scenario in cases:
            one(scenario,root)
        assert source_lock()==before
    except BaseException as error:
        write_json(root/('FAILED_'+args.phase+'.json'),dict(error=type(error).__name__+': '+str(error)))
        raise
    write_json(root/('CHECKPOINT_'+args.phase+'.json'),dict(status='DONE',source_sha256=before,
        results_bytes=size_guard(root),cases=cases))
if __name__=='__main__':main()
