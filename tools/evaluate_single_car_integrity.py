#!/usr/bin/env python3
"""After-run evaluation only. Reads truth/labels; never imported by estimator."""
from __future__ import annotations
import argparse
import collections
import csv
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from run_single_car_integrity_experiment import ROOT, DEFAULT, sha, write, read_rows, verify
from single_car_integrity import Trigger
from single_car_sequential_replay import bag_events
from run_single_car_sequential_baseline import endpoint


def csv_write(path,rows):
    if not rows:return
    fields=list(dict.fromkeys(k for row in rows for k in row))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def interp_truth(truth,times,columns):
    return np.column_stack([np.interp(times,truth['time_s'],truth[c]) for c in columns])


def recover_time(mask,times,start,consecutive=3):
    count=0
    for i,(ok,t) in enumerate(zip(mask,times)):
        count=count+1 if t>=start and ok else 0
        if count>=consecutive:return float(times[i-consecutive+1]-start)
    return None


def intervals(mask,times,ends,metadata):
    output=[];begin=None;end=None
    for active,t,e in zip(mask,times,ends):
        if active:
            if begin is None:begin=float(t)
            end=float(e)
        elif begin is not None:
            output.append(dict(metadata,start_s=begin,end_s=end,duration_s=end-begin));begin=None
    if begin is not None:output.append(dict(metadata,start_s=begin,end_s=end,duration_s=end-begin))
    return output


