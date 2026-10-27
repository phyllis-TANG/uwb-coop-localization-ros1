"""Offline synthetic-only evaluation; truth never enters the replay process."""
import csv
import json
import math
from pathlib import Path
import numpy as np
from io_utils import read_jsonl


def summarize(run,truth_path,scenario,seed):
    truth={r['epoch_ns']:r['vehicles'] for r in read_jsonl(truth_path)}
    epochs=sorted(truth); origin=epochs[0]; finish=epochs[-1]; results=[]; series=[]; groups={}
    with (Path(run)/'estimate.csv').open() as stream:
        for row in csv.DictReader(stream): groups.setdefault((row['method_id'],row['vehicle_id']),[]).append(row)
    mode=json.loads((Path(run)/'run.json').read_text())['motion_mode']
    final=json.loads((Path(run)/'summary.json').read_text())['methods']
    for (method,car),rows in groups.items():
        errors=[]; yaws=[]; biaserrors=[]; current_errors=[]; valid_s=0.; gap_s=0.; intervals=[]
        for index,row in enumerate(rows):
            pub=int(row['publish_receive_epoch_ns']); anchor=int(row['state_epoch_ns']) if row['state_epoch_ns'] else None
            dt=max(0,min(int(rows[index+1]['publish_receive_epoch_ns']) if index+1<len(rows) else pub,finish)-max(pub,origin))/1e9
            valid_s+=dt*int(row['valid']); gap_s+=dt*int(row['unobserved_motion_gap'])
            if anchor not in truth or not row['x_m']: continue
            actual=truth[anchor][car]; pose=actual['pose']; xy=math.hypot(float(row['x_m'])-pose[0],float(row['y_m'])-pose[1]); yaw=math.atan2(math.sin(float(row['yaw_rad'])-pose[2]),math.cos(float(row['yaw_rad'])-pose[2]))
            pub_grid=origin+((min(pub,finish)-origin)//5_000_000)*5_000_000
            current=truth[pub_grid][car]['pose']; xy_current=math.hypot(float(row['x_m'])-current[0],float(row['y_m'])-current[1])
            b=float(row['gyro_bias_rad_s']) if row['gyro_bias_rad_s'] else None; berr=b-actual['gyro_bias_rad_s'] if b is not None else None
            errors.append(xy); yaws.append(yaw); current_errors.append(xy_current)
            if berr is not None: biaserrors.append(berr)
            intervals.append((pub-origin)/1e9)
            series.append(dict(scenario=scenario,seed=seed,motion_mode=mode,method=method,vehicle_id=car,
                publish_receive_epoch_ns=pub,state_epoch_ns=anchor,t_s=(pub-origin)/1e9,state_t_s=(anchor-origin)/1e9,
                x_m=float(row['x_m']),y_m=float(row['y_m']),truth_x_m=pose[0],truth_y_m=pose[1],truth_yaw_rad=pose[2],
                xy_error_at_state_m=xy,xy_error_at_publication_m=xy_current,yaw_error_rad=yaw,gyro_bias_rad_s=b,truth_bias_rad_s=actual['gyro_bias_rad_s'],
                bias_error_rad_s=berr,gyro_bias_variance=float(row['gyro_bias_variance']) if row['gyro_bias_variance'] else None,
                valid=int(row['valid']),unobserved_motion_gap=int(row['unobserved_motion_gap']),status=row['fallback_status']))
        fs=final[method]['final_filter_state']; gram=fs.get('wall_only_initial_state_linearized_gramian',{}).get(car)
        spectrum=np.linalg.eigvalsh(gram).tolist() if gram else None
        rmse=lambda vals: float(np.sqrt(np.mean(np.square(vals)))) if vals else None
        tail=[e for t,e in zip(intervals,errors) if t>=34.]
        results.append(dict(scenario=scenario,seed=seed,motion_mode=mode,method=method,vehicle_id=car,
            samples=len(errors),xy_rmse_state_m=rmse(errors),xy_max_state_m=max(errors) if errors else None,
            xy_rmse_publication_m=rmse(current_errors),yaw_rmse_rad=rmse(yaws),bias_rmse_rad_s=rmse(biaserrors),
            xy_rmse_recovery_34_40_m=rmse(tail),valid_duration_s=valid_s,invalid_duration_s=(finish-origin)/1e9-valid_s,
            retained_gap_flag_duration_s=gap_s,wall_gramian_eigenvalues=spectrum,
            bias_terminal_variance=rows[-1]['gyro_bias_variance'],event_status_counts=final[method]['events']))
    return results,series


def csv_write(path,rows):
    if not rows: return
    with Path(path).open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n'); w.writeheader()
        for row in rows: w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in row.items()})
