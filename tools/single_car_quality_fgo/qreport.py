#!/usr/bin/env python3
"""Predefined tables/plots for every case/seed, including negative outcomes."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from qio import dump,read_jsonl,sha
from qevaluate import csv_write

GROUPS=['Q0','Q1','Q2','Q3'];COLORS=['#777777','#0072b2','#d55e00','#009e73']


def read_csv(path):
    if not Path(path).exists():return []
    with Path(path).open() as stream:return list(csv.DictReader(stream))


def number(v):return float(v) if v not in ('',None) else None


def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.experiment;out=a.output;out.mkdir(parents=True,exist_ok=False)
    state=json.loads((root/'checkpoint.json').read_text());protocol=json.loads((root/'protocol.json').read_text());plan=protocol[state['stage']];timeword='actual paced' if plan['paced'] else 'virtual development';rows=read_csv(root/'metrics.csv');links=read_csv(root/'quality_link_metrics.csv');events=read_csv(root/'fault_events.csv');by=defaultdict(list)
    for r in rows:by[r['scenario'],r['group']].append(r)
    columns=['all_xy_rmse_state_m','all_yaw_rmse_rad','all_bias_rmse_rad_s','all_xy_rmse_actual_available_m','common_xy_rmse_state_m','mean_complete_processor_wall_s','mean_actual_release_delay_s','max_actual_release_delay_s','unknown_link_seconds','healthy_other_link_attenuation_episodes']
    aggregate=[]
    for (scene,group),values in by.items():
        r=dict(scenario=scene,group=group,seeds=len(values))
        for k in columns:
            v=[number(x.get(k)) for x in values if number(x.get(k)) is not None];r[k+'_mean']=float(np.mean(v)) if v else None
        aggregate.append(r)
    csv_write(out/'aggregate.csv',aggregate);index={(r['scenario'],r['seed'],r['group']):r for r in rows};pairs=[]
    for r in rows:
        if r['group'] not in ('Q2','Q3'):continue
        baseline='Q0' if r['group']=='Q2' else 'Q1';b=index.get((r['scenario'],r['seed'],baseline))
        if not b:continue
        entry=dict(scenario=r['scenario'],seed=r['seed'],group=r['group'],baseline=baseline)
        for k in ['all_xy_rmse_state_m','all_yaw_rmse_rad','all_bias_rmse_rad_s','all_xy_max_state_m','mean_complete_processor_wall_s','mean_actual_release_delay_s','early_recovery_32_52_xy_rmse_m','late_recovery_52_60_xy_rmse_m']:
            entry['delta_'+k]=float(r[k])-float(b[k]) if r.get(k) not in ('',None) and b.get(k) not in ('',None) else None
        pairs.append(entry)
    csv_write(out/'paired_differences.csv',pairs)
    normal=[];detection=[]
    for group in ['Q2','Q3']:
        for seed in plan['seeds']:
            ls=[r for r in links if r['group']==group and int(r['seed'])==seed and r['scenario']=='nominal']
            directory=root/'runs'/f'nominal_seed{seed}__{group}';entries=list(read_jsonl(directory/'quality_ledger.jsonl.gz'));times=list(read_jsonl(directory/'availability.jsonl.gz'));by_pub=defaultdict(list)
            for entry in entries:by_pub[entry['publication_id']].append(entry)
            vehicle_observed=vehicle_monitorable=vehicle_attenuated=0.;vehicle_events=0;was=False
            for i,available in enumerate(times):
                end=times[i+1]['available_receive_epoch_ns'] if i+1<len(times) else available['available_receive_epoch_ns'];dt=max(0,end-available['available_receive_epoch_ns'])/1e9;decisions=by_pub[available['publication_id']];active=any(r['policy']['information_multiplier']<1 for r in decisions);known=any(r['policy']['monitorable'] is True for r in decisions)
                vehicle_observed+=dt;vehicle_monitorable+=dt*known;vehicle_attenuated+=dt*active;vehicle_events+=int(active and not was);was=active
            normal.append(dict(group=group,seed=seed,independent_nominal_runs=1,link_count=len(ls),vehicle_observed_seconds=vehicle_observed,vehicle_any_monitorable_seconds=vehicle_monitorable,vehicle_any_attenuated_seconds=vehicle_attenuated,vehicle_alarm_episodes=vehicle_events,attenuation_events=sum(int(r['attenuation_episodes']) for r in ls),disabled_events=sum(int(r['disabled_episodes']) for r in ls),monitorable_link_seconds=sum(float(r['monitorable_duration_s']) for r in ls),unknown_link_seconds=sum(float(r['unknown_duration_s']) for r in ls),attenuated_link_seconds=sum(float(r['attenuated_duration_s']) for r in ls),disabled_link_seconds=sum(float(r['disabled_duration_s']) for r in ls)))
        for scene in ['uwb_step','uwb_ramp','multi_common_uwb']:
            ev=[r for r in events if r['group']==group and r['scenario']==scene];known=[r for r in ev if r['monitorable_event']=='True'];detected=[r for r in ev if r['detected_new_or_escalated_alert']=='True'];kd=[r for r in known if r['detected_new_or_escalated_alert']=='True']
            delays=[float(r['alarm_delay_s']) for r in detected if r['alarm_delay_s']]
            detection.append(dict(group=group,scenario=scene,all_link_fault_events=len(ev),detected_all=len(detected),missed_all=len(ev)-len(detected),monitorable_link_fault_events=len(known),detected_monitorable=len(kd),missed_monitorable=len(known)-len(kd),not_monitorable=len(ev)-len(known),timely_active_alerts=sum(r['alarm_while_fault_active']=='True' for r in ev),median_actual_alarm_delay_s=float(np.median(delays)) if delays else None,max_actual_alarm_delay_s=max(delays) if delays else None,
                alert_but_XY_worse_events=sum(r['alert_but_XY_worse']=='True' for r in ev),denominator_note='multiple links/common cause and same seeds correlated; not independent probability trials'))
    csv_write(out/'normal_by_seed.csv',normal);csv_write(out/'detection_denominators.csv',detection)
    dump(out/'summary.json',dict(stage=state['stage'],status=state['status'],cli_runs=len(state['cells']),completed=sum(c['status']=='DONE' for c in state['cells']),failed=sum(c['status']!='DONE' for c in state['cells']),publications=sum(int(r['publications']) for r in rows),protocol_sha256=sha(root/'protocol.json'),
        worse_paired_XY_counts={g:dict(worse=sum(p['delta_all_xy_rmse_state_m']>0 for p in pairs if p['group']==g),comparisons=sum(p['group']==g for p in pairs)) for g in ['Q2','Q3']},normal_by_seed=normal,detection=detection,
        field_accuracy_evaluated=False,limitations=['engineering consistency, no calibrated NIS/PL','common upstream/multiple range faults can fool shadows','new control does not erase old factors/prior','3 validation seeds per scenario, paired noise across scenarios; correlated frames are not independent runs']))
    # Three-seed full range, not SEM/probability bounds.
    scenes=plan['scenarios'];fig,axes=plt.subplots(1,3,figsize=(16,5))
    for color,group in zip(COLORS,GROUPS):
        for ax,key in zip(axes,['all_xy_rmse_state_m','all_yaw_rmse_rad','all_bias_rmse_rad_s']):
            means=[];low=[];high=[]
            for scene in scenes:
                vals=[float(r[key]) for r in by[scene,group] if r.get(key)]
                means.append(np.mean(vals) if vals else np.nan);low.append(min(vals) if vals else np.nan);high.append(max(vals) if vals else np.nan)
            ax.plot(range(len(scenes)),means,'.-',label=group,color=color);ax.fill_between(range(len(scenes)),low,high,color=color,alpha=.1)
    for ax,label in zip(axes,['ALL finite XY RMSE(m)','wrapped yaw RMSE(rad)','effective gyro bias RMSE(rad/s)']):ax.set_ylabel(label);ax.set_xticks(range(len(scenes)),scenes,rotation=55,ha='right');ax.grid(alpha=.3);ax.legend()
    fig.suptitle(state['stage']+': seed mean and full seed range; no filtering unknown outputs');fig.tight_layout();fig.savefig(out/'all_errors.png',dpi=140);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,key,mult,label in zip(axes,['mean_complete_processor_wall_s','mean_actual_release_delay_s','unknown_link_seconds'],[1000,1,1],['nominal full processing(ms)',f'nominal {timeword} release delay(s)','nominal unknown(link-seconds)']):
        v=[next((r[key+'_mean'] for r in aggregate if r['scenario']=='nominal' and r['group']==g),None) for g in GROUPS];ax.bar(range(4),[x*mult if x is not None else np.nan for x in v],color=COLORS);ax.set_xticks(range(4),GROUPS);ax.set_ylabel(label);ax.grid(axis='y',alpha=.3)
    fig.suptitle('baseline groups have no monitor; unknown is not zero/healthy');fig.tight_layout();fig.savefig(out/'nominal_cost.png',dpi=140);plt.close(fig)
    seed=plan['seeds'][0]
    for scene in ['uwb_step','multi_common_uwb','weak_missing']:
        if scene not in scenes:continue
        fig,axes=plt.subplots(5,1,figsize=(11,12),sharex=True)
        for color,group in zip(COLORS,GROUPS):
            data=read_csv(root/'runs'/f'{scene}_seed{seed}__{group}'/'truth_evaluation.csv');t=[float(r['t_s']) for r in data]
            for ax,key in [(axes[0],'xy_error_state_m'),(axes[1],'yaw_error_rad')]:ax.plot(t,[float(r[key]) if r[key] else np.nan for r in data],color=color,label=group)
            if group in ('Q1','Q3'):axes[2].plot(t,[float(r['bias_rad_s']) if r['bias_rad_s'] else np.nan for r in data],color=color,label=group)
        labels=json.loads((root/'inputs'/f'{scene}_seed{seed}'/'labels.json').read_text());origin=labels['origin_epoch_ns'];ledger=list(read_jsonl(root/'runs'/f'{scene}_seed{seed}__Q3'/'quality_ledger.jsonl.gz'));avail={r['publication_id']:r for r in read_jsonl(root/'runs'/f'{scene}_seed{seed}__Q3'/'availability.jsonl.gz')};target=[r for r in ledger if r['target']=='node_10'];ts=[(r['state_epoch_ns']-origin)/1e9 for r in target];ta=[(avail[r['publication_id']]['available_receive_epoch_ns']-origin)/1e9 for r in target]
        axes[3].plot(ts,[r['engineering_score'] if r['engineering_score'] is not None else np.nan for r in target],label='Q3 excluded-node10 engineering score',color='#009e73')
        for value,color,label in [(1.5,'orange','warn'),(3.,'red','disable'),(.75,'blue','clear')]:axes[3].axhline(value,color=color,ls='--',label=label)
        axes[4].step(ta,[r['policy']['information_multiplier'] for r in target],where='post',color='#009e73',label='frozen multiplier @'+timeword+' availability');unknown=[r['policy']['state']=='unknown' for r in target];axes[4].fill_between(ta,0,1,where=unknown,color='gray',alpha=.25,label='unknown')
        for ax,label in zip(axes,['XY error at state(m)','yaw error at state(rad)','bias estimate(rad/s)','engineering score','information multiplier']):ax.set_ylabel(label);ax.grid(alpha=.3);ax.axvspan(12,32,color='gray',alpha=.1)
        axes[0].legend(ncol=4);axes[2].legend();axes[3].legend(ncol=4,fontsize=8);axes[4].legend(fontsize=8);axes[-1].set_xlabel('time minus truth origin(s): errors/scores at state, multiplier at actual output availability');fig.suptitle(f'{scene}, predeclared first seed {seed}; fault/availability interval shaded');fig.tight_layout();fig.savefig(out/(scene+'_timeline.png'),dpi=140);plt.close(fig)
    if 'uwb_step' in scenes:
        fig,ax=plt.subplots(figsize=(7,6));truth=list(read_jsonl(root/'inputs'/f'uwb_step_seed{seed}'/'truth.jsonl.gz'));xy=np.array([r['pose'][:2] for r in truth]);ax.plot(xy[:,0],xy[:,1],'k--',label='truth')
        for color,group in zip(COLORS,GROUPS):
            data=read_csv(root/'runs'/f'uwb_step_seed{seed}__{group}'/'truth_evaluation.csv');ax.plot([float(r['base_x_m']) for r in data if r['base_x_m']],[float(r['base_y_m']) for r in data if r['base_y_m']],color=color,label=group)
        ax.set_title(f'uwb_step seed{seed}, base frame');ax.axis('equal');ax.legend();ax.grid(alpha=.3);fig.tight_layout();fig.savefig(out/'uwb_step_trajectory.png',dpi=140);plt.close(fig)
    if 'common_turn_error' in scenes:
        fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=True);origin=json.loads((root/'inputs'/f'common_turn_error_seed{seed}'/'labels.json').read_text())['origin_epoch_ns']
        for color,group in [('#0072b2','Q1'),('#009e73','Q3')]:
            pubs=list(read_jsonl(root/'runs'/f'common_turn_error_seed{seed}__{group}'/'publications.jsonl.gz'));ts=[(r['state_epoch_ns']-origin)/1e9 for r in pubs];axes[0].plot(ts,[r.get('motion_conflict_diagnostic',{}).get('raw_odom_rate_minus_gyro_rad') if r.get('motion_conflict_diagnostic',{}).get('raw_odom_rate_minus_gyro_rad') is not None else np.nan for r in pubs],label=group)
            data=read_csv(root/'runs'/f'common_turn_error_seed{seed}__{group}'/'truth_evaluation.csv');axes[1].plot([float(r['t_s']) for r in data],[float(r['yaw_error_rad']) for r in data],label=group,color=color)
        axes[0].set_ylabel('raw Odom-gyro angle difference(rad)');axes[1].set_ylabel('true yaw error(rad)');axes[1].set_xlabel('state time(s)')
        for ax in axes:ax.grid(alpha=.3);ax.legend();ax.axvspan(12,32,color='gray',alpha=.15)
        fig.suptitle('Small raw conflict is not evidence that either motion input is correct');fig.tight_layout();fig.savefig(out/'common_angle_conflict.png',dpi=140);plt.close(fig)
    print(json.dumps(dict(status='DONE',files=len(list(out.iterdir())))))


if __name__=='__main__':main()