def summarize_run(runpath,thresholds,output):
    record=json.loads((runpath/'run.json').read_text())
    rows=read_rows(runpath/'output/updates.jsonl')
    truth=np.genfromtxt(runpath/'truth.csv',delimiter=',',names=True)
    labels=json.loads((runpath/'fault_labels.json').read_text())
    scenario=labels['scenario'];window=scenario['interval_s'];horizon=float(truth['time_s'][-1])
    state=np.array([r['state_time_s'] for r in rows]);ends=np.r_[state[1:],horizon];dt=np.maximum(0,ends-state)
    valid=np.array([r['pose'] is not None for r in rows])
    poses=np.array([r['antenna_xy_m'] if r['pose'] is not None else [np.nan,np.nan] for r in rows])
    true=interp_truth(truth,state,['antenna_x_m','antenna_y_m'])
    error=np.linalg.norm(poses-true,axis=1)
    active=np.zeros(len(rows),bool) if window is None else (state>=window[0])&(state<window[1])
    pre=np.ones(len(rows),bool) if window is None else state<window[0]
    post=np.zeros(len(rows),bool) if window is None else state>=window[1]
    summaries=[];timeseries=[];ranges=[];interval_rows=[]
    for method in ['M0','M1','M2']:
        if method=='M0':
            available=np.zeros(len(rows),bool);alarms=np.zeros(len(rows),bool);stats=[None]*len(rows)
        else:
            available=np.array([r[method]['available'] for r in rows])
            if record['group']=='diagnostic':
                alarms=np.array([r[method]['alarm'] is True for r in rows])
            else:
                trigger=Trigger(thresholds[method],2)
                alarms=np.array([trigger.update(r[method]['statistic'],r[method]['available']) is True for r in rows])
            stats=[r[method]['statistic'] for r in rows]
        available_times=np.array([r[method+'_available_receipt_s'] for r in rows])
        if np.any(np.diff(available_times)<0):raise AssertionError('Nonmonotonic output availability')
        costs=np.array([r['update_wall_s'] if method=='M0' else r[method+'_extra_wall_s'] for r in rows])
        successes=np.array([r['accepted_graph'] for r in rows])
        alarm_indices=np.where(active&alarms)[0]
        delay=float(available_times[alarm_indices[0]]-window[0]) if window and len(alarm_indices) else None
        result=dict(id=record['id'],group=record['group'],scenario=scenario['id'],category=scenario['category'],seed=record['seed'],method=method,
            states=len(rows),observed_state_duration_s=float(dt.sum()),initial_no_output_state_s=float(state[0]),
            initial_no_output_receipt_s=float(available_times[0]),state_rmse_m=float(np.sqrt(np.nanmean(error**2))),
            state_max_error_m=float(np.nanmax(error)),state_p95_error_m=float(np.nanpercentile(error,95)),
            normal_false_alarm_s=float(np.sum(dt[~active&alarms])) if method!='M0' else None,
            prefault_false_alarm_s=float(np.sum(dt[pre&alarms])) if method!='M0' else None,
            recovery_alarm_s=float(np.sum(dt[post&alarms])) if method!='M0' else None,
            unavailable_s=float(np.sum(dt[~available])) if method!='M0' else None,
            solver_failure_s=float(np.sum(dt[[r['status'].startswith('predict_only_solver_') for r in rows]])),
            prediction_fallback_s=float(np.sum(dt[~successes&valid])),missing_pose_s=float(np.sum(dt[~valid])),
            detected_fault=bool(len(alarm_indices)) if window and method!='M0' else None,
            detection_delay_receipt_s=delay,detected_before_recovery=bool(len(alarm_indices) and available_times[alarm_indices[0]]<window[1]) if window and method!='M0' else None,
            extra_compute_median_ms=float(np.median(costs)*1000),extra_compute_p95_ms=float(np.percentile(costs,95)*1000),
            extra_compute_max_ms=float(np.max(costs)*1000),extra_compute_total_s=float(costs.sum()),
            state_age_median_s=float(np.median(available_times-state)),state_age_max_s=float(np.max(available_times-state)),
            queue_max_s=max(r['modeled_event_queue_s'] for r in rows),
            alarm_recovery_state_s=recover_time(available&~alarms,state,window[1]) if window and method!='M0' else None,
            alarm_recovery_receipt_s=None,
            monitoring_note='not_installed' if method=='M0' else 'no_threshold_alarm is not a safety guarantee')
        if result['alarm_recovery_state_s'] is not None:
            index=np.where(state==window[1]+result['alarm_recovery_state_s'])[0][0]
            result['alarm_recovery_receipt_s']=float(available_times[index]-window[1])
        # Supplemental onset audit; preregistered primary remains first alarm
        # for an in-fault state. A pre-existing alarm is not causal detection.
        transitions=alarms & ~np.r_[False,alarms[:-1]]
        new_indices=np.where(active&transitions)[0]
        first_active=np.where(active)[0]
        result['alarm_already_active_at_fault_onset']=bool(len(first_active) and first_active[0]>0 and alarms[first_active[0]-1] and alarms[first_active[0]]) if window else None
        result['new_alarm_onset_during_fault']=bool(len(new_indices)) if window and method!='M0' else None
        result['new_alarm_delay_receipt_s']=float(available_times[new_indices[0]]-window[0]) if window and len(new_indices) else None
        result['timely_new_alarm_before_recovery']=bool(len(new_indices) and available_times[new_indices[0]]<window[1]) if window and method!='M0' else None
        # Availability-axis held diagnostics are separate from state-time errors.
        grid=np.arange(0,horizon,.05)
        latest=np.searchsorted(available_times,grid,side='right')-1
        has=latest>=0;index=np.maximum(latest,0)
        held_alarm=alarms[index]&has
        held_available=available[index]&has
        held_state_error=error[index]
        true_current=interp_truth(truth,grid,['antenna_x_m','antenna_y_m'])
        stale_error=np.linalg.norm(poses[index]-true_current,axis=1)
        result['receipt_axis_no_published_pose_s']=float(np.sum(~has)*.05)
        result['unpropagated_held_pose_current_truth_max_error_m']=float(np.nanmax(stale_error[has]))
        for limit in [.2,.5]:
            tag=str(limit).replace('.','p')
            exceed=error>limit
            result['exceed_'+tag+'_s']=float(np.sum(dt[exceed]))
            result['unalerted_exceed_'+tag+'_s']=float(np.sum(dt[exceed&~alarms]))
            result['available_unalerted_exceed_'+tag+'_s']=float(np.sum(dt[exceed&~alarms&available])) if method!='M0' else None
            result['unavailable_exceed_'+tag+'_s']=float(np.sum(dt[exceed&~available])) if method!='M0' else None
            result['receipt_axis_delayed_state_unalerted_exceed_'+tag+'_s']=float(np.sum(has&(held_state_error>limit)&~held_alarm)*.05)
            result['receipt_axis_current_unpropagated_unalerted_exceed_'+tag+'_s']=float(np.sum(has&(stale_error>limit)&~held_alarm)*.05)
            result['error_recovery_'+tag+'_state_s']=recover_time(valid&~exceed,state,window[1]) if window else None
            result['error_recovery_'+tag+'_receipt_s']=None
            if result['error_recovery_'+tag+'_state_s'] is not None:
                i=np.where(state==window[1]+result['error_recovery_'+tag+'_state_s'])[0][0]
                result['error_recovery_'+tag+'_receipt_s']=float(available_times[i]-window[1])
            interval_rows.extend(intervals(exceed&~alarms,state,ends,dict(id=record['id'],method=method,kind='unalerted_exceedance',error_limit_m=limit,time_axis='state')))
        if method!='M0':
            interval_rows.extend(intervals(~available,state,ends,dict(id=record['id'],method=method,kind='monitor_unavailable',error_limit_m=None,time_axis='state')))
            interval_rows.extend(intervals(alarms,state,ends,dict(id=record['id'],method=method,kind='alarm',error_limit_m=None,time_axis='state')))
        for i,r in enumerate(rows):
            timeseries.append(dict(id=record['id'],group=record['group'],scenario=scenario['id'],seed=record['seed'],method=method,
                state_time_s=float(state[i]),state_interval_end_s=float(ends[i]),availability_cutoff_s=r['availability_cutoff_s'],
                trigger_receipt_s=r['trigger_receipt_s'],result_available_receipt_s=float(available_times[i]),
                actual_output_utc=r['actual_output_utc'],unpaced_actual_output_elapsed_s=r['unpaced_actual_output_elapsed_s'],
                truth_antenna_x_m=float(true[i,0]),truth_antenna_y_m=float(true[i,1]),
                published_antenna_x_m=float(poses[i,0]) if valid[i] else None,published_antenna_y_m=float(poses[i,1]) if valid[i] else None,
                published_yaw_rad=r['pose'][2] if valid[i] else None,error_m=float(error[i]) if valid[i] else None,
                statistic=stats[i],threshold=thresholds.get(method),alarm=bool(alarms[i]),monitor_available=bool(available[i]) if method!='M0' else None,
                conclusion='not_installed' if method=='M0' else ('unavailable' if not available[i] else ('alarm' if alarms[i] else 'no_threshold_alarm')),
                unavailable_reasons=';'.join(r[method]['reasons']) if method!='M0' else None,
                locator_status=r['status'],accepted_graph=r['accepted_graph'],fault_active=bool(active[i]),
                current_anchor_count=len(r.get('range_medians_m',{})),extra_compute_wall_s=float(costs[i]),
                modeled_event_queue_s=r['modeled_event_queue_s'],latency_note='measured CPU on modeled receipt worker; actual UTC is unpaced offline output'))
        summaries.append(result)
    for r in rows:
        prefit={x['anchor']:x for x in r['prefit_current_residuals']}
        for item in r['postfit_current_residuals']:
            ranges.append(dict(id=record['id'],state_time_s=r['state_time_s'],M1_available_receipt_s=r['M1_available_receipt_s'],
                               **item,prefit_raw_innovation_m=prefit[item['anchor']]['raw_residual_m'],
                               prefit_normalized_innovation=prefit[item['anchor']]['normalized_raw_residual']))
    csv_write(output/'timeseries.csv',timeseries);csv_write(output/'range_residuals.csv',ranges);csv_write(output/'intervals.csv',interval_rows)
    write(output/'metrics.json',summaries)
    return summaries,timeseries,interval_rows


