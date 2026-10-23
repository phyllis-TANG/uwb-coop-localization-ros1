#!/usr/bin/env python3
"""Report archived independent replays; never launches an estimator."""
from __future__ import annotations
import argparse
import collections
import csv
import json
import math
from pathlib import Path
import numpy as np
from two_car_independent_integrity import ROOT,CARS,ANCHORS
from run_two_car_independent_integrity import read,write,verify_lock,verify_record,sha,PARENT


def jsonlines(path):return [json.loads(x) for x in path.open()]


def csvwrite(path,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
        writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)


def spans(rows,end,predicate):
    events=[]
    for i,row in enumerate(rows):
        t=row['state_time_s'];stop=rows[i+1]['state_time_s'] if i+1<len(rows) else min(t+1,end)
        if not predicate(row):continue
        if events and abs(events[-1]['end_s']-t)<1e-9:
            events[-1]['end_s']=stop;events[-1]['rows'].append(row)
        else:events.append(dict(start_s=t,end_s=stop,rows=[row]))
    return events


def sumspan(events):return sum(e['end_s']-e['start_s'] for e in events)


def phase(row,previous,protocol):
    if row.get('local_odom') is None:return 'missing_odom',None,None
    if previous is None or previous.get('local_odom') is None:return 'startup',None,None
    a,b=np.array(previous['local_odom']),np.array(row['local_odom']);dt=row['state_time_s']-previous['state_time_s']
    speed=float(np.linalg.norm(b[:2]-a[:2])/dt)
    yaw=abs(math.degrees(math.atan2(math.sin(b[2]-a[2]),math.cos(b[2]-a[2]))))/dt
    rule=protocol['odom_phase_diagnostic']
    state='moving' if speed>rule['translation_speed_threshold_m_s'] else (
        'turning' if yaw>rule['yaw_speed_threshold_deg_s'] else 'odom_near_zero')
    return state,speed,yaw


