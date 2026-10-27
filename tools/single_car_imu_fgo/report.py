#!/usr/bin/env python3
"""Fixed-seed plots and complete negative-result tables; no model selection."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from evaluate import read_csv,csv_write
from io_utils import dump,read_jsonl,sha

ARMS=['F0','F1','F2','F3'];COLORS=['#777777','#0072b2','#d55e00','#009e73']


def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.experiment;out=a.output;out.mkdir(parents=True,exist_ok=False)
    protocol=json.loads((root/'protocol.json').read_text());state=json.loads((root/'checkpoint.json').read_text());rows=read_csv(root/'metrics.csv');groups=defaultdict(list)
    for r in rows:groups[(r['scenario'],r['arm'])].append(r)
    aggregates=[]
    keys=['all_finite_xy_rmse_state_m','all_finite_yaw_rmse_rad','all_finite_bias_rmse_rad_s','common_valid_xy_rmse_state_m','estimate_valid_coverage','solver_failure_rate','mean_update_wall_s','max_update_wall_s','max_publication_delay_s','all_finite_xy_rmse_estimated_available_m']
    for (scene,arm),values in groups.items():
        entry=dict(scenario=scene,arm=arm,seeds=len(values))
        for k in keys:
            v=[float(r[k]) for r in values if r[k]!=''];entry[k+'_mean']=float(np.mean(v)) if v else None
        aggregates.append(entry)
    csv_write(out/'aggregate.csv',aggregates);pairs=[];index={(r['scenario'],r['seed'],r['arm']):r for r in rows}
    for r in rows:
        if r['arm']!='F3':continue
        for reference in ['F0','F1','F2']:
            other=index[(r['scenario'],r['seed'],reference)]
            pairs.append(dict(scenario=r['scenario'],seed=r['seed'],reference_arm=reference,delta_all_finite_xy_rmse_m=float(r['all_finite_xy_rmse_state_m'])-float(other['all_finite_xy_rmse_state_m']),
                delta_common_valid_xy_rmse_m=float(r['common_valid_xy_rmse_state_m'])-float(other['common_valid_xy_rmse_state_m']) if r['common_valid_xy_rmse_state_m'] and other['common_valid_xy_rmse_state_m'] else None))
    csv_write(out/'paired_differences.csv',pairs)
    dump(out/'summary.json',dict(status=state['status'],cli_runs=len(state['cells']),metric_rows=len(rows),completed=sum(c['status']=='DONE' for c in state['cells']),failed=sum(c['status']!='DONE' for c in state['cells']),batch_elapsed_s=state['elapsed_s'],protocol_sha256=sha(root/'protocol.json'),
        F3_worse_all_finite_counts={ref:dict(worse=sum(p['delta_all_finite_xy_rmse_m']>0 for p in pairs if p['reference_arm']==ref),total=sum(p['reference_arm']==ref for p in pairs)) for ref in ['F0','F1','F2']},
        field_accuracy_evaluated=False,independent_trials='3 fixed development seeds per scenario, no frame-count independence claim'))
    scenes=protocol['scenarios'];fig,axes=plt.subplots(1,2,figsize=(14,5))
    for color,arm in zip(COLORS,ARMS):
        for ax,key in zip(axes,['all_finite_xy_rmse_state_m','common_valid_xy_rmse_state_m']):
            means=[];lo=[];hi=[]
            for s in scenes:
                values=[float(r[key]) for r in groups[(s,arm)] if r[key]];means.append(np.mean(values) if values else np.nan);lo.append(min(values) if values else np.nan);hi.append(max(values) if values else np.nan)
            ax.plot(range(len(scenes)),means,'.-',color=color,label=arm);ax.fill_between(range(len(scenes)),lo,hi,color=color,alpha=.1)
    for ax,title in zip(axes,['ALL finite published outputs incl. gaps/failures','FOUR-ARM common valid states']):
        ax.set_title(title);ax.set_ylabel('base XY RMSE at state time(m)');ax.set_xticks(range(len(scenes)),scenes,rotation=45,ha='right');ax.grid(alpha=.3);ax.legend()
    fig.suptitle('Synthetic development: 3 seeds mean and full seed range');fig.tight_layout();fig.savefig(out/'all_and_common_errors.png',dpi=150);plt.close(fig)
    seed=31
    for scene in ['nominal','gyro_constant_bias']:
        fig,ax=plt.subplots(figsize=(7,6));truth=list(read_jsonl(root/'inputs'/f'{scene}_seed{seed}'/'truth.jsonl.gz'));xy=np.array([t['pose'][:2] for t in truth]);ax.plot(xy[:,0],xy[:,1],'k--',label='truth')
        for color,arm in zip(COLORS,ARMS):
            series=read_csv(root/'runs'/f'{scene}_seed{seed}__{arm}'/'synthetic_timeseries.csv');ax.plot([float(r['base_x_m']) for r in series if r['base_x_m']],[float(r['base_y_m']) for r in series if r['base_y_m']],color=color,label=arm)
        ax.set_title(scene+' seed31, base_footprint');ax.set_xlabel('x(m)');ax.set_ylabel('y(m)');ax.axis('equal');ax.grid(alpha=.3);ax.legend();fig.tight_layout();fig.savefig(out/(scene+'_trajectory.png'),dpi=150);plt.close(fig)
    for scene in ['gyro_constant_bias','gyro_drift','range_bias','velocity_slip','imu_gap','stationary_unobservable']:
        fig,axes=plt.subplots(4,1,figsize=(10,10),sharex=True)
        for color,arm in zip(COLORS,ARMS):
            series=read_csv(root/'runs'/f'{scene}_seed{seed}__{arm}'/'synthetic_timeseries.csv');t=[float(r['t_s']) for r in series]
            for ax,key in [(axes[0],'xy_error_state_m'),(axes[1],'yaw_error_rad')]:ax.plot(t,[float(r[key]) if r[key] else np.nan for r in series],color=color,label=arm)
            if arm in ('F2','F3'):axes[2].plot(t,[float(r['bias_rad_s']) if r['bias_rad_s'] else np.nan for r in series],color=color,label=arm)
            axes[3].step(t,[int(r['estimate_valid']=='True')+.06*ARMS.index(arm) for r in series],where='post',color=color,label=arm)
            if arm=='F3':axes[2].plot(t,[float(r['true_bias_rad_s']) for r in series],'k--',label='true residual bias')
        for ax,label in zip(axes,['base XY error(m)','wrapped yaw error(rad)','residual bias(rad/s)','valid flag (offset per arm)']):
            ax.set_ylabel(label);ax.grid(alpha=.3)
            if scene in ('imu_gap','velocity_slip','range_bias'):
                bounds={'imu_gap':[18,22],'velocity_slip':[15,35],'range_bias':[12,35]}[scene];ax.axvspan(*bounds,color='gray',alpha=.18)
        axes[0].legend(ncol=4);axes[2].legend();axes[-1].set_xlabel('state time - synthetic origin(s); availability is +1s + compute/queue');fig.suptitle(scene+' seed31, no result-based seed selection');fig.tight_layout();fig.savefig(out/(scene+'_timeseries.png'),dpi=150);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,4))
    for scene in ['nominal','imu_gap']:
        v=[next(r for r in aggregates if r['scenario']==scene and r['arm']==arm)['estimate_valid_coverage_mean'] for arm in ARMS];axes[0].plot(range(4),v,'o-',label=scene)
        v=[next(r for r in aggregates if r['scenario']==scene and r['arm']==arm)['solver_failure_rate_mean'] for arm in ARMS];axes[1].plot(range(4),v,'o-',label=scene)
    times=[np.mean([float(r['mean_update_wall_s']) for r in rows if r['arm']==arm])*1000 for arm in ARMS];axes[2].bar(range(4),times,color=COLORS)
    for ax,label in zip(axes,['valid publications / all','failed solves / attempted solves','mean complete update(ms)']):ax.set_ylabel(label);ax.set_xticks(range(4),ARMS);ax.grid(axis='y',alpha=.3)
    axes[0].legend();fig.tight_layout();fig.savefig(out/'coverage_failure_compute.png',dpi=150);plt.close(fig)
    print(json.dumps(dict(status='DONE',artifacts=len(list(out.iterdir())))))


if __name__=='__main__':main()
