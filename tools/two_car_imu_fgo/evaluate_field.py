#!/usr/bin/env python3
"""Saved-artifact field response diagnostics, no trajectory truth or online imports."""
import argparse
from collections import Counter
import csv
import gzip
import json
import math
from pathlib import Path
import numpy as np
import independent as ind
from evaluate import sha,dump,csv_write,rmse

ARMS=('M0','M1','M2','M3');CARS=('car1','car2')
ENDPOINT={'015334':{'car1':[1.5,4.,.17],'car2':[2.95,3.04,.20],'tape_m':1.743},
          '033248':{'car1':[1.45,2.98,.17],'car2':[2.95,3.04,.20],'tape_m':1.54}}


def evaluate(matrix,output):
    matrix=Path(matrix);output=Path(output);output.mkdir(exist_ok=False)
    index=json.loads((matrix/'RUN_INDEX.json').read_text());a=(matrix/index['artifact_root']).resolve()
    expected={c+'_'+m for c in ENDPOINT for m in ARMS}
    ind.require(len(index['cells'])==8 and {c['run_id'] for c in index['cells']}==expected and all(c['status']=='DONE' for c in index['cells']),'complete old eight cells')
    audits=[];data={};costs=[];timeline=[];failures=[]
    for cell in index['cells']:
        run=a/cell['run_path'];inp=a/cell['input_path'];meta=json.loads((run/'run.json').read_text());config=json.loads((run/'config.json').read_text())
        ind.require(sha(run/'run.json')==cell['run_sha256'],'run SHA')
        ind.require(meta['source_sha256']==cell['expected_source_sha256'] and meta['code_commit']==cell['expected_code_commit'] and not meta['worktree_dirty'],'execution SHA')
        ind.require(meta['input_sha256']==sha(inp/'events.jsonl.gz')==cell['input_sha256'] and meta['config_sha256']==sha(inp/'config.json')==cell['config_sha256'],'input/config')
        audit=ind.audit_run(run,inp/'events.jsonl.gz',all_marginals=True);audit['run_id']=cell['run_id'];audits.append(audit)
        print('AUDIT',cell['run_id'],audit['status'],flush=True)
        rows=ind.lines(run/'updates.jsonl.gz');summary=json.loads((run/'summary.json').read_text());case=cell['case'];method=cell['method'];vals={}
        for row in rows:
            epoch=row['state_epoch_ns'];d=row['state_dimension_per_keyframe'];stride=d//2;pose=row['pose'];ants=[];carrows=[]
            for i,car in enumerate(CARS):
                x=pose[i*stride:i*stride+stride];ant=ind.ant(x,config['models'][car]);ants.append(ant)
                walls=row['bins'][car]['observations'];model=config['models'][car]
                residuals=[float(np.linalg.norm(ant-model['anchors_xyz_m'][k])-(z-model['range_bias_m'][k])) for k,z in walls.items()]
                item=dict(case=case,method=method,vehicle=car,state_epoch_ns=epoch,state_time_s=row['state_time_s'],
                    availability_cutoff_epoch_ns=row['availability_cutoff_epoch_ns'],accepted=row['accepted_graph'],valid=row['estimate_valid'][car],
                    joint_valid=row['joint_estimate_valid'],status=row['status'],angular_valid=row['angular_valid'][car],
                    antenna_x_m=float(ant[0]),antenna_y_m=float(ant[1]),yaw_rad=x[2],bias_rad_s=row['bias_rad_s'][car],
                    wall_residual_rms_m=rmse(residuals),wall_factor_n=len(walls),peer_factor_used=row['peer_factor_used'])
                carrows.append(item)
            distance=float(np.linalg.norm(ants[0]-ants[1]));observed=row['peer_median_m']
            for item in carrows:item.update(distance_m=distance,peer_residual_m=None if observed is None else distance-observed);timeline.append(item)
            vals[epoch]=dict(row=row,carrows=carrows)
            if 'solver_' in row['status'] or 'marginal_error' in row['status']:failures.append(dict(case=case,method=method,state_time_s=row['state_time_s'],status=row['status'],optimizer=row['optimizer']))
        data[case,method]=vals
        costs.append(dict(case=case,method=method,publications=len(rows),finite=sum(r['pose'] is not None for r in rows),
            accepted=sum(r['accepted_graph'] for r in rows),car1_valid=sum(r['estimate_valid']['car1'] for r in rows),car2_valid=sum(r['estimate_valid']['car2'] for r in rows),
            joint_valid=sum(r['joint_estimate_valid'] for r in rows),warmup=sum('warmup' in r['status'] for r in rows),
            solver_failed=sum('solver_' in r['status'] for r in rows),marginal_failed=sum('marginal_error' in r['status'] for r in rows),
            missing_odom=sum(r['status']=='missing_odom_bracket' for r in rows),
            missing_gyro_car1=sum(r.get('angular_intervals') is not None and not r['angular_intervals']['car1']['valid'] for r in rows),
            missing_gyro_car2=sum(r.get('angular_intervals') is not None and not r['angular_intervals']['car2']['valid'] for r in rows),
            unknown_gyro=sum(sum(v for k,v in t.items() if k not in ('disabled','angular_control_accepted')) for t in summary['angular_decisions'].values()),
            missing_peer=sum(r['peer_median_m'] is None for r in rows),odom_yaw_fallback=sum(r['odom_yaw_fallback'] for r in rows),
            elapsed_s=summary['elapsed_s'],update_total_s=summary['update_wall_total_s'],update_p95_s=summary['update_wall_p95_s'],
            peak_scalars=summary['peak_solve_scalar_variables'],peak_transient_scalars=summary['peak_transient_scalar_variables']))
    stats=[];common={}
    for case in ENDPOINT:
        sets=[data[case,m] for m in ARMS];epochs=set.intersection(*(set(x) for x in sets))
        accepted={t for t in epochs if all(x[t]['row']['accepted_graph'] for x in sets)}
        valid={t for t in epochs if all(x[t]['row']['joint_estimate_valid'] for x in sets)}
        common[case]=dict(all_epochs=len(epochs),joint_common_accepted=len(accepted),joint_common_valid=len(valid))
        tail=set(sorted(epochs)[-5:])
        for method in ARMS:
            for mask in ('all_finite','per_vehicle_valid','joint_common_accepted','joint_common_valid'):
                for segment in ('all','last_five_publications','legacy_static_window'):
                    for i,car in enumerate(CARS):
                        def in_segment(t,v):
                            s=v['row']['state_time_s'];return segment=='all' or (segment=='last_five_publications' and t in tail) or (segment=='legacy_static_window' and (85<=s<=94.8 if case=='015334' else 0<=s<=5))
                        denominator=[(t,v) for t,v in data[case,method].items() if in_segment(t,v)]
                        selected=[v['carrows'][i] for t,v in denominator if mask=='all_finite' or (mask=='per_vehicle_valid' and v['row']['estimate_valid'][car]) or (mask=='joint_common_accepted' and t in accepted) or (mask=='joint_common_valid' and t in valid)]
                        for metric in ('antenna_x_m','antenna_y_m','yaw_rad','bias_rad_s','wall_residual_rms_m','distance_m','peer_residual_m'):
                            vv=[v[metric] for v in selected if v[metric] is not None]
                            # Response only. Circular mean for yaw; no claimed reference accuracy.
                            mean=None if not vv else (math.atan2(np.mean(np.sin(vv)),np.mean(np.cos(vv))) if metric=='yaw_rad' else float(np.mean(vv)))
                            stats.append(dict(case=case,method=method,vehicle=car,mask=mask,segment=segment,metric=metric,denominator=len(denominator),selected_n=len(selected),metric_n=len(vv),mean=mean,
                                std=None if not vv else float(np.std([ind.wrap(v-mean) for v in vv] if metric=='yaw_rad' else vv))))
                        if segment=='last_five_publications':
                            xy=[np.linalg.norm(np.array([v['antenna_x_m'],v['antenna_y_m']])-ENDPOINT[case][car][:2]) for v in selected]
                            for metric,vv in [('manual_stop_xy_separation_m',xy),('manual_tape_distance_difference_m',[v['distance_m']-ENDPOINT[case]['tape_m'] for v in selected])]:
                                stats.append(dict(case=case,method=method,vehicle=car,mask=mask,segment=segment,metric=metric,denominator=len(denominator),selected_n=len(selected),metric_n=len(vv),mean=None if not vv else float(np.mean(vv)),std=None if not vv else float(np.std(vv))))
    dump(output/'audits.json',dict(status='PASS',runs=audits,all_marginals_checked=True));dump(output/'failures.json',failures)
    csv_write(output/'costs.csv',costs);csv_write(output/'responses.csv',stats)
    with gzip.open(output/'timeline.csv.gz','xt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timeline[0]));w.writeheader();w.writerows(timeline)
    dump(output/'evaluation.json',dict(status='PASS',execution_level='conditional_development',strict_physical_branch='BLOCKED',cells=8,
        common=common,counts={k:sum(c[k] for c in costs) for k in ('publications','finite','accepted','car1_valid','car2_valid','joint_valid','warmup','solver_failed','missing_gyro_car1','missing_gyro_car2','unknown_gyro','missing_peer','odom_yaw_fallback')},
        reader_sha256=sha(ind.__file__),evaluator_sha256=sha(__file__),endpoint_evaluator_only=ENDPOINT,
        limitations=['no continuous trajectory/yaw/bias truth','manual stop discrepancy is uncalibrated development diagnostic; no trajectory RMSE/ATE','recorded receipt timing not physical sample synchronization','virtual availability and offline cost are not ROS latency']))
    plot(output,timeline)


def plot(output,rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=dict(zip(ARMS,['#666666','#e3892b','#337ab7','#218c63']))
    for case in ENDPOINT:
        fig,ax=plt.subplots(6,2,figsize=(13,12),sharex=True)
        for i,car in enumerate(CARS):
            for method in ARMS:
                rs=[r for r in rows if r['case']==case and r['vehicle']==car and r['method']==method];ts=[r['state_time_s'] for r in rs]
                for j,key in enumerate(('antenna_x_m','antenna_y_m','yaw_rad','bias_rad_s','wall_residual_rms_m','peer_residual_m')):
                    ax[j,i].plot(ts,[np.nan if r[key] is None else r[key]*(180/math.pi if key=='yaw_rad' else 1) for r in rs],label=method,color=colors[method],lw=1)
                    gaps=[r['state_time_s'] for r in rs if not r['angular_valid']]
                    if j==2 and method in ('M2','M3'):
                        for t in gaps:ax[j,i].axvline(t,color=colors[method],alpha=.18,lw=1)
                    ax[j,i].set_ylabel(key.replace('yaw_rad','yaw_deg'));ax[j,i].grid(alpha=.2)
            ax[0,i].set_title(case+' '+car+' conditional response, no continuous truth');ax[-1,i].set_xlabel('state time (s); receipt-association virtual timeline')
        ax[0,0].legend(ncol=4);fig.tight_layout();fig.savefig(output/(case+'.png'),dpi=140);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',type=Path,required=True);p.add_argument('--output',type=Path,required=True);v=p.parse_args();evaluate(v.matrix,v.output)