def run_metrics(out,record,protocol,evaluation):
    target=out/'runs'/record['id']/'output'
    rows=jsonlines(target/'updates.jsonl');trace=jsonlines(target/'sensor_provenance.jsonl')
    delivery={r['state_time_s']:r for r in jsonlines(target/'delivery_times.jsonl')}
    worker=read(target/'worker_summary.json');end=worker['input_diagnostics']['eof_receipt_s']
    summary=dict(id=record['id'],bag_id=record['bag_id'],car=record['car'],status=record['status'],
        output_states=len(rows),first_state_s=rows[0]['state_time_s'],last_state_s=rows[-1]['state_time_s'],
        eof_receipt_s=end,initial_no_output_s=rows[0]['state_time_s'],
        trailing_no_new_state_interval_s=max(0,end-rows[-1]['state_time_s']-1),
        process_wall_s=record['process_wall_s'],worker_wall_s=worker['wall_s'],
        peak_solve_states=worker['peak_solve_states'],frontend_counters=worker['frontend_counters'])
    states=[];links=[];exclusions=[];events=[];previous=None
    for row in rows:
        t=row['state_time_s'];state,speed,yaw=phase(row,previous,protocol);previous=row
        row['odom_phase']=state;row['odom_speed_m_s']=speed;row['odom_yaw_speed_deg_s']=yaw
        sep={k:h['separation_m'] for k,h in row['exclusion_hypotheses'].items() if h['separation_m'] is not None}
        m2max=max(sep,key=sep.get) if sep else None
        pre={r['anchor']:r for r in row['prefit_current_residuals']}
        post={r['anchor']:r for r in row['postfit_current_residuals']}
        m1max=max(pre,key=lambda k:abs(pre[k]['raw_residual_m'])) if pre else None
        row['M1_max_anchor']=m1max;row['M2_max_anchor']=m2max
        d=delivery[t];assert d['result_available_receipt_s']>=row['M2_available_receipt_s']
        common=dict(bag_id=record['bag_id'],car=record['car'],state_time_s=t)
        states.append(dict(common,status=row['status'],accepted_graph=row['accepted_graph'],
            antenna_xy_m=row['antenna_xy_m'],local_odom=row.get('local_odom'),
            odom_phase=state,odom_speed_m_s=speed,odom_yaw_speed_deg_s=yaw,
            cutoff_s=row['availability_cutoff_s'],dependency_receipt_max_s=row['dependency_receipt_max_s'],
            trigger_receipt_s=row['trigger_receipt_s'],trigger_wait_beyond_cutoff_s=row['trigger_receipt_s']-row['availability_cutoff_s'],
            event_queue_s=row['modeled_event_queue_s'],M0_available_s=row['M0_available_receipt_s'],
            M1_available_s=row['M1_available_receipt_s'],M2_available_s=row['M2_available_receipt_s'],
            result_available_s=d['result_available_receipt_s'],result_age_s=d['result_available_receipt_s']-t,
            M1_statistic=row['M1']['statistic'],M1_available=row['M1']['available'],M1_alarm=row['M1']['alarm'],
            M1_reasons=row['M1']['reasons'],M1_max_anchor=m1max,
            M2_statistic_m=row['M2']['statistic'],M2_available=row['M2']['available'],M2_alarm=row['M2']['alarm'],
            M2_reasons=row['M2']['reasons'],M2_max_anchor=m2max,
            update_wall_s=row['update_wall_s'],M1_extra_wall_s=row['M1_extra_wall_s'],M2_extra_wall_s=row['M2_extra_wall_s']))
        for k in ANCHORS:
            a,b=pre.get(k,{}),post.get(k,{})
            links.append(dict(common,anchor=k,support_samples=row.get('range_sample_counts',{}).get(k,0),
                raw_median_m=a.get('raw_median_m'),corrected_once_m=a.get('corrected_median_m'),
                applied_bias_m=read(out/'configs'/(record['id']+'.json'))['model']['range_bias_m'][k],
                predicted_prefit_range_m=a.get('predicted_range_m'),
                signed_innovation_corrected_minus_prediction_m=-a['raw_residual_m'] if a else None,
                absolute_normalized_innovation=abs(a['normalized_raw_residual']) if a else None,
                posterior_predicted_minus_corrected_m=b.get('raw_residual_m'),
                posterior_robust_residual=b.get('pseudo_huber_transformed_residual'),
                posterior_irls_weight=b.get('irls_weight'),odom_phase=state))
            h=row['exclusion_hypotheses'][k]
            assert k not in h['source_anchor_ids'] and h['excluded_observations_ever_ingested']==0
            assert h['graph_states']<=21 if 'graph_states' in h else True
            exclusions.append(dict(common,excluded_anchor=k,separation_m=h['separation_m'],available=h['available'],
                reasons=h['reasons'],max_item=(k==m2max),prior_lineage_sha256=h['prior_lineage_sha256']))
        if row['dependency_receipt_max_s'] is not None:assert row['dependency_receipt_max_s']<=row['availability_cutoff_s']
    durations=[]
    for method in ['M1','M2']:
        available=spans(rows,end,lambda r:r[method]['available'])
        alarm=spans(rows,end,lambda r:r[method]['alarm'] is True)
        unavailable=spans(rows,end,lambda r:not r[method]['available'])
        warmup=spans(rows,end,lambda r:'warmup' in r['status'] and not r[method]['available'])
        monitored=sumspan(available);total=sumspan(spans(rows,end,lambda r:True))
        counts=collections.Counter(r[method+'_max_anchor'] for r in rows if r[method]['alarm'] is True)
        summary[method]=dict(available_s=monitored,covered_state_s=total,
            startup_unavailable_s=sumspan(warmup),other_unavailable_s=sumspan(unavailable)-sumspan(warmup),
            alarm_s=sumspan(alarm),alarm_fraction_of_available=sumspan(alarm)/monitored if monitored else None,
            alarm_fraction_of_covered=sumspan(alarm)/total if total else None,
            alarm_events=len(alarm),max_anchor_counts_during_alarm=dict(counts))
        for kind,groups in [('alarm',alarm),('unavailable',unavailable)]:
            for e in groups:
                rr=e.pop('rows')
                events.append(dict(bag_id=record['bag_id'],car=record['car'],method=method,kind=kind,
                    **e,duration_s=e['end_s']-e['start_s'],first_result_available_s=delivery[rr[0]['state_time_s']]['result_available_receipt_s'],
                    odom_phases=dict(collections.Counter(r['odom_phase'] for r in rr)),
                    max_anchor_counts=dict(collections.Counter(r[method+'_max_anchor'] for r in rr)),
                    reasons=sorted({s for r in rr for s in r[method]['reasons']})))
        durations.append(dict(id=record['id'],method=method,**summary[method]))
    ev=evaluation[record['bag_id']];times=ev['state_times_s'];window=[r for r in rows if r['state_time_s'] in times]
    usable=[r for r in window if r['pose'] is not None]
    local=np.array([r['local_odom'] for r in usable])
    trans=float(np.linalg.norm(np.diff(local[:,:2],axis=0),axis=1).sum()) if len(local)>1 else None
    rotation=float(np.degrees(np.abs(np.diff(np.unwrap(local[:,2])))).sum()) if len(local)>1 else None
    raw_odom=[r for r in trace if r['kind']=='odom' and times[0]<=r['association_time_s']<=times[-1]]
    speedmax=max((float(np.linalg.norm(r['linear_velocity_m_s'])) for r in raw_odom),default=None)
    yawmax=max((abs(math.degrees(r['angular_velocity_rad_s'])) for r in raw_odom),default=None)
    endpoint=np.median([r['antenna_xy_m'] for r in usable],axis=0) if usable else None
    summary['endpoint']=dict(frozen_times_s=times,actual_times_s=[r['state_time_s'] for r in usable],
        full_window_present=len(usable)==5,all_graphs_accepted=all(r['accepted_graph'] for r in usable),
        antenna_xy_m=endpoint.tolist() if endpoint is not None else None,
        manual_reference_xy_m=ev['end_antenna_xyz_m'][record['car']][:2],
        difference_to_manual_m=float(np.linalg.norm(endpoint-ev['end_antenna_xyz_m'][record['car']][:2])) if endpoint is not None else None,
        odom_path_m=trans,odom_total_yaw_deg=rotation,raw_odom_samples=len(raw_odom),
        max_recorded_linear_velocity_m_s=speedmax,max_recorded_yaw_velocity_deg_s=yawmax,
        strict_numerical_constant=trans is not None and trans<1e-6 and rotation<1e-4,
        conditional_stop_supported=len(usable)==5 and trans is not None and trans<=.005*(times[-1]-times[0]) and rotation<=1. and speedmax is not None and speedmax<=.005 and yawmax<=1.)
    summary['prediction_fallback_states']=sum(not r['accepted_graph'] for r in rows)
    summary['solver_failed_states']=sum('solver_fail' in r['status'] or 'solver_error' in r['status'] for r in rows)
    summary['missing_link_bins']={k:sum(k not in r.get('range_medians_m',{}) for r in rows) for k in ANCHORS}
    summary['max_anchor_counts_all_states']={m:dict(collections.Counter(r[m+'_max_anchor'] for r in rows)) for m in ['M1','M2']}
    summary['cost']=dict(full_update_wall_s=sum(r['update_wall_s'] for r in rows),
        M1_extra_wall_s=sum(r['M1_extra_wall_s'] for r in rows),M2_extra_wall_s=sum(r['M2_extra_wall_s'] for r in rows),
        external_logging_wall_s=worker['external_output_logging_wall_s'],
        max_event_queue_s=max(r['modeled_event_queue_s'] for r in rows),
        result_age_s=dict(zip(['min','median','p95','max'],map(float,np.percentile([s['result_age_s'] for s in states],[0,50,95,100])))))
    return summary,rows,trace,states,links,exclusions,events,durations


