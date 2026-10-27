"""Complete historical output/action/timing diagnostics; no trajectory truth."""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import statistics
import numpy as np
from .common import ROOT,begin,finish,lines,require,sha,write


def stats(values):
    v=np.asarray(values,float)
    if not len(v):return dict(n=0,minimum=None,median=None,mean=None,p95=None,maximum=None)
    return dict(n=len(v),minimum=float(v.min()),median=float(np.median(v)),mean=float(v.mean()),p95=float(np.percentile(v,95)),maximum=float(v.max()))


def stop_window(rows,case):
    a,b=case['evaluation_window_s'];selected=[r for r in rows if a<=r['state_time_s']<=b and r['pose'] is not None];xy=np.array([r['antenna_xy_m'] for r in selected]);valid=sum(bool(r['estimate_valid']) for r in selected)
    if not len(xy):return dict(outputs=0,valid_outputs=0,median_xy_m=None,manual_endpoint_distance_m=None)
    middle=np.median(xy,axis=0);radial=np.linalg.norm(xy-middle,axis=1);elapsed=selected[-1]['state_time_s']-selected[0]['state_time_s']
    return dict(frozen_window_s=[a,b],outputs=len(selected),valid_outputs=valid,median_xy_m=middle.tolist(),manual_endpoint_xy_m=case['end_antenna_xyz_m'][:2],manual_endpoint_distance_m=float(np.linalg.norm(middle-case['end_antenna_xyz_m'][:2])),manual_uncertainty_m=None,
      scatter_about_component_median_m=dict(median=float(np.median(radial)),rms=float(np.sqrt(np.mean(radial**2))),maximum=float(radial.max())),
      candidate_static_net_displacement_m=float(np.linalg.norm(xy[-1]-xy[0])),candidate_static_max_displacement_from_first_m=float(np.linalg.norm(xy-xy[0],axis=1).max()),candidate_static_elapsed_s=elapsed,
      static_confirmation='frozen historical stop window only; no independent exact standstill/parking-time bound',reference='uncertain operator endpoint, development diagnostic only; not continuous RMSE/ATE')


def differences(rows,reference,selected=None):
    by={r['state_epoch_ns']:r for r in reference};use=[r for r in rows if selected is None or r['state_epoch_ns'] in selected];xy=[];yaw=[];bias=[]
    for r in use:
        q=by[r['state_epoch_ns']];xy.append(math.dist(r['pose'][:2],q['pose'][:2]));yaw.append(abs(math.degrees(math.atan2(math.sin(r['pose'][2]-q['pose'][2]),math.cos(r['pose'][2]-q['pose'][2])))))
        if r.get('bias_rad_s') is not None and q.get('bias_rad_s') is not None:bias.append(abs(r['bias_rad_s']-q['bias_rad_s']))
    return dict(publications=len(use),base_shift_m=stats(xy),absolute_wrapped_yaw_change_deg=stats(yaw),absolute_bias_change_rad_s=stats(bias) if bias else None,interpretation='output difference, not error against truth or accuracy improvement')


