"""Synthetic evaluation: all publications AND four-arm common valid times."""
import bisect
import csv
import json
import math
from pathlib import Path
import numpy as np
from io_utils import read_jsonl


def csv_write(path,rows):
    if not rows:return
    with Path(path).open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def read_csv(path):
    with Path(path).open() as stream:return list(csv.DictReader(stream))


def truth_lookup(records,epochs,stamp):
    if stamp<epochs[0] or stamp>epochs[-1]:return None
    i=bisect.bisect_right(epochs,stamp)-1
    if epochs[i]==stamp:return records[i]
    a,b=records[i],records[i+1];r=(stamp-epochs[i])/(epochs[i+1]-epochs[i]);p=np.array(a['pose'])+r*(np.array(b['pose'])-a['pose']);ant=np.array(a['antenna_xyz_m'])+r*(np.array(b['antenna_xyz_m'])-a['antenna_xyz_m'])
    return dict(pose=p,antenna_xyz_m=ant,bias_rad_s=a['bias_rad_s']+r*(b['bias_rad_s']-a['bias_rad_s']))


def evaluate_case(root,scenario,seed):
    root=Path(root);input_dir=root/'inputs'/f'{scenario}_seed{seed}';truth=list(read_jsonl(input_dir/'truth.jsonl.gz'));epochs=[r['epoch_ns'] for r in truth];origin=epochs[0]
    runs={};common=None
    for arm in ['F0','F1','F2','F3']:
        path=root/'runs'/f'{scenario}_seed{seed}__{arm}'
        if not (path/'run.json').exists() or json.loads((path/'run.json').read_text())['status']!='DONE':continue
        rows=read_csv(path/'published.csv');runs[arm]=(path,rows)
        valid={int(r['state_epoch_ns']) for r in rows if r['estimate_valid']=='True'};common=valid if common is None else common&valid
    if len(runs)!=4:common=set()
    metrics=[];series_by_arm={}
    for arm,(path,rows) in runs.items():
        series=[];attempts=[r for r in rows if int(r['graph_states'])>=3];failures=[r for r in attempts if r['accepted_graph']!='True'];summary=json.loads((path/'summary.json').read_text())
        for row in rows:
            stamp=int(row['state_epoch_ns']);t=(stamp-origin)/1e9;actual=truth_lookup(truth,epochs,stamp);available=int(row['estimated_available_epoch_ns']);at_available=truth_lookup(truth,epochs,available)
            pose=[float(row[k]) for k in ('base_x_m','base_y_m','yaw_rad')] if row['base_x_m'] else None
            xy=math.hypot(pose[0]-actual['pose'][0],pose[1]-actual['pose'][1]) if pose and actual else None
            yaw=math.atan2(math.sin(pose[2]-actual['pose'][2]),math.cos(pose[2]-actual['pose'][2])) if pose and actual else None
            avail_error=math.hypot(pose[0]-at_available['pose'][0],pose[1]-at_available['pose'][1]) if pose and at_available else None
            bias=float(row['bias_rad_s']) if row['bias_rad_s'] else None
            series.append(dict(scenario=scenario,seed=seed,arm=arm,state_epoch_ns=stamp,availability_cutoff_epoch_ns=int(row['availability_cutoff_epoch_ns']),estimated_available_epoch_ns=available,t_s=t,
                base_x_m=pose[0] if pose else None,base_y_m=pose[1] if pose else None,yaw_rad=pose[2] if pose else None,
                truth_base_x_m=float(actual['pose'][0]) if actual else None,truth_base_y_m=float(actual['pose'][1]) if actual else None,
                xy_error_state_m=xy,yaw_error_rad=yaw,xy_error_estimated_available_m=avail_error,
                bias_rad_s=bias,true_bias_rad_s=actual['bias_rad_s'] if actual else None,
                bias_error_rad_s=bias-actual['bias_rad_s'] if bias is not None and actual and arm in ('F2','F3') else None,
                estimate_valid=row['estimate_valid']=='True',accepted_graph=row['accepted_graph']=='True',angular_valid=row['angular_valid']=='True',
                common_valid=stamp in common,status=row['status'],publication_delay_s=float(row['publication_delay_s']),
                odom_yaw_fallback=row['odom_yaw_fallback']=='True',missing_angular_edges_cumulative=int(row['missing_angular_edges_cumulative']) if row['missing_angular_edges_cumulative'] else 0))
        rmse=lambda key,predicate=lambda r:True:float(np.sqrt(np.mean([r[key]**2 for r in series if r[key] is not None and predicate(r)]))) if any(r[key] is not None and predicate(r) for r in series) else None
        values=[r['xy_error_state_m'] for r in series if r['xy_error_state_m'] is not None];updates=[float(r['update_wall_s']) for r in rows]
        metrics.append(dict(scenario=scenario,seed=seed,arm=arm,total_publications=len(rows),finite_pose_publications=len(values),finite_pose_coverage=len(values)/len(rows),
            accepted_graph_publications=sum(r['accepted_graph'] for r in series),estimate_valid_publications=sum(r['estimate_valid'] for r in series),estimate_valid_coverage=sum(r['estimate_valid'] for r in series)/len(rows),
            common_valid_publications=len(common),angular_missing_publications=sum(not r['angular_valid'] for r in series) if arm!='F0' else 0,
            solve_attempts=len(attempts),solver_failures=len(failures),solver_failure_rate=len(failures)/len(attempts) if attempts else None,
            all_finite_xy_rmse_state_m=rmse('xy_error_state_m'),all_finite_xy_max_state_m=max(values) if values else None,
            all_finite_yaw_rmse_rad=rmse('yaw_error_rad'),all_finite_bias_rmse_rad_s=rmse('bias_error_rad_s'),
            common_valid_xy_rmse_state_m=rmse('xy_error_state_m',lambda r:r['common_valid']),common_valid_yaw_rmse_rad=rmse('yaw_error_rad',lambda r:r['common_valid']),
            all_finite_xy_rmse_estimated_available_m=rmse('xy_error_estimated_available_m'),available_truth_missing_publications=sum(r['xy_error_estimated_available_m'] is None for r in series),
            recovery_38_49_xy_rmse_m=rmse('xy_error_state_m',lambda r:38<=r['t_s']<50),
            mean_update_wall_s=float(np.mean(updates)),p95_update_wall_s=float(np.percentile(updates,95)),max_update_wall_s=max(updates),
            max_publication_delay_s=max(r['publication_delay_s'] for r in series),odom_yaw_fallback_publications=sum(r['odom_yaw_fallback'] for r in series),
            marginalizations=summary['marginalizations'],peak_solve_scalar_variables=summary['peak_solve_scalar_variables'],status_counts=summary['status_counts']))
        series_by_arm[arm]=series
    return metrics,series_by_arm
