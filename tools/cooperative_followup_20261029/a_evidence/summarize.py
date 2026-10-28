#!/usr/bin/env python3
"""Descriptive readback and figures; never imports or invokes an estimator."""
import argparse
import json
from collections import Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io_evidence import read, table, csvwrite, dump, sha, SCENARIOS, METHODS
from signals import antenna, wrap, CARS

PERIODS = dict(all=(1,64), pre=(3,24), fault=(24,38), recovery=(38,48),
               late=(48,64), recovery_0_20=(38,58), recovery_20plus=(58,64))
COLORS = dict(I='#555555', J='#ca5100', W025='#228833', C004='#4477aa', K004='#aa3377')

def number(v):
    if v == '': return None
    if v in ('True','False'): return v == 'True'
    try: return float(v)
    except ValueError: return v

def parsed(path):
    return [{k:(int(v) if k.endswith('_ns') and v else number(v)) for k,v in x.items()} for x in table(path)]

def rms(xs):
    return float(np.sqrt(np.mean(np.square(xs)))) if len(xs) else None

def save(fig,path):
    fig.tight_layout(); fig.savefig(path,dpi=140,metadata={'Software':'Task A read-only evidence'}); plt.close(fig)

def shading(ax, scenario):
    ax.axvspan(1,3,color='grey',alpha=.12)
    if scenario != 'nominal': ax.axvspan(24,38,color='orange',alpha=.12)
    ax.axvline(58,color='grey',ls=':',lw=.8)
    ax.grid(alpha=.2); ax.set_xlim(1,63)