def actions(ledger,availability,case,group):
    by=sorted(availability,key=lambda r:r['state_epoch_ns']);when={r['state_epoch_ns']:r['available_receive_epoch_ns'] for r in by};epochs=[r['state_epoch_ns'] for r in by];duration={t:(when[epochs[i+1]]-when[t])/1e9 if i+1<len(epochs) else 0. for i,t in enumerate(epochs)};links=sorted({r['target'] for r in ledger});perlink={};triggers=[];recovery=[];intervals=[];flat=[]
    for link in links:
        rows=[r for r in ledger if r['target']==link];counts=Counter();seconds=Counter();previous_gain=1.;previous_mode='normal';segment=None;known_down_intervals=0;last_known_down=False
        for i,r in enumerate(rows):
            policy=r['policy'];state=policy['state'];gain=policy['information_multiplier'];known=policy['monitorable'] is True;dt=duration[r['state_epoch_ns']];counts[state]+=1;seconds[state]+=dt
            if known:seconds['known_total']+=dt;counts['known_total']+=1
            elif state=='unknown':seconds['unknown_total']+=dt;counts['unknown_total']+=1
            else:seconds['unmonitored_total']+=dt
            if known and gain<1:seconds['known_attenuation']+=dt;counts['known_attenuation']+=1
            if known and gain==0:seconds['known_disabled']+=dt;counts['known_disabled']+=1
            if state=='unknown' and gain<1:seconds['unknown_hold_attenuation']+=dt
            if state=='unknown' and gain==0:seconds['unknown_hold_disabled']+=dt
            down=known and gain<1
            if down and not last_known_down:known_down_intervals+=1
            last_known_down=down
            if known and gain<previous_gain:
                triggers.append(dict(case_id=case,group=group,link=link,state_epoch_ns=r['state_epoch_ns'],available_receive_epoch_ns=when[r['state_epoch_ns']],score=r['engineering_score'],previous_information_gain=previous_gain,new_information_gain=gain,reason=policy['reason'],interpretation='trigger event; no complete independent fault labels'))
            mode=policy.get('policy_mode_held')
            if known and mode in ('recovering','normal') and mode!=previous_mode and (mode=='recovering' or previous_mode=='recovering'):
                event=dict(case_id=case,group=group,link=link,state_epoch_ns=r['state_epoch_ns'],available_receive_epoch_ns=when[r['state_epoch_ns']],event='recovery_trial_start' if mode=='recovering' else 'policy_normal_onset',reason=policy['reason'],third_known_normal_confirmation_epoch_ns=None)
                if mode=='normal' and i+2<len(rows) and all(x['policy']['monitorable'] is True and x['policy']['state']=='normal' and x['policy']['information_multiplier']==1 for x in rows[i:i+3]):event['third_known_normal_confirmation_epoch_ns']=when[rows[i+2]['state_epoch_ns']]
                recovery.append(event)
            signature=(state,mode,gain,r['actual_information_multiplier'] is None)
            if segment is None or segment['signature']!=signature:
                if segment:intervals.append(segment)
                segment=dict(case_id=case,group=group,link=link,signature=signature,start_state_epoch_ns=r['state_epoch_ns'],start_available_epoch_ns=when[r['state_epoch_ns']],last_state_epoch_ns=r['state_epoch_ns'],duration_s=0.,publications=0)
            segment['last_state_epoch_ns']=r['state_epoch_ns'];segment['duration_s']+=dt;segment['publications']+=1
            flat.append(dict(case_id=case,group=group,link=link,state_epoch_ns=r['state_epoch_ns'],available_epoch_ns=when[r['state_epoch_ns']],state=state,held_mode=mode,known=known,score=r['engineering_score'],policy_information_gain=gain,actual_information_gain=r['actual_information_multiplier'],factor_action=r['factor_action'],reason=policy['reason'],exposure_to_next_publication_s=dt))
            previous_gain=gain;previous_mode=mode
        if segment:intervals.append(segment)
        perlink[link]=dict(publications=len(rows),state_counts=dict(counts),exposure_link_seconds=dict(seconds),known_attenuation_intervals=known_down_intervals,trigger_events=sum(t['link']==link for t in triggers),observed_exposure_s=sum(duration[t] for t in epochs))
    any_reduced=0.;unknown_any=0.
    for t in epochs:
        rs=[r for r in ledger if r['state_epoch_ns']==t]
        if any(r['policy']['information_multiplier']<1 for r in rs):any_reduced+=duration[t]
        if any(r['policy']['state']=='unknown' for r in rs):unknown_any+=duration[t]
    return dict(per_link=perlink,trigger_events=len(triggers),vehicle_any_link_attenuation_s=any_reduced,vehicle_any_unknown_s=unknown_any,link_seconds_are_not_vehicle_seconds=True,normal_completion_is_not_fault_free_label=True),triggers,recovery,intervals,flat


