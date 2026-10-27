"""Offline-only truth/labels evaluation, actual availability and event denominators."""
import bisect
import csv
import json
import math
from pathlib import Path
import numpy as np
from qio import read_jsonl


def csv_write(path,rows):
    if not rows:return
    with Path(path).open('x',newline='') as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})


def lookup(truth,epochs,t):
    if t<epochs[0] or t>epochs[-1]:return None
    i=bisect.bisect_right(epochs,t)-1
    if t==epochs[i]:return truth[i]
    a,b=truth[i],truth[i+1];fraction=(t-epochs[i])/(epochs[i+1]-epochs[i]);return dict(pose=(np.array(a['pose'])+fraction*(np.array(b['pose'])-a['pose'])).tolist(),bias_rad_s=a['bias_rad_s']+fraction*(b['bias_rad_s']-a['bias_rad_s']))


def rmse(rows,key,condition=lambda r:True):
    values=[r[key] for r in rows if r[key] is not None and condition(r)]
    return float(np.sqrt(np.mean(np.square(values)))) if values else None


def episode_summary(rows,available,nominal_only=False):
    # Episodes are contiguous policy-gain conditions, never one event per frame.
    episodes=[];stopped=[];current=None;stop=None;duration=unknown=monitorable=attenuated=disabled=unknown_attenuated=0.
    for i,r in enumerate(rows):
        t=available[r['publication_id']]['available_receive_epoch_ns'];end=available[rows[i+1]['publication_id']]['available_receive_epoch_ns'] if i+1<len(rows) else t;dt=max(0,end-t)/1e9
        duration+=dt;known=r['policy']['monitorable'] is True;monitorable+=dt*known;unknown+=dt*(not known)
        g=r['policy']['information_multiplier'];attenuated+=dt*(g<1);disabled+=dt*(g==0);unknown_attenuated+=dt*(not known and g<1)
        if g<1 and current is None:current=dict(onset_state_epoch_ns=r['state_epoch_ns'],onset_available_epoch_ns=t,start_policy_state=r['policy']['state'])
        if g>=1 and current is not None:current['end_available_epoch_ns']=t;current['right_censored']=False;episodes.append(current);current=None
        if g==0 and stop is None:stop=dict(onset_state_epoch_ns=r['state_epoch_ns'],onset_available_epoch_ns=t)
        if g!=0 and stop is not None:stop['end_available_epoch_ns']=t;stop['right_censored']=False;stopped.append(stop);stop=None
    if current is not None:current.update(end_available_epoch_ns=None,right_censored=True);episodes.append(current)
    if stop is not None:stop.update(end_available_epoch_ns=None,right_censored=True);stopped.append(stop)
    return dict(observed_output_duration_s=duration,monitorable_duration_s=monitorable,unknown_duration_s=unknown,attenuated_duration_s=attenuated,disabled_duration_s=disabled,unknown_held_attenuation_duration_s=unknown_attenuated,
                attenuation_episodes=len(episodes),disabled_episodes=len(stopped),episode_details=episodes,disabled_episode_details=stopped)


