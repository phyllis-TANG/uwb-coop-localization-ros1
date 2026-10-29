"""Only this post-run evaluator receives truth. No estimator imports."""
import math
import numpy as np
from common import SPEC
from decisions import primary_names


def ant(p, model):
    lx,ly=model['base_to_antenna_body_xy_m']; c,s=math.cos(p[2]),math.sin(p[2])
    return np.array([p[0]+c*lx-s*ly,p[1]+s*lx+c*ly,model['antenna_height_m']])


def wrap(v):return math.atan2(math.sin(v),math.cos(v))


def count_episodes(values):
    return sum(v and (i==0 or not values[i-1]) for i,v in enumerate(values))


def evaluate(scenario, rows, truth, config):
    by_time={r['state_epoch_ns']:r for r in truth}
    trajectory=[]; declarations=[]; ss_rows=[]
    common=set(r['state_epoch_ns'] for r in rows if all(d['computable'] for name in primary_names() for d in r['monitor']['declarations'][name]))
    for r in rows:
        t=by_time[r['state_epoch_ns']]; pose=np.asarray(r['pose']); m=r['monitor']
        aa=[ant(pose[3*i:3*i+3],config['models'][car]) for i,car in enumerate(('car1','car2'))]
        tt=[np.array(t['cars'][car]['antenna_xyz_m']) for car in ('car1','car2')]
        relative=float(np.linalg.norm((aa[1]-aa[0])[:2]-(tt[1]-tt[0])[:2]))
        distance_error=float(np.linalg.norm(aa[1]-aa[0])-np.linalg.norm(tt[1]-tt[0]))
        for ci,car in enumerate(('car1','car2')):
            ref=t['cars'][car]; p=pose[3*ci:3*ci+3]
            xyerr=float(np.linalg.norm(aa[ci][:2]-tt[ci][:2])); yawerr=wrap(p[2]-ref['pose'][2])
            aux=r['monitor']['subset_results'].get('peer',{}).get('pose')
            peerfree_err=None if aux is None else float(np.linalg.norm(ant(aux[3*ci:3*ci+3],config['models'][car])[:2]-tt[ci][:2]))
            trajectory.append(dict(scenario=scenario,car=car,t_s=r['state_time_s'],state_epoch_ns=r['state_epoch_ns'],
                cutoff_epoch_ns=r['availability_cutoff_epoch_ns'],main_accepted=r['accepted_graph'],main_status=r['status'],
                common_computable=r['state_epoch_ns'] in common,base_x_m=float(p[0]),base_y_m=float(p[1]),yaw_rad=float(p[2]),
                antenna_x_m=float(aa[ci][0]),antenna_y_m=float(aa[ci][1]),xy_error_m=xyerr,
                base_xy_error_m=float(np.linalg.norm(p[:2]-ref['pose'][:2])),yaw_error_rad=yawerr,
                relative_xy_error_m=relative,distance_error_m=distance_error,peer_free_xy_error_m=peerfree_err,
                q=m['b0'].get('engineering_q'),q_state=m['b0']['state'],
                wrapper_emit_wall_s=r['total_monitored_emit_wall_s'],numeric_graphs_wall_s=m['graph_wall_s'],
                influence_wall_s=m['covariance_wall_s'],b1_and_declarations_wall_s=m['four_anchor_and_declaration_wall_s'],
                monitor_available_virtual_s=r['monitor_available_time_virtual_s'],
                delay_virtual_s=r['monitor_available_time_virtual_s']-r['state_time_s']))
            for name, pair in m['declarations'].items():
                d=pair[ci]
                declarations.append(dict(scenario=scenario,car=car,t_s=r['state_time_s'],state_epoch_ns=r['state_epoch_ns'],
                    profile=name,computable=d['computable'],available=d['available'],alarm=d['alarm'],reason=d['reason'],
                    common_computable=r['state_epoch_ns'] in common,xy_error_m=xyerr,yaw_error_rad=yawerr,
                    available_virtual_s=r['monitor_available_time_virtual_s']))
            for group,pair in m['ss'].items():
                s=pair[ci]
                c=s.get('covariance');delta=s.get('delta_xy_m')
                ss_rows.append(dict(scenario=scenario,car=car,t_s=r['state_time_s'],group=group,
                    computable=s['computable'],reason=s['reason'],rank=s.get('rank'),statistic=s['statistic'],
                    delta_x_m=None if delta is None else delta[0],delta_y_m=None if delta is None else delta[1],
                    separation_m=s.get('separation_m'),cov_xx=None if c is None else c[0][0],
                    cov_xy=None if c is None else c[0][1],cov_yy=None if c is None else c[1][1],
                    cross_norm=None if s.get('cross_covariance') is None else float(np.linalg.norm(s['cross_covariance']))))
    metrics=[];episodes=[]
    for car in ('car1','car2'):
        tt=[t for t in trajectory if t['car']==car]
        names=rows[0]['monitor']['declarations']
        for name in names:
            full=[d for d in declarations if d['car']==car and d['profile']==name]
            for al in SPEC['alert_limits_m']:
                over=[d['xy_error_m']>al for d in full]
                k=0
                while k<len(full):
                    if not over[k]:k+=1;continue
                    end=k+1
                    while end<len(full) and over[end]:end+=1
                    seg=full[k:end]
                    alarms=[d for d in seg if d['alarm']]
                    protection=[d for d in seg if d['alarm'] or not d['available']]
                    episodes.append(dict(scenario=scenario,car=car,profile=name,AL_m=al,start_s=seg[0]['t_s'],end_s=seg[-1]['t_s']+1,
                        overlimit_s=len(seg),hmi_s=sum(d['available'] and not d['alarm'] for d in seg),
                        first_alarm_s=alarms[0]['t_s'] if alarms else None,
                        alarm_delay_state_s=alarms[0]['t_s']-seg[0]['t_s'] if alarms else None,
                        alarm_delay_virtual_s=alarms[0]['available_virtual_s']-seg[0]['t_s'] if alarms else None,
                        alarm_right_censored=not bool(alarms),protection_delay_state_s=protection[0]['t_s']-seg[0]['t_s'] if protection else None,
                        protection_right_censored=not bool(protection),
                        alarm_already_present_at_start=bool(seg[0]['alarm']),unknown_at_start=not seg[0]['computable']))
                    k=end
                for period,(lo,hi) in SPEC['evaluation_intervals'].items():
                    for coverage in ('all_published','common_computable'):
                        ds=[d for d in full if lo<=d['t_s']<hi and (coverage=='all_published' or d['common_computable'])]
                        ts=[d for d in tt if lo<=d['t_s']<hi and (coverage=='all_published' or d['common_computable'])]
                        n=len(ds)
                        metrics.append(dict(scenario=scenario,car=car,profile=name,AL_m=al,period=period,coverage=coverage,
                            denominator_s=n,available_s=sum(d['available'] for d in ds),available_rate=sum(d['available'] for d in ds)/n if n else None,
                            unknown_s=sum(not d['computable'] for d in ds),alarm_s=sum(d['alarm'] for d in ds),
                            alarm_episodes=count_episodes([d['alarm'] for d in ds]),
                            nominal_false_alarm_s=sum(d['alarm'] for d in ds) if scenario=='nominal' else None,
                            overlimit_s=sum(d['xy_error_m']>al for d in ds),
                            overlimit_noalarm_s=sum(d['xy_error_m']>al and not d['alarm'] for d in ds),
                            hmi_s=sum(d['xy_error_m']>al and d['available'] and not d['alarm'] for d in ds),
                            xy_rmse_m=float(np.sqrt(np.mean([d['xy_error_m']**2 for d in ts]))) if n else None,
                            yaw_rmse_rad=float(np.sqrt(np.mean([d['yaw_error_rad']**2 for d in ts]))) if n else None,
                            relative_xy_rmse_m=float(np.sqrt(np.mean([d['relative_xy_error_m']**2 for d in ts]))) if n else None,
                            peerfree_xy_rmse_m=float(np.sqrt(np.mean([d['peer_free_xy_error_m']**2 for d in ts]))) if n else None,
                            main_failure_s=sum(d['main_status'].startswith('predict_only_solver') or d['main_status']=='predict_only_marginal_error' for d in ts)))
    return dict(trajectory=trajectory,declarations=declarations,ss=ss_rows,metrics=metrics,episodes=episodes)
