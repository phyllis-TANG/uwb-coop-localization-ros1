#!/usr/bin/env python3
"""Four matched models, receipt-ordered virtual offline replay only."""
import argparse
import collections
import csv
import gzip
import json
from pathlib import Path
import sys
import time
import numpy as np
from frontend import JointReplay, ARMS
from io_utils import dump,external,git_state,lines,sha,sources,utc
from pinned import two_legacy

CARS=('car1','car2')
COLUMNS=['experiment_id','method_id','vehicle_id','state_time_s','availability_cutoff_s','state_epoch_ns','availability_cutoff_epoch_ns',
 'base_x_m','base_y_m','yaw_rad','bias_rad_s','bias_estimated','antenna_x_m','antenna_y_m','antenna_z_m','finite_output','accepted_graph','valid',
 'angular_valid','status','prediction_yaw_source','odom_yaw_fallback','peer_factor_used','graph_states','scalar_variables','numerical_rank',
 'marginalizations','solve_wall_s','marginal_wall_s','update_wall_s','estimated_worker_finish_s','estimated_worker_queue_s','timing_mode']


def csv_rows(row,config):
    stride=row['state_dimension_per_keyframe']//2
    for i,c in enumerate(CARS):
        p=None if row['pose'] is None else row['pose'][i*stride:i*stride+3]
        xy=None if p is None else two_legacy.antenna(p,config['models'][c]['base_to_antenna_body_xy_m'])
        out={k:row.get(k) for k in COLUMNS};out.update(vehicle_id=c,finite_output=p is not None,valid=row['estimate_valid'][c],
            angular_valid=row['angular_valid'][c],bias_rad_s=row['bias_rad_s'][c],bias_estimated=stride==4,
            prediction_yaw_source=row['prediction_yaw_source'][c],base_x_m=None if p is None else p[0],
            base_y_m=None if p is None else p[1],yaw_rad=None if p is None else p[2],
            antenna_x_m=None if xy is None else float(xy[0]),antenna_y_m=None if xy is None else float(xy[1]),
            antenna_z_m=None if p is None else config['models'][c]['antenna_height_m'])
        yield out


def run(events_path,config_path,method,output,max_seconds=900):
    from configuration import validate
    output=external(output);output.mkdir(parents=True,exist_ok=False);started=time.perf_counter()
    config=json.loads(Path(config_path).read_text());validate(config);lock=sources()
    info=dict(status='IN_PROGRESS',role='two_car_imu_fgo',method_id=method,created_at_utc=utc(),**git_state(),
        source_sha256=lock,config_sha256=sha(config_path),input_sha256=sha(events_path),input_path=str(events_path),
        command_argv=sys.argv,timing_mode='virtual',field_accuracy_evaluated=False)
    dump(output/'config.json',config);dump(output/'run.json',info);counts=collections.Counter();durations=[]
    try:
        with gzip.open(output/'updates.jsonl.gz','xt') as journal,gzip.open(output/'input_decisions.jsonl.gz','xt') as decisions,(output/'published.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=COLUMNS);writer.writeheader()
            def sink(row):
                counts[row['status']]+=1;durations.append(row['update_wall_s'])
                journal.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
                for out in csv_rows(row,config):writer.writerow(out)
            replay=None
            for raw in lines(events_path):
                if time.perf_counter()-started>max_seconds:raise TimeoutError('bounded cell runtime')
                if replay is None:
                    replay=JointReplay(config,method,sink,raw['receive_epoch_ns']);info['epoch_origin_ns']=replay.origin_ns
                result=replay.ingest(raw)
                decisions.write(json.dumps(dict(record_index=raw['record_index'],decision=result,angular_decision=replay.last_angular_decision))+'\n')
            if replay is None:raise ValueError('empty')
            replay.finish()
        graph=replay.graph
        dump(output/'final_active_graph.json',graph.snapshot())
        dump(output/'summary.json',dict(publications=replay.output_count,status_counts=dict(counts),counters=dict(replay.counters),
            angular_decisions={c:dict(v) for c,v in replay.angular_decisions.items()},
            peak_solve_keyframes=graph.peak_solve_states,peak_transient_keyframes=graph.peak_transient_states,
            peak_solve_scalar_variables=replay.d*graph.peak_solve_states,peak_transient_scalar_variables=replay.d*graph.peak_transient_states,
            angular_buffer_peaks={c:b.peak for c,b in replay.angular.items()},sensor_peaks={c:b.sensor_peaks for c,b in replay.binners.items()},
            peer_peak=replay.peer_peak,pending_peak=replay.pending_peak,marginalizations=graph.marginalizations,
            update_wall_total_s=sum(durations),update_wall_p95_s=float(np.percentile(durations,95)) if durations else None,
            elapsed_s=time.perf_counter()-started,timing_mode='virtual'))
        if sources()!=lock:raise RuntimeError('source changed during cell')
        info.update(status='DONE',finished_at_utc=utc(),elapsed_s=time.perf_counter()-started)
    except BaseException as e:
        info.update(status='FAILED',error=type(e).__name__+': '+str(e));raise
    finally:
        info['outputs']={p.name:sha(p) for p in output.iterdir() if p.name!='run.json'};dump(output/'run.json',info)
    return info


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--events',required=True,type=Path);p.add_argument('--config',required=True,type=Path)
    p.add_argument('--method',required=True,choices=ARMS);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();print(json.dumps(run(a.events,a.config,a.method,a.output)))