def event_evaluate(event,rows,available,series):
    start,end=event['start_epoch_ns'],event['end_epoch_ns'];inside=[r for r in rows if start<=r['state_epoch_ns']<end];best=streak=0;previous=None
    for r in inside:
        if r['policy']['monitorable'] is True:streak=streak+1 if previous is not None and r['state_epoch_ns']-previous==10**9 else 1;previous=r['state_epoch_ns']
        else:streak=0;previous=None
        best=max(best,streak)
    monitorable=best>=2;before=[r for r in rows if r['state_epoch_ns']<start];preexisting=bool(before and before[-1]['policy']['information_multiplier']<1)
    alert=None;last_gain=1.
    for r in rows:
        gain=r['policy']['information_multiplier']
        if start<=r['state_epoch_ns']<end and r['policy']['monitorable'] is True and gain<last_gain and gain<1 and alert is None:alert=r
        last_gain=gain
    detected=alert is not None;ready=available[alert['publication_id']]['available_receive_epoch_ns'] if alert else None;recovery=None
    if detected:
        after=[r for r in rows if r['state_epoch_ns']>=end]
        for i,r in enumerate(after[:-2]):
            triple=after[i:i+3]
            if all(a['policy']['state']=='normal' and a['policy']['monitorable'] is True and a['policy']['information_multiplier']==1 for a in triple) and triple[-1]['state_epoch_ns']-triple[0]['state_epoch_ns']==2*10**9:
                recovery=available[r['publication_id']]['available_receive_epoch_ns'];break
    active_series=[r for r in series if start<=r['state_epoch_ns']<end];tail=[r for r in series if end<=r['state_epoch_ns']<end+20*10**9];late=[r for r in series if r['state_epoch_ns']>=end+20*10**9]
    return dict(event_id=event['event_id'],target=event['target'],start_epoch_ns=start,end_epoch_ns=end,monitorable_event=monitorable,max_consecutive_monitorable_decisions=best,
        preexisting_alert_at_onset=preexisting,detected_new_or_escalated_alert=detected,alarm_available_epoch_ns=ready,alarm_delay_s=(ready-start)/1e9 if ready is not None else None,
        alarm_while_fault_active=bool(ready is not None and ready<end),late_historical_detection=bool(ready is not None and ready>=end),recovered_available_epoch_ns=recovery,
        alarm_recovery_delay_s=(recovery-end)/1e9 if recovery is not None else None,recovery_censored_or_not_applicable=recovery is None,
        fault_xy_rmse_m=rmse(active_series,'xy_error_state_m'),fault_yaw_rmse_rad=rmse(active_series,'yaw_error_rad'),fault_bias_rmse_rad_s=rmse(active_series,'bias_error_rad_s'),
        residual_first20s_xy_rmse_m=rmse(tail,'xy_error_state_m'),residual_after20s_xy_rmse_m=rmse(late,'xy_error_state_m'),
        xy_over_020m_state_s=sum(r['xy_error_state_m'] is not None and r['xy_error_state_m']>.20 for r in active_series),yaw_over_020rad_state_s=sum(r['yaw_error_rad'] is not None and abs(r['yaw_error_rad'])>.20 for r in active_series))


