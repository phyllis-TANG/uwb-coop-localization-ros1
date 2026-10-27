#!/usr/bin/env python3
"""Read compact frozen tables only. No estimator imports or optimization."""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[5]
OWN = Path(__file__).resolve().parent.parent
BASE = ROOT / 'docs/field_tests/20261024_25/single_car_quality_fgo_eval_v2'
PROTOCOL = ROOT / 'docs/field_tests/single_car_fixed_lag_20261022/protocol.json'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1048576), b''): h.update(block)
    return h.hexdigest()


def read_csv(path):
    with path.open(newline='') as f: return list(csv.DictReader(f))


def boolean(text):
    if text == 'True': return True
    if text == 'False': return False
    raise ValueError('Unexpected boolean: '+str(text))


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)+'\n')


def audit(output):
    output = output.resolve()
    if OWN not in output.parents: raise ValueError('Output must be in this task evidence directory')
    output.mkdir(parents=True, exist_ok=False)
    inputs = [BASE/'results/publication_diagnostics.csv', BASE/'results/four_groups.csv', PROTOCOL,
              BASE/'results/summary.json', BASE/'results/performance_matrix.json', BASE/'ARTIFACTS.json']
    rows = read_csv(inputs[0]); published = read_csv(inputs[1]); summary = json.loads(inputs[3].read_text())
    cases = {c['id']: c for c in json.loads(PROTOCOL.read_text())['cases']}
    reported = {(r['case_id'], r['group']): r for r in published}
    original = {c['case_id']: c['modes'] for c in summary['cases']}
    recomputed, selected_all, manifest_rows = [], [], []
    max_difference = 0.
    performance = BASE/'artifacts/quality-field-v2-performance.tar.gz'
    artifacts = json.loads((BASE/'ARTIFACTS.json').read_text())['artifacts']
    artifact_checks = []
    for a in artifacts:
        path = BASE/a['relative_path']; inputs.append(path)
        actual = sha(path); assert actual == a['sha256'], path
        artifact_checks.append(dict(kind=a['kind'], bytes=path.stat().st_size, sha256=actual))
    # Only read eight run manifests, never extract or execute archived programs.
    with tarfile.open(performance, 'r:gz') as tar:
        manifests = {}
        for c in ('004023', '005135'):
            for g in ('Q0', 'Q1', 'Q2', 'Q3'):
                member = f'FGO_B_20261027/performance_001/{c}_{g}/run.json'
                raw = tar.extractfile(member).read(); run = json.loads(raw)
                config = BASE/f'frozen_configs/{c}_{g}.json'; inputs.append(config)
                cfg = json.loads(config.read_text())
                assert cfg['base']['fixed_lag_s'] == 20.
                assert sha(config) == run['config_sha256']
                assert run['status'] == 'DONE' and not run['worktree_dirty']
                manifests[c,g] = run
                manifest_rows.append(dict(case_id=c, group=g, archived_member=member,
                    run_manifest_sha256=hashlib.sha256(raw).hexdigest(), code_commit=run['code_commit'],
                    config_sha256=run['config_sha256'], input_events_sha256=run['input_sha256'],
                    source_sha256=run['source_sha256'], timing_mode=run['timing_mode']))
    for c in ('004023', '005135'):
        case = cases[c]; low, high = map(lambda x: Decimal(str(x)), case['evaluation_window_s'])
        groups = {g: [r for r in rows if r['case_id'] == c and r['group'] == g] for g in ('Q0','Q1','Q2','Q3')}
        common = set.intersection(*[{int(r['state_epoch_ns']) for r in v if boolean(r['estimate_valid'])} for v in groups.values()])
        assert len(common) == len(original[c]['Q0'] and next(x for x in summary['cases'] if x['case_id']==c)['common_valid_state_epoch_ns'])
        assert len({manifests[c,g]['input_sha256'] for g in groups}) == 1
        for g, values in groups.items():
            epochs = [int(r['state_epoch_ns']) for r in values]
            assert len(epochs) == len(set(epochs)) and epochs == sorted(epochs)
            assert all(b-a == 1000000000 for a,b in zip(epochs,epochs[1:]))
            assert all(int(r['cutoff_epoch_ns'])-int(r['state_epoch_ns']) == 1000000000 for r in values)
            assert all(boolean(r['common_valid']) == (int(r['state_epoch_ns']) in common) for r in values)
            selected = [r for r in values if low <= Decimal(r['state_time_s']) <= high]
            assert len(selected) == 5 and all(boolean(r['estimate_valid']) for r in selected)
            points = [(float(r['antenna_x_m']),float(r['antenna_y_m'])) for r in selected]
            mid = [statistics.median(p[i] for p in points) for i in range(2)]
            endpoint = case['end_antenna_xyz_m'][:2]
            distance = math.hypot(mid[0]-endpoint[0],mid[1]-endpoint[1])
            scatter = math.sqrt(statistics.mean((p[0]-mid[0])**2+(p[1]-mid[1])**2 for p in points))
            drift = math.hypot(points[-1][0]-points[0][0],points[-1][1]-points[0][1])
            result = dict(case_id=c, group=g, published=len(values), valid=sum(boolean(r['estimate_valid']) for r in values),
                common_valid=len(common), warmup=sum(r['status']=='predict_only_warmup' for r in values),
                stop_samples=len(selected), stop_window_low_s=str(low), stop_window_high_s=str(high),
                selected_state_times_s=';'.join(r['state_time_s'] for r in selected),
                antenna_median_x_m=mid[0],antenna_median_y_m=mid[1],manual_stop_distance_m=distance,
                stop_scatter_rms_m=scatter,candidate_static_net_drift_m=drift)
            for key in ('published','valid','common_valid'): assert result[key] == int(reported[c,g][key])
            for key in ('antenna_median_x_m','antenna_median_y_m','manual_stop_distance_m','stop_scatter_rms_m','candidate_static_net_drift_m'):
                difference=abs(result[key]-float(reported[c,g][key]));max_difference=max(max_difference,difference)
                assert difference < 1e-12, (c,g,key,difference)
            assert list(map(float,case['evaluation_window_s'])) == original[c][g]['stop_window']['frozen_window_s']
            recomputed.append(result)
            selected_all.extend(dict(case_id=c,group=g,state_epoch_ns=r['state_epoch_ns'],state_time_s=r['state_time_s'],
                antenna_x_m=r['antenna_x_m'],antenna_y_m=r['antenna_y_m']) for r in selected)
    for name, data in [('recomputed_eight_groups.csv',recomputed),('selected_stop_samples.csv',selected_all)]:
        with (output/name).open('x',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    deltas=[]
    for c in ('004023','005135'):
        for a,b in [('Q0','Q2'),('Q1','Q3')]:
            x,y=[next(r for r in recomputed if r['case_id']==c and r['group']==g) for g in (a,b)]
            deltas.append(dict(case_id=c,comparison=a+'→'+b,manual_stop_distance_change_m=y['manual_stop_distance_m']-x['manual_stop_distance_m'],
                scatter_change_m=y['stop_scatter_rms_m']-x['stop_scatter_rms_m'],drift_change_m=y['candidate_static_net_drift_m']-x['candidate_static_net_drift_m']))
    dump(output/'run_manifests.json',manifest_rows)
    receipt=dict(status='PASS',estimator_runs=0,video_processing_runs=0,source_script_sha256=sha(__file__),
        rows_read=len(rows),performance_runs=8,published=sum(r['published'] for r in recomputed),valid=sum(r['valid'] for r in recomputed),
        warmup=sum(r['warmup'] for r in recomputed),stop_samples=sum(r['stop_samples'] for r in recomputed),
        max_abs_difference_vs_original_table_m=max_difference,paired_stop_differences=deltas,
        archive_sha_checks=artifact_checks,read_scope='compact tables, frozen configs and eight archived run manifests; no raw bag, video or full graph journal reread',
        source_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted(set(inputs))},
        manual_endpoint_uncertainty_m=None,continuous_trajectory_truth=None,complete_fault_labels=None,
        limitations=['same frozen candidate stop windows, not a new reference acceptance','scatter is about own median, not ground-truth RMSE',
                     'normal completion is not fault-free','archived semantic/optimization readback results are cited, not repeated here'])
    dump(output/'receipt.json',receipt)
    print(json.dumps({k:receipt[k] for k in ('status','rows_read','valid','warmup','stop_samples','max_abs_difference_vs_original_table_m')}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    audit(p.parse_args().output)