def correlation(values,lag):
    a=np.array(values,dtype=float)
    if len(a)<=lag+2 or np.std(a[:-lag])<1e-12 or np.std(a[lag:])<1e-12:return None
    return float(np.corrcoef(a[:-lag],a[lag:])[0,1])


def historical_audit(out,results,p):
    audits=[];static=[];calibration={};historical_rows=[]
    thresholds=json.loads((out/'thresholds.json').read_text())['values']
    # Recompute original P1 raw medians independently from archived ROS messages.
    calibration_path=ROOT/'datasets/field_raw/20261017/bags/CAR2_P1_REINSTALL_STATIC_20261017_045257.bag'
    spec=importlib.util.spec_from_file_location('archived_static_reader',ROOT/'docs/field_tests/20261018/single_car_transfer_20261021/analyze_static_transfer.py')
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    data=reader.load_bag(calibration_path)
    for key,xyz in p['model']['anchors_xyz_m'].items():
        values=[v[key] for _,v,tag in data['ranges'] if tag=='node_0' and key in v]
        geometric=float(np.linalg.norm(np.array([2,2,.2])-xyz));recomputed=float(np.median(values)-geometric)
        calibration[key]=dict(raw_median_m=float(np.median(values)),geometry_m=geometric,recomputed_bias_m=recomputed,
                              frozen_bias_m=p['model']['range_bias_m'][key],delta_m=recomputed-p['model']['range_bias_m'][key])
        if abs(calibration[key]['delta_m'])>1e-12:raise AssertionError('P1 correction mismatch')
    for case in p['historical_cases']:
        run=out/'runs'/('history_'+case['id'])
        status=json.loads((run/'run.json').read_text())
        if status['status']!='completed':
            audits.append(dict(case=case['id'],status=status['status']));continue
        current=read_rows(run/'output/updates.jsonl')
        archive=ROOT/'docs/field_tests/single_car_fixed_lag_20261022/results'/case['id']/'analytic_warm_fixed_20s/updates.json'
        old=json.loads(archive.read_text())
        if len(old)!=len(current):raise AssertionError('Historical count mismatch')
        keys=['state_time_s','availability_cutoff_s','range_medians_m','range_sample_counts','local_odom','status','accepted_graph']
        same=all(all(a.get(k)==b.get(k) for k in keys) for a,b in zip(current,old))
        delta=max(float(np.linalg.norm(np.array(a['antenna_xy_m'])-b['antenna_xy_m'])) for a,b in zip(current,old))
        if not same or delta>1e-6:raise AssertionError('Historical reproduction mismatch')
        events=list(bag_events(ROOT/case['bag']))
        windows=[('initial_conditional_stationary',[3.,8.]),('existing_endpoint_stop',case['evaluation_window_s'])]
        for name,window in windows:
            odom=[e.value for e in events if e.kind=='odom' and window[0]<=e.header_s<window[1]]
            odom=np.array(odom)
            path=float(np.linalg.norm(np.diff(odom[:,:2],axis=0),axis=1).sum()) if len(odom)>1 else None
            for key in p['model']['anchors_xyz_m']:
                samples=[(e.header_s,e.value[key]) for e in events if e.kind=='uwb' and window[0]<=e.header_s<window[1] and key in e.value]
                values=np.array([v for _,v in samples]);stamps=np.array([t for t,_ in samples]);median=float(np.median(values))
                static.append(dict(case=case['id'],window=name,start_s=window[0],end_s=window[1],anchor=key,n=len(values),
                    odom_path_m=path,median_sample_dt_s=float(np.median(np.diff(stamps))),
                    raw_median_m=median,corrected_median_m=median-p['model']['range_bias_m'][key],
                    std_m=float(np.std(values)),MAD_m=float(np.median(np.abs(values-median))),p05_m=float(np.percentile(values,5)),p95_m=float(np.percentile(values,95)),
                    lag1_correlation=correlation(values,1),lag20_correlation=correlation(values,20),interpretation='stability only; position/orientation survey not certified; no absolute ranging bias claim'))
        times=[r['state_time_s'] for r in current]
        value=endpoint(times,[r['antenna_xy_m'] for r in current],case['evaluation_window_s'],case['end_antenna_xyz_m'],[r['accepted_graph'] for r in current])
        checks=dict(case=case['id'],status='completed',input_hash_matches=sha(ROOT/case['bag'])==case['sha256'],
                    archived_updates_sha256=sha(archive),same_frontend_and_status=same,max_published_position_delta_m=delta,
                    endpoint=value,counters=json.loads((run/'output/worker_summary.json').read_text())['counters'],
                    continuous_trajectory_truth=False,full_trajectory_RMSE=None,error_exceedance_missed_alarm_rate=None)
        triggers={m:Trigger(thresholds[m],2) for m in ['M1','M2']}
        monitor_counts={m:dict(alarm_states=0,unavailable_states=0) for m in triggers}
        for r in current:
            for method in triggers:
                alarm=triggers[method].update(r[method]['statistic'],r[method]['available'])
                monitor_counts[method]['alarm_states']+=alarm is True
                monitor_counts[method]['unavailable_states']+=not r[method]['available']
                historical_rows.append(dict(case=case['id'],method=method,state_time_s=r['state_time_s'],
                    result_available_receipt_s=r[method+'_available_receipt_s'],
                    base_x_m=r['pose'][0],base_y_m=r['pose'][1],yaw_rad=r['pose'][2],
                    antenna_x_m=r['antenna_xy_m'][0],antenna_y_m=r['antenna_xy_m'][1],
                    status=r['status'],statistic=r[method]['statistic'],threshold=thresholds[method],
                    available=r[method]['available'],alarm=alarm,conclusion='unavailable' if not r[method]['available'] else ('alarm' if alarm else 'no_threshold_alarm'),
                    reasons=';'.join(r[method]['reasons']),
                    raw_range_medians_json=json.dumps(r['range_medians_m'],sort_keys=True),
                    sample_counts_json=json.dumps(r['range_sample_counts'],sort_keys=True),
                    alarm_evaluation='retrospective threshold application; raw statistics computed during replay; no truth-based detection accuracy'))
        checks['retrospective_monitor_counts']=monitor_counts
        audits.append(checks)
    csv_write(results/'historical_monitor_timeseries.csv',historical_rows)
    csv_write(results/'static_link_stability.csv',static)
    write(results/'historical_audit.json',dict(cases=audits,P1_calibration=calibration,P1_raw_bag_sha256=sha(calibration_path),
        anchor_source='docs/field_tests/20261017/session_config.json; original P1 field note says previous manual survey, pending recheck',
        correction_sign='raw - P1 bias; ingestion validity check does not mutate raw; medians remain raw; Objective subtracts once',
        calibration_scope='Oct17 reinstallation and unchanged Oct18 mounting only; no transfer to Oct11 or future installations guaranteed',
        lever_assumption='[.12,-.08] m manual geometric center; Odom reference correspondence pending',
        timestamp_policy='receipt order; header measurement association; +-0.4s raw median, >=5 samples, closes t+1s; no clock fit',
        continuity_truth_absent=True))
    return audits,static
