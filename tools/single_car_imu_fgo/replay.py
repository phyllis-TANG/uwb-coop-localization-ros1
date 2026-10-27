#!/usr/bin/env python3
"""F0 original20s graph; F1 odom rate; F2 gyro fixed0; F3 gyro+bias graph."""
import argparse
from collections import Counter
import copy
import csv
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from configuration import ARMS,validate
from frontend import ImuReplay,convert
from legacy import FixedLagReplay
from io_utils import append,clean,dump,external_path,git_state,gzip_writer,outputs,packages,read_jsonl,sha,sources,utc

COLUMNS=['state_time_s','availability_cutoff_s','status','accepted_graph','base_x_m','base_y_m','yaw_rad','antenna_x_m','antenna_y_m',
         'aligned_odom_antenna_x_m','aligned_odom_antenna_y_m','graph_states','graph_time_span_s','marginalizations','solve_wall_s','marginal_wall_s','update_wall_s',
         'position_correction_m','yaw_correction_deg','optimizer_nfev','dependency_receipt_max_s','estimated_worker_queue_s','range_medians_json','sample_counts_json',
         'arm','state_epoch_ns','availability_cutoff_epoch_ns','bias_rad_s','bias_estimated','angular_valid','estimate_valid','odom_yaw_fallback',
         'prediction_yaw_source','missing_angular_edges_cumulative','scalar_variables','state_dimension_per_keyframe','numerical_rank','angular_source','estimated_available_epoch_ns','publication_delay_s']


def validate_events(events,config):
    last=None; case=set()
    for e in events:
        if e.get('kind') not in ('odom','uwb','imu','clock','other'): raise ValueError('event kind')
        for k in ('receive_epoch_ns','record_index'):
            if type(e.get(k)) is not int: raise ValueError('exact integer '+k)
        if e['kind'] in ('odom','uwb','imu'):
            if type(e.get('header_epoch_ns')) is not int: raise ValueError('exact integer header')
            for k in ('source_file_sha256','topic'):
                if not isinstance(e.get(k),str) or not e[k]: raise ValueError('missing identity '+k)
        if last is not None and e['receive_epoch_ns']<last: raise ValueError('input must retain recorded receive order; no offline source sort')
        last=e['receive_epoch_ns']; case.add(e.get('case_id'))
        if {'truth','fault_label','true_pose','true_bias'} & set(e): raise ValueError('truth/labels prohibited in estimator events')
    if not events or len(case)!=1 or None in case: raise ValueError('single identified input case required')
    if config['scope']=='field' and not case.issubset({'004023','005135','T08','T10'}): raise ValueError('field allowlist excludes holdouts')


def csv_row(row,arm):
    pose=row.get('pose'); xy=row.get('antenna_xy_m'); aligned=row.get('aligned_odom_antenna_xy_m'); opt=row.get('optimizer',{})
    result={k:row.get(k) for k in COLUMNS}
    result['estimated_available_epoch_ns']=row['state_epoch_ns']+round((row['estimated_worker_finish_s']-row['state_time_s'])*1e9)
    result['publication_delay_s']=row['estimated_worker_finish_s']-row['state_time_s']
    result.update(base_x_m=pose[0] if pose else None,base_y_m=pose[1] if pose else None,yaw_rad=pose[2] if pose else None,
                  antenna_x_m=xy[0] if xy else None,antenna_y_m=xy[1] if xy else None,
                  aligned_odom_antenna_x_m=aligned[0] if aligned else None,aligned_odom_antenna_y_m=aligned[1] if aligned else None,
                  optimizer_nfev=opt.get('optimizer_nfev'),range_medians_json=json.dumps(row.get('range_medians_m'),sort_keys=True),
                  sample_counts_json=json.dumps(row.get('range_sample_counts'),sort_keys=True),bias_estimated=int(arm=='F3'),arm=arm)
    return result


def make_replay(config,on_output,origin):
    arm=config.get('arm','F0')
    if arm!='F0': return ImuReplay(config,on_output,origin,config['fixed_lag_s'])
    def forward(r):
        # Only annotate output; leave original initialization, failure, factors and bins unchanged.
        n=r['graph_states']; r.update(arm='F0',state_epoch_ns=origin+round(r['state_time_s']*1e9),availability_cutoff_epoch_ns=origin+round(r['availability_cutoff_s']*1e9),
            bias_rad_s=None,bias_estimated=False,angular_valid=None,estimate_valid=bool(r['accepted_graph']),odom_yaw_fallback=False,
            prediction_yaw_source='legacy_odom_pose',scalar_variables=3*n,state_dimension_per_keyframe=3,angular_source='legacy_odom_pose',
            missing_angular_edges_cumulative=0,field_accuracy_evaluated=False)
        on_output(r)
    return FixedLagReplay(config['model'],config['replay'],forward,lag_s=config['fixed_lag_s'],max_nfev=config['optimizer']['max_nfev'],max_sensor_samples=config['frontend']['max_sensor_samples_per_stream'])