def figure(output,case,results):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors=dict(zip(ANCHORS,['#d1495b','#00798c','#edae49','#30638e']))
    fig,axes=plt.subplots(7,2,figsize=(18,20),sharex=True)
    for col,car in enumerate(CARS):
        summary,rows,trace,states,links,exclusions,*_=results[case+'_'+car]
        for k in ANCHORS:
            samples=[r for r in trace if r['kind']=='uwb' and k in r['wall_raw_m']]
            axes[0,col].plot([r['association_time_s'] for r in samples],[r['wall_raw_m'][k] for r in samples],lw=.55,alpha=.65,color=colors[k])
            ll=[r for r in links if r['anchor']==k and r['raw_median_m'] is not None];t=[r['state_time_s'] for r in ll]
            for i,key in [(0,'raw_median_m'),(1,'corrected_once_m'),(2,'signed_innovation_corrected_minus_prediction_m'),(3,'posterior_predicted_minus_corrected_m')]:
                axes[i,col].plot(t,[r[key] for r in ll],color=colors[k],label=k,lw=1.)
            ee=[r for r in exclusions if r['excluded_anchor']==k and r['separation_m'] is not None]
            axes[4,col].plot([r['state_time_s'] for r in ee],[r['separation_m'] for r in ee],color=colors[k],label=k)
        axes[4,col].axhline(.062191200771030145,color='k',ls='--',lw=.8)
        for y in [-.2,.2]:axes[2,col].axhline(y,color='k',ls='--',lw=.7)
        for lane,method in enumerate(['M1','M2']):
            for status,color in [('alarm','#d1495b'),('unavailable','#aaaaaa')]:
                pred=(lambda r:r[method]['alarm'] is True) if status=='alarm' else (lambda r:not r[method]['available'])
                for e in spans(rows,summary['eof_receipt_s'],pred):
                    axes[5,col].broken_barh([(e['start_s'],e['end_s']-e['start_s'])],(lane-.3,.6),facecolors=color)
        axes[5,col].set_yticks([0,1],['M1','M2']);axes[5,col].set_ylim(-.6,1.6)
        tt=[s['state_time_s'] for s in states]
        axes[6,col].plot(tt,[s['odom_speed_m_s'] if s['odom_speed_m_s'] is not None else np.nan for s in states],label='Odom translation m/s',color='#00798c')
        ax2=axes[6,col].twinx()
        ax2.plot(tt,[s['odom_yaw_speed_deg_s'] if s['odom_yaw_speed_deg_s'] is not None else np.nan for s in states],ls=':',color='#d1495b')
        ax2.set_ylabel('yaw deg/s');axes[6,col].set_xlabel('Shared bag receipt association time / s')
        labels=['Raw ranges / m (thin: samples)','Once corrected ranges / m','Innovation (corrected - prediction) / m',
                'Posterior residual (prediction - corrected) / m','Exclusion separation / m (numeric; validity below)',
                'Alarm red; unavailable grey','Odom translation speed / m/s']
        for i,label in enumerate(labels):
            axes[i,col].set_ylabel(label);axes[i,col].grid(alpha=.2)
        axes[0,col].set_title(case+' / '+car+' (independent; no peer factors)')
        axes[0,col].legend(ncol=4,fontsize=8)
        axes[4,col].legend(ncol=4,fontsize=8)
    fig.tight_layout();fig.savefig(output/(case+'_diagnostics.png'),dpi=140)
    fig.savefig(output/(case+'_diagnostics.svg'));plt.close(fig)


