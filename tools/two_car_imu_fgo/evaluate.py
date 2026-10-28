#!/usr/bin/env python3
"""Independent artifact-only evaluation; no online graph/frontend imports."""
import argparse
import collections
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np
import independent as ind

ARMS=('M0','M1','M2','M3');SCENARIOS=('nominal','gyro_constant_bias','car1_gyro_gap','peer_bias','car1_common_wall_bias');SEEDS=(101,211)
CARS=('car1','car2')
SEGMENTS={'all':lambda t:True,'pre':lambda t:3<=t<24,'fault':lambda t:24<=t<38,'recovery':lambda t:38<=t<48,'late':lambda t:48<=t<=63}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n')
def csv_write(p,rows):
    if not rows:return
    with Path(p).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def errors(row,truth,config):
    d=row['state_dimension_per_keyframe'];stride=d//2;x=row['pose'];out={}
    if x is None:return None
    for i,c in enumerate(CARS):
        pose=x[stride*i:stride*i+3];ant=ind.ant(pose,config['models'][c]);reference=truth['cars'][c]
        b=row['bias_rad_s'][c]
        out[c]=dict(base_xy_m=float(np.linalg.norm(np.asarray(pose[:2])-reference['pose'][:2])),
            antenna_xy_m=float(np.linalg.norm(ant[:2]-reference['antenna_xyz_m'][:2])),
            yaw_rad=ind.wrap(pose[2]-reference['pose'][2]),bias_rad_s=None if b is None else b-reference['bias_rad_s'])
    a=ind.ant(x[:stride],config['models']['car1']);b=ind.ant(x[stride:],config['models']['car2'])
    ta=np.asarray(truth['cars']['car1']['antenna_xyz_m']);tb=np.asarray(truth['cars']['car2']['antenna_xyz_m'])
    out['pair']=dict(relative_xy_m=float(np.linalg.norm((a-b)[:2]-(ta-tb)[:2])),distance_m=float(np.linalg.norm(a-b)-np.linalg.norm(ta-tb)))
    return out


def rmse(v):
    v=[x for x in v if x is not None];return None if not v else float(np.sqrt(np.mean(np.square(v))))