def evaluate_case(root,scenario,seed):
    root=Path(root);inp=root/'inputs'/f'{scenario}_seed{seed}';truth=list(read_jsonl(inp/'truth.jsonl.gz'));epochs=[r['epoch_ns'] for r in truth];labels=json.loads((inp/'labels.json').read_text());origin=labels['origin_epoch_ns'];runs={};common=None
    for group in ['Q0','Q1','Q2','Q3']:
        path=root/'runs'/f'{scenario}_seed{seed}__{group}'
        if not(path/'run.json').exists() or json.loads((path/'run.json').read_text())['status']!='DONE':continue
        pubs=list(read_jsonl(path/'publications.jsonl.gz'));availability={r['publication_id']:r for r in read_jsonl(path/'availability.jsonl.gz')};ledger=list(read_jsonl(path/'quality_ledger.jsonl.gz'));runs[group]=(path,pubs,availability,ledger)
        valid={r['state_epoch_ns'] for r in pubs if r['row'].get('estimate_valid',r['row']['accepted_graph'])};common=valid if common is None else common&valid
    if len(runs)!=4:common=set()
    metrics=[];link_metrics=[];events=[];series_by_group={};diagnostics=[]
    for group,(path,pubs,available,ledger) in runs.items():
        series=[];attempts=failed=0
        for pub in pubs:
            row=pub['row'];stamp=pub['state_epoch_ns'];a=available[pub['publication_id']];ready=a['available_receive_epoch_ns'];actual=lookup(truth,epochs,stamp);now=lookup(truth,epochs,ready);pose=row['pose'];bias=row.get('bias_rad_s');xy=math.hypot(pose[0]-actual['pose'][0],pose[1]-actual['pose'][1]) if pose is not None and actual else None
            yaw=math.atan2(math.sin(pose[2]-actual['pose'][2]),math.cos(pose[2]-actual['pose'][2])) if pose is not None and actual else None
            current=math.hypot(pose[0]-now['pose'][0],pose[1]-now['pose'][1]) if pose is not None and now else None
            series.append(dict(scenario=scenario,seed=seed,group=group,publication_id=pub['publication_id'],state_epoch_ns=stamp,availability_cutoff_epoch_ns=pub['availability_cutoff_epoch_ns'],available_receive_epoch_ns=ready,t_s=(stamp-origin)/1e9,
                base_x_m=pose[0] if pose else None,base_y_m=pose[1] if pose else None,yaw_rad=pose[2] if pose else None,true_x_m=actual['pose'][0] if actual else None,true_y_m=actual['pose'][1] if actual else None,
                xy_error_state_m=xy,yaw_error_rad=yaw,xy_error_at_actual_available_m=current,bias_rad_s=bias,true_effective_gyro_bias_rad_s=actual['bias_rad_s'] if actual else None,
                bias_error_rad_s=bias-actual['bias_rad_s'] if bias is not None and actual else None,true_physical_gyro_bias_rad_s=actual.get('physical_gyro_bias_rad_s') if actual else None,accepted_graph=row['accepted_graph'],estimate_valid=row.get('estimate_valid',row['accepted_graph']),common_valid=stamp in common,status=row['status'],complete_processor_wall_s=a['complete_processor_wall_s'],actual_release_delay_s=a['actual_release_delay_s']))
            if row['graph_states']>=3:attempts+=1;failed+=int(not row['accepted_graph'])
        series_by_group[group]=series;enabled=group in ('Q2','Q3');links={k:[r for r in ledger if r['target']==k] for k in sorted({r['target'] for r in ledger})}
        for target,rows in links.items():
            stat=episode_summary(rows,available) if enabled else {k:None for k in ['observed_output_duration_s','monitorable_duration_s','unknown_duration_s','attenuated_duration_s','disabled_duration_s','unknown_held_attenuation_duration_s','attenuation_episodes','disabled_episodes','episode_details','disabled_episode_details']}
            injected=any(e['target']==target for e in labels['uwb_fault_events'])
            link_metrics.append(dict(scenario=scenario,seed=seed,group=group,target=target,normal_UWB_case=scenario=='nominal',injected_UWB_link=injected,healthy_link_attenuation_episodes=stat['attenuation_episodes'] if enabled and not injected else None,healthy_link_disabled_episodes=stat['disabled_episodes'] if enabled and not injected else None,**stat))
        for event in labels['uwb_fault_events']:
            if enabled:events.append(dict(scenario=scenario,seed=seed,group=group,**event_evaluate(event,links[event['target']],available,series)))
        for target,rows in links.items():
            for r in rows:
                a=available[r['publication_id']];diagnostics.append(dict(scenario=scenario,seed=seed,group=group,target=target,state_epoch_ns=r['state_epoch_ns'],available_receive_epoch_ns=a['available_receive_epoch_ns'],t_s=(r['state_epoch_ns']-origin)/1e9,
                    score=r['engineering_score'],state=r['policy']['state'],reason=r['policy']['reason'],monitorable=r['policy']['monitorable'],policy_information_multiplier=r['policy']['information_multiplier'],actual_information_multiplier=r['actual_information_multiplier'],information_admitted=r['information_admitted'],raw_residual_m=r['raw_signed_consistency_residual_m']))
        complete=[s['complete_processor_wall_s'] for s in series];finite=[s['xy_error_state_m'] for s in series if s['xy_error_state_m'] is not None];ownlinks=[r for r in link_metrics if r['group']==group and r['scenario']==scenario and r['seed']==seed]
        metrics.append(dict(scenario=scenario,seed=seed,group=group,run_status='DONE',publications=len(series),finite_pose_publications=len(finite),finite_pose_coverage=len(finite)/len(series),estimate_valid_publications=sum(r['estimate_valid'] for r in series),common_valid_publications=len(common),solve_attempts=attempts,solver_failures=failed,
            all_xy_rmse_state_m=rmse(series,'xy_error_state_m'),all_xy_max_state_m=max(finite) if finite else None,all_yaw_rmse_rad=rmse(series,'yaw_error_rad'),all_bias_rmse_rad_s=rmse(series,'bias_error_rad_s'),all_xy_rmse_actual_available_m=rmse(series,'xy_error_at_actual_available_m'),available_truth_covered_publications=sum(r['xy_error_at_actual_available_m'] is not None for r in series),
            common_xy_rmse_state_m=rmse(series,'xy_error_state_m',lambda r:r['common_valid']),common_yaw_rmse_rad=rmse(series,'yaw_error_rad',lambda r:r['common_valid']),
            xy_over_020m_state_s=sum(r['xy_error_state_m'] is not None and r['xy_error_state_m']>.20 for r in series),yaw_over_020rad_state_s=sum(r['yaw_error_rad'] is not None and abs(r['yaw_error_rad'])>.20 for r in series),
            early_recovery_32_52_xy_rmse_m=rmse(series,'xy_error_state_m',lambda r:32<=(r['state_epoch_ns']-origin)/1e9<52),late_recovery_52_60_xy_rmse_m=rmse(series,'xy_error_state_m',lambda r:52<=(r['state_epoch_ns']-origin)/1e9<60),
            mean_complete_processor_wall_s=float(np.mean(complete)),p95_complete_processor_wall_s=float(np.percentile(complete,95)),max_complete_processor_wall_s=max(complete),mean_actual_release_delay_s=float(np.mean([r['actual_release_delay_s'] for r in series])),max_actual_release_delay_s=max(r['actual_release_delay_s'] for r in series),
            monitorable_link_seconds=sum(r['monitorable_duration_s'] for r in ownlinks) if enabled else None,unknown_link_seconds=sum(r['unknown_duration_s'] for r in ownlinks) if enabled else None,
            attenuation_episodes=sum(r['attenuation_episodes'] for r in ownlinks) if enabled else None,disabled_episodes=sum(r['disabled_episodes'] for r in ownlinks) if enabled else None,
            healthy_UWB_attenuation_episodes=sum(r['attenuation_episodes'] for r in ownlinks) if enabled and not labels['uwb_fault_events'] else None,
            healthy_UWB_disabled_episodes=sum(r['disabled_episodes'] for r in ownlinks) if enabled and not labels['uwb_fault_events'] else None,
            healthy_other_link_attenuation_episodes=sum(r['healthy_link_attenuation_episodes'] for r in ownlinks if r['healthy_link_attenuation_episodes'] is not None) if enabled else None,healthy_other_link_disabled_episodes=sum(r['healthy_link_disabled_episodes'] for r in ownlinks if r['healthy_link_disabled_episodes'] is not None) if enabled else None,
            timing_mode=pubs[0]['timing_mode'],events_sha256=json.loads((path/'run.json').read_text()).get('input_sha256')))
    # Detection and actual error limitation are two different outcomes, paired by input.
    index={r['group']:r for r in metrics}
    for e in events:
        baseline='Q0' if e['group']=='Q2' else 'Q1';controlled=index[e['group']];b=index.get(baseline)
        e['baseline_group']=baseline;e['delta_all_xy_rmse_m']=controlled['all_xy_rmse_state_m']-b['all_xy_rmse_state_m'] if b else None;e['delta_all_yaw_rmse_rad']=controlled['all_yaw_rmse_rad']-b['all_yaw_rmse_rad'] if b else None
        e['delta_all_bias_rmse_rad_s']=controlled['all_bias_rmse_rad_s']-b['all_bias_rmse_rad_s'] if b and controlled['all_bias_rmse_rad_s'] is not None and b['all_bias_rmse_rad_s'] is not None else None
        e['alert_but_XY_worse']=bool(e['detected_new_or_escalated_alert'] and e['delta_all_xy_rmse_m'] is not None and e['delta_all_xy_rmse_m']>0)
    return metrics,link_metrics,events,series_by_group,diagnostics