def build(out,output):
    verify_lock(out);inventory=read(out/'run_inventory.json');p=read(out/'protocol.json');ev=read(out/'evaluation.json')
    for r in inventory:verify_record(out,r)
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    results={r['id']:run_metrics(out,r,p,ev) for r in inventory}
    for index,name in [(3,'states.csv'),(4,'links.csv'),(5,'exclusions.csv'),(6,'events.csv'),(7,'monitor_durations.csv')]:
        csvwrite(output/name,[row for values in results.values() for row in values[index]])
    summary=[v[0] for v in results.values()]
    old=list(csv.DictReader((ROOT/PARENT/'results/trajectories.csv').open()))
    comparisons=[];correspond=[];peers=[]
    for case in p['cases']:
        cid=case['id'];figure(output,cid,results)
        for car in CARS:
            s,rows,trace,*_=results[cid+'_'+car]
            for method in ['independent','joint']:
                archived={float(r['elapsed_s']):r for r in old if r['case']==cid and r['configuration']=='per_car_walls' and r['method']==method and r['car']==car}
                paired=[(r,archived[r['state_time_s']]) for r in rows if r['pose'] is not None and r['state_time_s'] in archived]
                differences=[float(np.linalg.norm(np.array(r['antenna_xy_m'])-[float(b['antenna_x_m']),float(b['antenna_y_m'])])) for r,b in paired]
                endpoint_old=np.median([[float(archived[t]['antenna_x_m']),float(archived[t]['antenna_y_m'])] for t in ev[cid]['state_times_s']],axis=0)
                comparisons.append(dict(bag_id=cid,car=car,archived_method=method,common_states=len(paired),
                    max_trajectory_difference_m=max(differences),median_trajectory_difference_m=float(np.median(differences)),
                    archived_endpoint_difference_to_manual_m=float(np.linalg.norm(endpoint_old-ev[cid]['end_antenna_xyz_m'][car][:2])),
                    new_endpoint_difference_to_manual_m=s['endpoint']['difference_to_manual_m'],
                    interpretation='different information: full-bag smoothing vs causal fixed lag; common receipt-axis concept, new integer-ns subtraction and causal cutoff'))
            for r in trace:
                if r['kind']=='uwb' and r['peer_raw_m'] is not None:
                    peers.append(dict(bag_id=cid,car=car,association_time_s=r['association_time_s'],
                        original_header_ns=r['original_header_ns'],bag_receipt_ns=r['bag_receipt_ns'],peer_raw_m=r['peer_raw_m'],used_by_estimator=False))
    references=list(csv.DictReader((ROOT/PARENT/'results/wall_reference_diagnostics.csv').open()))
    for ref in references:
        cid,car,k=ref['case'],ref['car'],ref['anchor']
        archived=read(ROOT/PARENT/'results'/cid/'per_car_walls_inputs.json')
        times=archived['times'][:5] if ref['phase']=='start' else ev[cid]['state_times_s']
        s,rows,trace,states,links,exclusions,*_=results[cid+'_'+car]
        rr=[r for r in rows if r['state_time_s'] in times]
        ll=[r for r in links if r['anchor']==k and r['state_time_s'] in times and r['raw_median_m'] is not None]
        correspond.append(dict(bag_id=cid,car=car,anchor=k,phase=ref['phase'],
            frozen_window_start_s=times[0],frozen_window_end_s=times[-1],actual_state_times_s=[r['state_time_s'] for r in rr],
            PR38_corrected_minus_manual_geometry_m=float(ref['corrected_minus_reference_m']),
            M1_alarm_states=sum(r['M1']['alarm'] is True for r in rr),M1_available_states=sum(r['M1']['available'] for r in rr),
            M2_alarm_states=sum(r['M2']['alarm'] is True for r in rr),M2_available_states=sum(r['M2']['available'] for r in rr),
            M1_max_anchor_matches=sum(r['M1_max_anchor']==k for r in rr),M2_max_anchor_matches=sum(r['M2_max_anchor']==k for r in rr),
            median_signed_innovation_m=float(np.median([r['signed_innovation_corrected_minus_prediction_m'] for r in ll])) if ll else None,
            source=PARENT+'/results/wall_reference_diagnostics.csv',
            interpretation='temporal overlap/sensitivity correspondence only; manual-reference residual differs from model innovation; no physical fault diagnosis'))
    csvwrite(output/'PR38_comparison.csv',comparisons);csvwrite(output/'correspondence.csv',correspond)
    csvwrite(output/'peer_diagnostic_only.csv',peers)
    n10=[str(f.relative_to(ROOT)) for f in (ROOT/'docs').rglob('*') if f.is_file() and ('n10' in f.name.lower() or 'node_10' in f.name.lower())]
    write(output/'N10_report_discovery.json',dict(found_named_artifacts=n10,
        new_three_bag_report_status='待对照',note='Existing named N10 artifacts concern Oct17 historical data. No separate new three-bag N10 report found; do not infer its conclusions.',
        existing_PR38_PR39_sources=[PARENT+'/results/INTERPRETATION.md','docs/field_tests/two_car_stationary_confidence_20261023/results/REPORT.md']))
    write(output/'summary.json',dict(runs=summary,total_process_wall_s=sum(s['process_wall_s'] for s in summary),
        total_full_update_wall_s=sum(s['cost']['full_update_wall_s'] for s in summary),
        total_M1_extra_wall_s=sum(s['cost']['M1_extra_wall_s'] for s in summary),
        total_M2_extra_wall_s=sum(s['cost']['M2_extra_wall_s'] for s in summary),
        continuous_truth_available=False,thresholds=p['thresholds'],formal_estimator_runs=6))
    lines=['# 双车独立因果定位与完好性监测衔接：一页中文结论','',
        '三份历史双车包共六条分车回放已完成；没有加入车间测距、独立 IMU 或 PR39 两项策略。M1/M2 为旧阈值迁移诊断，报警不是已证实的真实故障。','',
        '|包 / 车|状态数 / 时刻s|M1 报警/可监测s|M2 报警/可监测s|冻结窗终点差cm|',
        '|---|---:|---:|---:|---:|']
    for s in summary:
        lines.append(f"|{s['bag_id']} / {s['car']}|{s['output_states']} / {s['first_state_s']:g}–{s['last_state_s']:g}|{s['M1']['alarm_s']:g}/{s['M1']['available_s']:g}|{s['M2']['alarm_s']:g}/{s['M2']['available_s']:g}|{s['endpoint']['difference_to_manual_m']*100:.2f}|")
    lines+=['','报警比例的分母为可监测状态时长；启动无输出、启动不可用与其他不可用分别记录。单状态按 [t,t+1) 描述，末段裁到实际 bag EOF。','',
        '对应检查（同一 bag、车、链路、起终点窗口；最大排除项只表示敏感度，不能当作故障隔离）：','']
    for cid,car,k,stage in [('015334','car2','node_10','start'),('050447','car1','node_8','start'),('050447','car1','node_8','end'),('050447','car2','node_10','end')]:
        r=next(r for r in correspond if (r['bag_id'],r['car'],r['anchor'],r['phase'])==(cid,car,k,stage))
        lines.append(f"- {cid} {car} {k} {stage}：PR38 校正测距−人工几何 {r['PR38_corrected_minus_manual_geometry_m']:+.3f}m；本轮重叠 {len(r['actual_state_times_s'])} 状态中 M1/M2 报警 {r['M1_alarm_states']}/{r['M2_alarm_states']}，该锚为 M1/M2 最大项 {r['M1_max_anchor_matches']}/{r['M2_max_anchor_matches']} 次。")
    lines+=['','其余报警保留完整事件、运动阶段、四锚创新和排除解记录；没有连续位置真值与故障标签，无法判断真实误报/漏警，也无法把报警唯一归因于某个物理原因。新三包 N10 专项报告尚未发现，标记“待对照”。PR39 静态 N10 正负参考差来自其他静态包，不能当作本轮逐时刻故障标签。','',
        '人工终点只按事先冻结的 PR38 末五时刻评价；停止支持、实际覆盖和原始 Odom 速度另列。定位与旧整包独立/联合结果的信息范围不同，位置差不等于真实全程误差。两车共用接收时间不证明物理同步。','',
        f"六条正式进程合计 {sum(s['process_wall_s'] for s in summary):.3f}s；最大单条 {max(s['process_wall_s'] for s in summary):.3f}s。两车采用独立虚拟工作者，1秒等待、触发等待、计算、排队和当前输出写盘后的可获得时间单列；不据此宣称平台满足实时要求。"]
    (output/'CONCLUSION_ZH.md').write_text('\n'.join(lines)+'\n')
    details=lines+['','## 分车可用性、计算与边界','']
    for s in summary:
        details += [f"### {s['id']}",'',f"前端计数：`{json.dumps(s['frontend_counters'])}`；缺链路状态：`{json.dumps(s['missing_link_bins'])}`。",
            f"预测回退 {s['prediction_fallback_states']}，求解失败 {s['solver_failed_states']}；启动无输出 {s['initial_no_output_s']:g}s。",
            f"M1/M2 启动不可用 {s['M1']['startup_unavailable_s']:g}/{s['M2']['startup_unavailable_s']:g}s，其他不可用 {s['M1']['other_unavailable_s']:g}/{s['M2']['other_unavailable_s']:g}s。",
            f"全量更新/M1/M2 计算累计 {s['cost']['full_update_wall_s']:.4f}/{s['cost']['M1_extra_wall_s']:.4f}/{s['cost']['M2_extra_wall_s']:.4f}s；可获得结果年龄 `{json.dumps(s['cost']['result_age_s'])}`。",
            f"冻结终点评价和停止支持：`{json.dumps(s['endpoint'],ensure_ascii=False)}`。",'']
    details+=['## 图与表','',
        'states.csv 为逐状态结果/时间/运动状态，links.csv 保留四锚原始与一次修正中位数、创新、后验残差和支持数；exclusions.csv 为四个独立排除假设，events.csv 为连续报警/不可用事件；完整先验矩阵、偏移和历史链哈希在各运行 updates.jsonl。',
        'sensor_provenance.jsonl 保留原始 header_ns、bag 接收 ns、关联时间及各原始观测；peer_diagnostic_only.csv 双向数据仅诊断。PR38_comparison.csv 只作因果/整包输出比较，correspondence.csv 覆盖全部48个起终点×车×墙锚窗口。',
        '数值解分离曲线在不可用时仍可显示，不能作可信监测结论；有效性见灰色区间及 CSV available/reasons。原始创新为 corrected−prediction，后验残差为 prediction−corrected。',
        '模型可获得时间排除 bag 解码、输入档案写盘和进程启动，这些均计入实际单条180秒预算。两车虚拟队列独立，正式进程串行执行；未测试真实并发平台。','']
    for c in p['cases']:details.append(f"![{c['id']} 两车共用时间轴]({c['id']}_diagnostics.png)")
    (output/'REPORT.md').write_text('\n'.join(details)+'\n')
    verify_lock(out)
    print('Reported six archived runs, all four wall links and 48 correspondence windows',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    if not a.output.resolve().is_relative_to(ROOT):raise ValueError('Output must stay in project')
    build(a.experiment.resolve(),a.output.resolve())


if __name__=='__main__':main()