def main(analysis,evidence,out):
    out.mkdir(exist_ok=False)
    d=parsed(analysis/'diagnostics.csv'); signals=parsed(analysis/'local_signals_offline_join.csv')
    get=lambda s,m,c: [x for x in d if x['scenario']==s and x['method']==m and x['car']==c]
    grouped={(s,m,c):get(s,m,c) for s in SCENARIOS for m in METHODS for c in CARS}
    comparison=[]; modes=[]; differences=[]
    original_costs={(x['scenario'],x['method']):x for x in table(evidence/'public_snapshot/results/costs.csv')}
    for s in SCENARIOS:
        for m in METHODS:
            rows=get(s,m,'car1'); cnt=Counter(v['publication_mode'] for v in rows)
            modes.append(dict(scenario=s,method=m,denominator=63,finite=sum(v['finite'] for v in rows),
                              reference_accepted=sum(v['reference_accepted'] for v in rows),
                              reference_valid_pairs=sum(v['reference_pair_valid'] for v in rows),
                              reference_valid_triples=sum(v['reference_triplet_valid'] for v in rows),
                              normal_joint=cnt['normal_joint'],independent=cnt['independent'],post_clip=cnt['post_clip'],
                              fallback=cnt['reference_fallback'],unknown=cnt['unknown'],unpublished=63-len(rows),
                              timeout=int(original_costs[s,m]['timeout']),failure=int(original_costs[s,m]['failure']),
                              main_success=sum(v['main_success'] for v in rows),joint_success=sum(v['joint_success'] for v in rows)))
            for car in CARS:
                for per,(lo,hi) in PERIODS.items():
                    v=[x for x in get(s,m,car) if lo<=x['t_s']<hi]
                    normal=[x for x in get('nominal',m,car) if lo<=x['t_s']<hi]
                    indep=[x for x in get(s,'I',car) if lo<=x['t_s']<hi]
                    rm=rms([x['true_error_xy_m'] for x in v])
                    comparison.append(dict(scenario=s,method=m,car=car,period=per,denominator=len(v),finite=len(v),
                        reference_accepted=sum(x['reference_accepted'] for x in v),xy_rmse_m=rm,
                        yaw_rmse_rad=rms([x['true_error_yaw_rad'] for x in v]),
                        relative_xy_rmse_m=rms([x['relative_xy_error_m'] for x in v]),
                        antenna_distance_rmse_m=rms([x['distance_error_m'] for x in v]),
                        same_input_vs_I_delta_rmse_m=rm-rms([x['true_error_xy_m'] for x in indep]),
                        same_method_vs_nominal_delta_rmse_m=rm-rms([x['true_error_xy_m'] for x in normal]),
                        mean_help_vs_I_m=float(np.mean([max(y['true_error_xy_m']-x['true_error_xy_m'],0) for x,y in zip(v,indep)])),
                        mean_harm_vs_I_m=float(np.mean([max(x['true_error_xy_m']-y['true_error_xy_m'],0) for x,y in zip(v,indep)]))))
        for car in CARS:
            for k,c in zip(get(s,'K004',car),get(s,'C004',car)):
                differences.append(dict(scenario=s,car=car,t_s=k['t_s'],state_epoch_ns=int(k['state_epoch_ns']),cutoff_epoch_ns=int(k['cutoff_epoch_ns']),
                    reference_accepted=k['reference_accepted'],C_mode=c['publication_mode'],K_mode=k['publication_mode'],
                    K_minus_C_error_xy_m=k['true_error_xy_m']-c['true_error_xy_m'],
                    K_minus_C_yaw_rad=wrap(k['yaw_rad']-c['yaw_rad']),
                    K_minus_C_antenna_xy_m=float(np.hypot(k['antenna_x_m']-c['antenna_x_m'],k['antenna_y_m']-c['antenna_y_m'])),
                    C_main_to_publish_xy_m=c['main_to_publish_xy_m'],K_main_to_publish_xy_m=k['main_to_publish_xy_m']))
    csvwrite(out/'method_comparison.csv',comparison);csvwrite(out/'publication_counts.csv',modes);csvwrite(out/'K_C_differences.csv',differences)
    # Normal-range overlaps are descriptive counterexamples, not a fitted detector.
    signal_names=['wall_post_rms_m','wall_post_whitened_rms','wall_raw_MAD_mean_m','wall_count','wall_samples',
                  'wall_geometry_condition','GN_xy_trace_sigma_proxy_m','prediction_correction_xy_m','wall_prediction_rms_m']
    overlaps=[]
    for car in CARS:
        for scope,start in [('reference_accepted',3),('after_first_accepted',4)]:
            normal=[v for v in signals if v['scenario']=='nominal' and v['car']==car and v['t_s']>=start]
            for metric in signal_names:
                low=min(x[metric] for x in normal); high=max(x[metric] for x in normal)
                for period,(lo,hi) in PERIODS.items():
                    v=[x for x in signals if x['scenario']!='nominal' and x['car']==car and max(lo,start)<=x['t_s']<hi]
                    within=[x for x in v if low<=x[metric]<=high]
                    overlaps.append(dict(car=car,scope=scope,normal_n=len(normal),metric=metric,normal_min=low,normal_max=high,
                        period=period,n=len(v),inside_normal_range=len(within),fault_input_min=min([x[metric] for x in v],default=None),fault_input_max=max([x[metric] for x in v],default=None),
                        max_true_error_among_overlap_m=max([x['offline_true_error_xy_m'] for x in within],default=None)))
    csvwrite(out/'local_range_overlap.csv',overlaps)
    csvwrite(out/'local_witnesses.csv',[x for x in signals if x['t_s'] in [24,30,37,38,47,50,54,58,59,63]])
    receipt=json.loads((evidence/'ARCHIVE_CHECK.json').read_text());root=Path(receipt['matrix_root']);index=json.loads((root/'RUN_INDEX.json').read_text())
    runs={(c['case'].removesuffix('_seed101'),c['method']):read(root/c['path']/'updates.jsonl.gz') for c in index['cells'] if c['method'] in METHODS}
    config=json.loads((root/'inputs/nominal_seed101/config.json').read_text())
    # Snapshot identity and clipping readback, using independent antenna equations.
    checks=[];history=[]
    for scenario in SCENARIOS:
        for j,c,k,i in zip(runs[scenario,'J'],runs[scenario,'C004'],runs[scenario,'K004'],runs[scenario,'I']):
            assert c['snapshot']==j['snapshot'] and c['main_pose']==j['pose']
            assert c['pose'][2]==j['pose'][2] and c['pose'][5]==j['pose'][5]
            assert k['pose']==k['main_pose']==k['snapshot']['states'][-1]
            assert not i['snapshot']['peer_enabled'] and not i['provenance']['prior_peer_factor_ids'] and not i['provenance']['window_peer_factor_ids']
            assert c.get('covariance') is None and k.get('covariance') is None
            if i['accepted_graph']:
                for n,car in enumerate(CARS):
                    a=antenna(j['pose'][3*n:3*n+3],config['models'][car])[:2];b=antenna(i['pose'][3*n:3*n+3],config['models'][car])[:2]
                    expected=b+(a-b)*min(1,.04/np.linalg.norm(a-b)) if np.linalg.norm(a-b) else b
                    actual=antenna(c['pose'][3*n:3*n+3],config['models'][car])[:2]
                    assert np.linalg.norm(expected-actual)<2e-14
            checks.append(dict(scenario=scenario,t_s=i['state_time_s'],C_snapshot_equals_J=True,C_yaw_equals_J=True,K_publish_equals_main=True,I_history_peer_free=True,covariance_is_null=True))
    # Follow stored consumed-factor provenance; no reconstruction or clearing of priors.
    for method in METHODS:
        nominal=runs['nominal',method];fault=runs['car1_common_wall_bias',method]
        changed={x['state_epoch_ns'] for x,y in zip(fault,nominal) if x['bins']['car1']['observations']!=y['bins']['car1']['observations']}
        consumed=set();previous_prior=None
        for x,y in zip(fault,nominal):
            p=x['provenance']
            for step in p['marginalizations']:
                if previous_prior is not None: assert step['prior_before_id']==previous_prior
                previous_prior=step['prior_after_id']
                for factor in step['consumed_wall_factor_ids']:
                    if factor.startswith('wall|car1|') and int(factor.split('|')[-1]) in changed: consumed.add(factor)
            assert previous_prior is None or previous_prior==p['current_prior_id']
            active=[t for t in x['snapshot']['times_s'] if int(x['state_epoch_ns']+round((t-x['state_time_s'])*1e9)) in changed]
            ant_f=[antenna(x['pose'][3*n:3*n+3],config['models'][car]) for n,car in enumerate(CARS)]
            ant_n=[antenna(y['pose'][3*n:3*n+3],config['models'][car]) for n,car in enumerate(CARS)]
            H=np.array(x['snapshot']['prior']['matrix']);H=H.T@H
            history.append(dict(method=method,t_s=x['state_time_s'],state_epoch_ns=x['state_epoch_ns'],cutoff_epoch_ns=x['availability_cutoff_epoch_ns'],
                publication_mode=x.get('publication_mode','independent' if method=='I' and x['accepted_graph'] else 'normal_joint' if x['accepted_graph'] else 'unknown'),
                active_changed_wall_bin_n=len(active),consumed_changed_wall_factor_n=len(consumed),current_prior_id=p['current_prior_id'],
                prior_peer_n=len(p['prior_peer_factor_ids']),prior_cross_norm=float(np.linalg.norm(H[:3,3:])),prior_affine_norm=float(np.linalg.norm(x['snapshot']['prior']['offset'])),
                paired_normal_car1_separation_m=float(np.linalg.norm(ant_f[0][:2]-ant_n[0][:2])),paired_normal_car2_separation_m=float(np.linalg.norm(ant_f[1][:2]-ant_n[1][:2])),
                paired_normal_car1_yaw_difference_rad=wrap(x['pose'][2]-y['pose'][2]),paired_normal_car2_yaw_difference_rad=wrap(x['pose'][5]-y['pose'][5])))
    csvwrite(out/'snapshot_identity_checks.csv',checks);csvwrite(out/'history_readback.csv',history)
    dump(out/'SUMMARY_CHECK.json',dict(status='PASS',estimator_runs=0,source_sha256=sha(Path(__file__)),
        input_sha256={p.name:sha(p) for p in [analysis/'diagnostics.csv',analysis/'local_signals_offline_join.csv',evidence/'ARCHIVE_CHECK.json']},
        clipping_epochs_checked=126,snapshot_identity_epochs_checked=126,history_records=315,
        limitations=['No hardware acceptance limit','No published covariance; GN proxy only','No isolated prior intervention','One exposed seed, two paired conditions']))
    # Same-epoch figures. Shading is offline annotation only.
    for scenario in SCENARIOS:
        fig,axes=plt.subplots(4,2,figsize=(12,11),sharex=True)
        for j,car in enumerate(CARS):
            for method in METHODS:
                vs=get(scenario,method,car);t=[x['t_s'] for x in vs]
                for r,(key,scale,label) in enumerate([
                    ('true_error_xy_m',1000,'Antenna XY true error (mm)'),
                    ('true_error_yaw_rad',180/np.pi,'Wrapped yaw true error (deg)'),
                    ('publish_step_xy_m',1000,'1 s publication step (mm)'),
                    ('published_odom_body_conflict_m',1000,'Publication/Odom translation conflict (mm)')]):
                    axes[r,j].plot(t,[np.nan if x[key] is None else x[key]*scale for x in vs],label=method,color=COLORS[method],lw=1.2)
                    axes[r,j].set_ylabel(label);shading(axes[r,j],scenario)
            axes[0,j].set_title(car+' | '+scenario);axes[-1,j].set_xlabel('State time (s); cutoff = state + 1 s')
        axes[0,0].legend(ncol=5,fontsize=8);save(fig,out/(scenario+'_publication.png'))
    fig,axes=plt.subplots(4,2,figsize=(12,11),sharex=True)
    scenario='car1_common_wall_bias'
    for j,car in enumerate(CARS):
        for method in METHODS:
            vs=get(scenario,method,car);t=[x['t_s'] for x in vs]
            for r,(key,scale,label) in enumerate([
                ('main_to_publish_xy_m',1000,'Main-to-publication separation (mm)'),
                ('publish_rate_change_mps2',1000,'1 s secant-rate change (mm/s^2)'),
                ('window_previous_vs_previous_publication_xy_m',1000,'Window old state vs prior publication (mm)'),
                ('peer_residual_published_m',1000,'Signed peer residual at publication (mm)')]):
                axes[r,j].plot(t,[np.nan if x[key] is None else x[key]*scale for x in vs],label=method,color=COLORS[method],lw=1.2)
                axes[r,j].set_ylabel(label);shading(axes[r,j],scenario)
        axes[0,j].set_title(car);axes[-1,j].set_xlabel('State time (s); sample differences are not instantaneous motion')
    axes[0,0].legend(ncol=5,fontsize=8);save(fig,out/'publication_state_gaps.png')
    fig,axes=plt.subplots(4,2,figsize=(12,11),sharex=True)
    for j,car in enumerate(CARS):
        for scenario,color in zip(SCENARIOS,['#4477aa','#cc3311']):
            vs=[x for x in signals if x['scenario']==scenario and x['car']==car];t=[x['t_s'] for x in vs]
            for r,(key,scale,label) in enumerate([
                ('offline_true_error_xy_m',1000,'I antenna XY true error (mm; offline only)'),
                ('wall_post_rms_m',1000,'I current-wall posterior RMS (mm)'),
                ('GN_xy_trace_sigma_proxy_m',1000,'I nominal GN trace sigma proxy (mm)'),
                ('prediction_correction_xy_m',1000,'I prediction correction (mm)')]):
                axes[r,j].plot(t,[np.nan if x[key] is None else x[key]*scale for x in vs],label=scenario,color=color,lw=1.3)
                axes[r,j].set_ylabel(label);shading(axes[r,j],'car1_common_wall_bias')
        axes[0,j].set_title(car+' | peer-free local signals');axes[-1,j].set_xlabel('State time (s); no fitted alarm threshold')
    axes[0,0].legend(fontsize=8);save(fig,out/'local_signals.png')
    fig,axes=plt.subplots(2,2,figsize=(12,7),sharex=True)
    for j,car in enumerate(CARS):
        vs=[x for x in differences if x['car']==car and x['scenario']!='nominal']
        axes[0,j].plot([x['t_s'] for x in vs],[x['K_minus_C_yaw_rad']*180/np.pi for x in vs],color=COLORS['K004']);axes[0,j].set_ylabel('K004 - C004 yaw (deg)')
        for method in METHODS:
            vs=[x for x in history if x['method']==method]
            axes[1,j].plot([x['t_s'] for x in vs],[x['paired_normal_'+car+'_separation_m']*1000 for x in vs],color=COLORS[method],label=method)
        axes[1,j].set_ylabel('Same method: biased - nominal XY norm (mm)');axes[1,j].set_xlabel('State time (s)');axes[0,j].set_title(car)
        for ax in axes[:,j]:shading(ax,'car1_common_wall_bias')
    axes[1,0].legend(ncol=5,fontsize=8);save(fig,out/'yaw_and_history_tail.png')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analysis',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();main(a.analysis,a.evidence,a.output)