def evaluate(root,output):
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    index=json.loads((root/'RUN_INDEX.json').read_text());expected={f'{s}_seed{k}_{a}' for s in SCENARIOS for k in SEEDS for a in ARMS}
    ind.require(len(index['cells'])==40 and {r['run_id'] for r in index['cells']}==expected and all(c['status']=='DONE' for c in index['cells']),'complete 40 index')
    audits=[];data={};timeline=[];costs=[]
    for cell in index['cells']:
        artifact_root=(root/index['artifact_root']).resolve() if 'artifact_root' in index else root
        run=artifact_root/cell['run_path'] if 'run_path' in cell else root/'runs'/cell['run_id']
        inp=artifact_root/cell['input_path'] if 'input_path' in cell else root/'inputs'/cell['case']
        meta=json.loads((run/'run.json').read_text());config=json.loads((run/'config.json').read_text())
        ind.require(sha(run/'run.json')==cell['run_sha256'],'run identity SHA')
        ind.require(meta['input_sha256']==cell['input_sha256'] and meta['config_sha256']==cell['config_sha256'],'paired input/config SHA')
        ind.require(meta['source_sha256']==cell.get('expected_source_sha256',index['source_sha256']) and meta['code_commit']==cell.get('expected_code_commit',index['code_commit']) and not meta['worktree_dirty'],'frozen execution SHA')
        for name,digest in index['inputs'][cell['case']].items():ind.require(sha(inp/name)==digest,'input/truth/label SHA')
        audit=ind.audit_run(run,inp/'events.jsonl.gz',all_marginals=True);audit['run_id']=cell['run_id'];audits.append(audit);print('AUDIT',cell['run_id'],audit['status'],flush=True)
        rows=ind.lines(run/'updates.jsonl.gz');truth={t['state_epoch_ns']:t for t in ind.lines(inp/'truth.jsonl.gz')}
        vals={r['state_epoch_ns']:dict(row=r,errors=errors(r,truth[r['state_epoch_ns']],config)) for r in rows}
        data[cell['scenario'],cell['seed'],cell['method']]=vals
        summary=json.loads((run/'summary.json').read_text());costs.append(dict(run_id=cell['run_id'],method=cell['method'],scenario=cell['scenario'],seed=cell['seed'],
            publications=len(rows),finite=sum(r['pose'] is not None for r in rows),accepted=sum(r['accepted_graph'] for r in rows),
            car1_valid=sum(r['estimate_valid']['car1'] for r in rows),car2_valid=sum(r['estimate_valid']['car2'] for r in rows),joint_valid=sum(r['joint_estimate_valid'] for r in rows),
            warmup=sum('warmup' in r['status'] for r in rows),solve_failed=sum('solver_failed' in r['status'] or 'solver_error' in r['status'] for r in rows),
            marginal_failed=sum('marginal_error' in r['status'] for r in rows),missing_odom=sum(r['status']=='missing_odom_bracket' for r in rows),
            missing_gyro_car1=sum(r.get('angular_intervals') is not None and not r['angular_intervals']['car1']['valid'] for r in rows),
            missing_gyro_car2=sum(r.get('angular_intervals') is not None and not r['angular_intervals']['car2']['valid'] for r in rows),
            odom_yaw_fallback=sum(r['odom_yaw_fallback'] for r in rows),peer_added=sum(r['peer_factor_used'] for r in rows),
            unknown_gyro=sum(sum(v for k,v in d.items() if k not in ('disabled','angular_control_accepted')) for d in summary['angular_decisions'].values()),
            elapsed_s=summary['elapsed_s'],update_total_s=summary['update_wall_total_s'],update_p95_s=summary['update_wall_p95_s'],
            peak_scalars=summary['peak_solve_scalar_variables'],peak_transient_scalars=summary['peak_transient_scalar_variables'],
            angular_peak=max(summary['angular_buffer_peaks'].values())))
        for ep,v in vals.items():
            r=v['row'];e=v['errors'];stride=r['state_dimension_per_keyframe']//2
            for i,c in enumerate(CARS):
                timeline.append(dict(scenario=cell['scenario'],seed=cell['seed'],method=cell['method'],vehicle=c,
                    state_epoch_ns=ep,state_time_s=r['state_time_s'],availability_cutoff_epoch_ns=r['availability_cutoff_epoch_ns'],
                    estimated_worker_finish_s=r['estimated_worker_finish_s'],valid=r['estimate_valid'][c],accepted=r['accepted_graph'],
                    status=r['status'],angular_valid=r['angular_valid'][c],base_x_m=r['pose'][i*stride] if r['pose'] else None,
                    base_y_m=r['pose'][i*stride+1] if r['pose'] else None,yaw_rad=r['pose'][i*stride+2] if r['pose'] else None,
                    bias_rad_s=r['bias_rad_s'][c],**({k+'_error':v for k,v in e[c].items()} if e else {k+'_error':None for k in ('base_xy_m','antenna_xy_m','yaw_rad','bias_rad_s')})))
    tables=[];common={}
    for scenario in SCENARIOS:
        for seed in SEEDS:
            sets=[data[scenario,seed,a] for a in ARMS];epochs=set.intersection(*(set(s) for s in sets))
            commonvalid={t for t in epochs if all(s[t]['row']['joint_estimate_valid'] for s in sets)}
            commonaccepted={t for t in epochs if all(s[t]['row']['accepted_graph'] for s in sets)}
            common[scenario,seed]=commonvalid
            for arm in ARMS:
                vals=data[scenario,seed,arm]
                for mask in ('all_finite','per_vehicle_valid','joint_common_accepted','joint_common_valid'):
                    for segment,selector in SEGMENTS.items():
                        for c in (*CARS,'pair'):
                            selected=[v for t,v in vals.items() if v['errors'] is not None and selector(v['row']['state_time_s']) and
                                (mask=='all_finite' or (mask=='joint_common_accepted' and t in commonaccepted) or (mask=='joint_common_valid' and t in commonvalid) or
                                 (mask=='per_vehicle_valid' and (v['row']['joint_estimate_valid'] if c=='pair' else v['row']['estimate_valid'][c])))]
                            keys=('relative_xy_m','distance_m') if c=='pair' else ('base_xy_m','antenna_xy_m','yaw_rad','bias_rad_s')
                            for key in keys:
                                vv=[v['errors'][c][key] for v in selected]
                                tables.append(dict(scenario=scenario,seed=seed,method=arm,mask=mask,segment=segment,vehicle=c,metric=key,
                                    denominator_all_publications=sum(selector(v['row']['state_time_s']) for v in vals.values()),
                                    selected_publications=len(selected),metric_valid_n=sum(x is not None for x in vv),rmse=rmse(vv)))
    deltas=[]
    for scenario in SCENARIOS:
        for seed in SEEDS:
            for segment,selector in SEGMENTS.items():
                times={t for t in common[scenario,seed] if selector(data[scenario,seed,'M0'][t]['row']['state_time_s'])}
                for c in (*CARS,'pair'):
                    for key in (('relative_xy_m','distance_m') if c=='pair' else ('base_xy_m','antenna_xy_m','yaw_rad')):
                        for a,b,role in [('M2','M0','IMU_independent'),('M3','M1','IMU_joint'),('M1','M0','peer_without_IMU'),('M3','M2','peer_with_IMU')]:
                            av=rmse([data[scenario,seed,a][t]['errors'][c][key] for t in times]);bv=rmse([data[scenario,seed,b][t]['errors'][c][key] for t in times])
                            deltas.append(dict(scenario=scenario,seed=seed,segment=segment,vehicle=c,metric=key,comparison=a+'-'+b,role=role,n=len(times),
                                a_rmse=av,b_rmse=bv,delta=None if av is None or bv is None else av-bv))
    propagation=[]
    for scenario in SCENARIOS[1:]:
        for seed in SEEDS:
            for segment,selector in SEGMENTS.items():
                times={t for t in common[scenario,seed]&common['nominal',seed] if selector(data[scenario,seed,'M0'][t]['row']['state_time_s'])}
                for arm in ARMS:
                    for car in CARS:
                        for key in ('antenna_xy_m','yaw_rad'):
                            fault=rmse([data[scenario,seed,arm][t]['errors'][car][key] for t in times]);nominal=rmse([data['nominal',seed,arm][t]['errors'][car][key] for t in times])
                            propagation.append(dict(scenario=scenario,seed=seed,segment=segment,method=arm,vehicle=car,metric=key,n=len(times),
                                scenario_rmse=fault,nominal_rmse=nominal,increment=None if fault is None or nominal is None else fault-nominal))
    dump(output/'audits.json',dict(status='PASS',runs=audits,complete_matrix=True,all_recorded_marginalizations_FD_checked=True))
    csv_write(output/'metrics.csv',tables);csv_write(output/'contrasts.csv',deltas);csv_write(output/'propagation.csv',propagation);csv_write(output/'costs.csv',costs)
    with gzip.open(output/'timeline.csv.gz','xt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timeline[0]));w.writeheader();w.writerows(timeline)
    dump(output/'evaluation.json',dict(status='PASS',cells=40,publications=sum(c['publications'] for c in costs),
        counts={k:sum(c[k] for c in costs) for k in ('finite','accepted','car1_valid','car2_valid','joint_valid','warmup','solve_failed','marginal_failed','missing_odom','missing_gyro_car1','missing_gyro_car2','odom_yaw_fallback')},
        common_valid={f'{s}_seed{k}':len(v) for (s,k),v in common.items()},evaluator_sha256=sha(__file__),independent_source_sha256=sha(ind.__file__),
        limitations=['already exposed synthetic development seeds, not independent validation','correlated timestamps not independent trials','virtual timings not ROS latency','M2 per-car F3 stopping; M3 joint stopping; identical engineering parameters']))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();evaluate(a.matrix,a.output)