def table_csv(path,rows):
    if not rows:write(path.with_suffix('.json'),[]);return
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--performance',type=Path,required=True);p.add_argument('--readback',type=Path,required=True);p.add_argument('--controls',type=Path,required=True);p.add_argument('--negative',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_all_publication_native_quality_field_diagnostics')
    try:
        for folder in (a.readback,a.controls,a.negative):require(json.loads((folder/'verification.json').read_text())['status']=='PASS','completed independent checks required')
        legacy=ROOT/'docs/field_tests/single_car_fixed_lag_20261022/protocol.json';cases={c['id']:c for c in json.loads(legacy.read_text())['cases']};summaries=[];diagnostics=[];link_rows=[];trigger_rows=[];recover_rows=[];action_intervals=[];comparison_rows=[];all_data={}
        for case in ('004023','005135'):
            rows_by={group:[p['row'] for p in lines(a.performance/(case+'_'+group)/'publications.jsonl.gz')] for group in ('Q0','Q1','Q2','Q3')};grid={r['state_epoch_ns'] for r in rows_by['Q0']};common=set(grid)
            for rows in rows_by.values():require({r['state_epoch_ns'] for r in rows}==grid,'missing/unmatched complete output grid');common&={r['state_epoch_ns'] for r in rows if r['estimate_valid']}
            modes={}
            for group,rows in rows_by.items():
                folder=a.performance/(case+'_'+group);pub=lines(folder/'publications.jsonl.gz');avail=lines(folder/'availability.jsonl.gz');ledger=lines(folder/'quality_ledger.jsonl.gz');graphs=lines(folder/'graphs.jsonl.gz');meta=json.loads((folder/'run.json').read_text());available={r['publication_id']:r for r in avail};origin=meta['origin_receive_epoch_ns'];inputrows=lines(folder/'input_decisions.jsonl.gz');eof=inputrows[-1]['input']['receive_epoch_ns'];cycles=[];pre=[];main=[];post=[]
                for out in pub:
                    x=available[out['publication_id']];end=x['data_flushed_host_monotonic_ns'];start=out['processing_cycle_start_monotonic_ns'];cycles.append((end-start)/1e9);pre.append((out['main_solve_start_monotonic_ns']-start)/1e9);main.append((out['main_solve_finish_monotonic_ns']-out['main_solve_start_monotonic_ns'])/1e9);post.append((end-out['main_solve_finish_monotonic_ns'])/1e9)
                    r=out['row'];diagnostics.append(dict(case_id=case,group=group,state_epoch_ns=out['state_epoch_ns'],cutoff_epoch_ns=out['availability_cutoff_epoch_ns'],actual_available_receive_epoch_ns=x['available_receive_epoch_ns'],state_time_s=r['state_time_s'],estimate_valid=r['estimate_valid'],common_valid=r['state_epoch_ns'] in common,status=r['status'],base_x_m=r['pose'][0],base_y_m=r['pose'][1],yaw_rad=r['pose'][2],bias_rad_s=r['bias_rad_s'],antenna_x_m=r['antenna_xy_m'][0],antenna_y_m=r['antenna_xy_m'][1],actual_release_delay_s=x['actual_release_delay_s'],complete_publication_cycle_wall_s=cycles[-1],pre_main_shadows_quality_and_logging_s=pre[-1],main_phase_s=main[-1],post_main_diagnostic_and_flush_s=post[-1]))
                q,tr,rec,intervals,flat=actions(ledger,avail,case,group);trigger_rows+=tr;recover_rows+=rec;action_intervals+=intervals;link_rows+=flat;bias=[r['bias_rad_s'] for r in rows if r['bias_rad_s'] is not None];first=next(i for i,r in enumerate(rows) if r['accepted_graph']);ref='Q0' if group in ('Q0','Q2') else 'Q1';stop=stop_window(rows,cases[case]);role_costs={}
                for role in sorted({g['role'] for g in graphs}):
                    use=[g['row'] for g in graphs if g['role']==role];role_costs[role]=dict(solve_wall_s=sum(g['solve_wall_s'] for g in use),marginal_wall_s=sum(g['marginal_wall_s'] for g in use),max_keyframes=max(g['graph_states'] for g in use),scalar_dimension=4 if group in ('Q1','Q3') else 3)
                summary=dict(published=len(rows),finite_pose_outputs=sum(bool(np.isfinite(r['pose']).all()) for r in rows),estimate_valid_outputs=sum(bool(r['estimate_valid']) for r in rows),accepted_graph_outputs=sum(bool(r['accepted_graph']) for r in rows),common_valid_outputs=len(common),warmup_outputs=sum('warmup' in r['status'] for r in rows),solver_failures=sum('solver_failed' in r['status'] or 'solver_error' in r['status'] for r in rows),fallback_outputs=sum(bool(r.get('odom_yaw_fallback')) for r in rows),status_counts=dict(Counter(r['status'] for r in rows)),
                    first_accepted=dict(state_time_s=rows[first]['state_time_s'],position_correction_m=rows[first]['position_correction_m'],yaw_correction_deg=rows[first]['yaw_correction_deg'],step_from_previous_publication_m=math.dist(rows[first]['pose'][:2],rows[first-1]['pose'][:2]) if first else None),
                    max_adjacent_publication_jump_m=max(math.dist(x['pose'][:2],y['pose'][:2]) for x,y in zip(rows,rows[1:])),bias_rad_s=dict(stats(bias),last=bias[-1]) if bias else None,
                    quality=q,stop_window=stop,paired_baseline_group=ref,all_output_change_vs_paired_baseline=differences(rows,rows_by[ref]),common_valid_change_vs_paired_baseline=differences(rows,rows_by[ref],common),all_output_change_vs_Q0=differences(rows,rows_by['Q0']),
                    timing=dict(actual_release_delay_s=stats([x['actual_release_delay_s'] for x in avail]),post_cutoff_total_s=stats([x['post_cutoff_total_delay_s'] for x in avail]),complete_publication_cycle_wall_s=stats(cycles),complete_publication_cycle_wall_s_sum=sum(cycles),pre_main_shadows_quality_and_graph_logging_s=stats(pre),main_phase_s=stats(main),post_main_diagnostic_and_flush_s=stats(post),role_solver_costs=role_costs,
                        CLI_elapsed_including_pacing_and_IO_s=meta['elapsed_s'],original_incomplete_processor_column_s=stats([x['complete_processor_wall_s'] for x in avail]),beyond_next_cutoff_count=sum(x['available_receive_epoch_ns']>x['availability_cutoff_epoch_ns']+10**9 for x in avail),output_after_recorded_EOF_count=sum(x['available_receive_epoch_ns']>eof for x in avail),
                        caveat='cycle wall includes shadow/quality/main/diagnostics/write, excludes earlier inter-publication ingest; original incomplete column retained separately and is not additive. Actual end-to-end delay includes original1s wait and scheduling; not physical ROS latency or pure CPU time.'),
                    reference_coverage=dict(continuous_state_truth=0,continuous_available_time_truth=0,frozen_stop_reference_samples=stop['outputs'],all_publications=len(rows),manual_uncertainty_m=None,actual_available_reference_error=None),field_accuracy_assessment='尚不能判断')
                modes[group]=summary;all_data[case,group]=dict(rows=rows,avail=avail,ledger=ledger)
                comparison_rows.append(dict(case_id=case,group=group,published=len(rows),valid=summary['estimate_valid_outputs'],common_valid=len(common),antenna_median_x_m=stop['median_xy_m'][0],antenna_median_y_m=stop['median_xy_m'][1],manual_stop_distance_m=stop['manual_endpoint_distance_m'],stop_scatter_rms_m=stop['scatter_about_component_median_m']['rms'],candidate_static_net_drift_m=stop['candidate_static_net_displacement_m'],trigger_events=q['trigger_events'],vehicle_any_link_attenuation_s=q['vehicle_any_link_attenuation_s'],actual_release_mean_s=summary['timing']['actual_release_delay_s']['mean'],actual_release_p95_s=summary['timing']['actual_release_delay_s']['p95'],actual_release_max_s=summary['timing']['actual_release_delay_s']['maximum'],solver_failures=summary['solver_failures']))
            summaries.append(dict(case_id=case,common_valid_state_epoch_ns=sorted(common),modes=modes))
        table_csv(a.output/'four_groups.csv',comparison_rows);table_csv(a.output/'publication_diagnostics.csv',diagnostics);table_csv(a.output/'link_diagnostics.csv',link_rows);table_csv(a.output/'trigger_events.csv',trigger_rows);table_csv(a.output/'recovery_events.csv',recover_rows);table_csv(a.output/'action_intervals.csv',action_intervals)
        write(a.output/'summary.json',dict(status='DONE',cases=summaries,main_performance_runs=8,all_publications=len(diagnostics),known_fault_labels=None,continuous_trajectory_truth=None,thresholds_tuned_on_field=False,interpretation='actions are trigger events; stop-distance changes are uncertain development observations, not overall field precision improvement',field_accuracy_assessment='尚不能判断'))
        md=['# 两历史包完整四组开发诊断','', '人工末点不确定度未知，历史几何/轴/时间仍有条件假设。全部发布和共同有效都保留；距离差不是全程RMSE/ATE，触发不是误报/漏报。静止漂移仅指原冻结停车窗内自身位移。','', '| 包 | 组 | 发布/有效/共同 | 天线XY中位数m | 人工末点差m | 窗散布RMS m | 候选静止净漂移m | 触发事件 | 实际延迟均值/p95/最大s |','|---|---|---:|---|---:|---:|---:|---:|---|']
        for x in comparison_rows:md.append(f"| {x['case_id']} | {x['group']} | {x['published']}/{x['valid']}/{x['common_valid']} | ({x['antenna_median_x_m']:.6f},{x['antenna_median_y_m']:.6f}) | {x['manual_stop_distance_m']:.6f} | {x['stop_scatter_rms_m']:.6f} | {x['candidate_static_net_drift_m']:.6f} | {x['trigger_events']} | {x['actual_release_mean_s']:.4f}/{x['actual_release_p95_s']:.4f}/{x['actual_release_max_s']:.4f} |")
        (a.output/'TABLE.md').write_text('\n'.join(md)+'\n');v['inputs']=[dict(path=str(p/'verification.json'),sha256=sha(p/'verification.json')) for p in (a.readback,a.controls,a.negative)];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