def execute(events,config,on_output):
    validate(config); validate_events(events,config); origin=events[0]['receive_epoch_ns']; replay=make_replay(config,on_output,origin)
    for raw in events: replay.ingest(convert(raw,config,origin))
    replay.finish(); return replay


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--events-jsonl',type=Path,required=True); parser.add_argument('--config',type=Path,required=True); parser.add_argument('--output',type=Path,required=True); parser.add_argument('--max-seconds',type=float,default=120.)
    a=parser.parse_args(argv); started=time.monotonic(); run=None
    try:
        if not 0<a.max_seconds<=18000: raise ValueError('bounded runtime required')
        config=json.loads(a.config.read_text()); validate(config); events=list(read_jsonl(a.events_jsonl)); validate_events(events,config)
        root=external_path(a.output); root.mkdir(parents=True,exist_ok=False); origin=events[0]['receive_epoch_ns']; arm=config.get('arm','F0')
        source_lock=sources(); run=dict(schema_version=1,status='IN_PROGRESS',role='single_car_20s_IMU_factor_graph',created_at_utc=utc(),**git_state(),
             command_argv=[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]),source_sha256=source_lock,
             config_sha256=sha(a.config),input=dict(sha256=sha(a.events_jsonl),source_path=str(a.events_jsonl),case_id=events[0]['case_id']),
             epoch_origin_ns=origin,arm=arm,environment=dict(python=sys.version,packages=packages()),publications=0,field_accuracy_evaluated=False)
        dump(root/'run.json',run); dump(root/'config.json',config); counts=Counter(); outputs_count=0
        with (root/'published.csv').open('x',newline='') as stream,gzip_writer(root/'updates.jsonl.gz') as journal,gzip_writer(root/'input_decisions.jsonl.gz') as decisions:
            writer=csv.DictWriter(stream,fieldnames=COLUMNS,lineterminator='\n'); writer.writeheader()
            def sink(row):
                nonlocal outputs_count
                writer.writerow(csv_row(row,arm)); append(journal,clean(row)); outputs_count+=1; counts[row['status']]+=1; run['publications']=outputs_count
                if outputs_count%10==0: stream.flush(); journal.flush(); dump(root/'run.json',run)
            replay=make_replay(config,sink,origin)
            for index,raw in enumerate(events):
                if time.monotonic()-started>a.max_seconds: raise TimeoutError('single replay time budget')
                event=convert(raw,config,origin); status=replay.ingest(event); flags=[]; safe=clean(raw,flags=flags)
                append(decisions,dict(event_index=index,input=safe,nonfinite_input_fields=flags,angular_status=status if status is not None else 'legacy_ignored_or_original_handling',mapped_identity=event.identity))
            replay.finish()
        graph=replay.graph
        dump(root/'final_active_graph.json',dict(times_s=graph.times,states=np.asarray(graph.states).tolist(),prior_point=graph.prior.point.tolist(),prior_matrix=graph.prior.matrix.tolist(),prior_offset=graph.prior.offset.tolist(),eliminated_constant=graph.eliminated_constant,
             intervals=getattr(graph,'intervals',None),observations=graph.observations,local_odom=np.asarray(graph.local).tolist()))
        dump(root/'summary.json',dict(arm=arm,publications=outputs_count,status_counts=dict(counts),counters=dict(replay.counters),
             peak_solve_keyframes=graph.peak_solve_states,peak_transient_keyframes=graph.peak_transient_states,
             peak_solve_scalar_variables=graph.peak_solve_states*(4 if arm=='F3' else 3),marginalizations=graph.marginalizations,
             sensor_buffer_peaks=dict(replay.sensor_peaks,angular=replay.angular.peak if arm!='F0' else 0),
             angular_rejections=dict(replay.rejections) if arm!='F0' else {},field_accuracy_evaluated=False,
             caveats=['Odom yaw still expresses common body translation; no statistical independence claim','historical factors frozen after linearization, not full batch equivalence','1s input wait plus measured compute/virtual queue; no hardware latency guarantee','no endpoint/reference factor or field trajectory truth']))
        if source_lock!=sources(): raise ValueError('source changed during run')
        run.update(status='DONE',finished_at_utc=utc(),elapsed_s=time.monotonic()-started,outputs=outputs(root)); dump(root/'run.json',run)
        print(json.dumps(dict(status=run['status'],arm=arm,publications=outputs_count,elapsed_s=run['elapsed_s']))); return 0
    except (Exception,KeyboardInterrupt) as error:
        if run is not None:
            run.update(status='FAILED',error=type(error).__name__+': '+str(error),elapsed_s=time.monotonic()-started,outputs=outputs(a.output)); dump(a.output/'run.json',run)
        print(type(error).__name__+': '+str(error),file=sys.stderr); return 1


if __name__=='__main__': raise SystemExit(main())
