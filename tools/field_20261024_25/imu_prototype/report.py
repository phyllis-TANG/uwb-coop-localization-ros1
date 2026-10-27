#!/usr/bin/env python3
"""Synthetic development summary/figures; never used to choose parameters."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from configuration import MODES
from io_utils import dump,read_jsonl,sha
from evaluate import csv_write

COLORS=['#777777','#0072b2','#d55e00','#009e73']


def read_csv(path):
    with Path(path).open() as stream: return list(csv.DictReader(stream))


def main():
    p=argparse.ArgumentParser(); p.add_argument('--experiment',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    root=a.experiment; out=a.output; out.mkdir(parents=True,exist_ok=False)
    state=json.loads((root/'checkpoint.json').read_text()); rows=read_csv(root/'metrics.csv'); scenes=json.loads((root/'protocol.json').read_text())['scenarios']
    groups=defaultdict(list)
    for r in rows: groups[(r['scenario'],r['motion_mode'],r['method'],r['vehicle_id'])].append(r)
    aggregates=[]
    for (scene,mode,method,car),values in groups.items():
        result=dict(scenario=scene,motion_mode=mode,method=method,vehicle_id=car,independent_seeds=len(values))
        for k in ['xy_rmse_state_m','xy_max_state_m','yaw_rmse_rad','bias_rmse_rad_s','valid_duration_s','invalid_duration_s','retained_gap_flag_duration_s','xy_rmse_recovery_34_40_m']:
            v=[float(r[k]) for r in values if r[k]]; result[k+'_mean']=float(np.mean(v)) if v else None
        aggregates.append(result)
    csv_write(out/'aggregate.csv',aggregates)
    paired=[]; index={(r['scenario'],r['seed'],r['motion_mode'],r['method'],r['vehicle_id']):r for r in rows}
    for r in rows:
        if r['motion_mode']!='body_imu_bias': continue
        for mode in ['legacy_odom_pose','body_odom_rate','body_imu_fixed_bias']:
            previous=index[(r['scenario'],r['seed'],mode,r['method'],r['vehicle_id'])]
            delta=float(r['xy_rmse_state_m'])-float(previous['xy_rmse_state_m'])
            paired.append(dict(scenario=r['scenario'],seed=r['seed'],method=r['method'],vehicle_id=r['vehicle_id'],reference_mode=mode,delta_xy_rmse_m=delta,estimated_bias_worse=int(delta>0)))
    csv_write(out/'paired_differences.csv',paired)
    dump(out/'summary.json',dict(status=state['status'],cli_runs=len(state['cells']),method_trials=2*len(state['cells']),vehicle_metric_rows=len(rows),
        completed=sum(c['status']=='DONE' for c in state['cells']),failed=sum(c['status']!='DONE' for c in state['cells']),
        elapsed_batch_s=state['elapsed_s'],protocol_sha256=sha(root/'protocol.json'),
        worse_counts_vs_reference={m:dict(worse=sum(p['estimated_bias_worse'] for p in paired if p['reference_mode']==m),total=sum(p['reference_mode']==m for p in paired)) for m in ['legacy_odom_pose','body_odom_rate','body_imu_fixed_bias']},
        limitations=['all seeds are development, not blind validation','40s per input, correlated frames are not repeated trials','generator draws do not establish real gyro/velocity independence','CLI runtime includes both fusion engines and evidence serialization, not per-method latency']))
    # Per-car/fusion scene aggregates, with three-seed spread rather than standard-error claims.
    fig,axes=plt.subplots(2,2,figsize=(15,9),sharex=True)
    for ax,(car,method) in zip(axes.flat,[(c,m) for c in ['car1','car2'] for m in ['independent','joint']]):
        for color,mode in zip(COLORS,MODES):
            means=[]; lows=[]; highs=[]
            for scene in scenes:
                values=[float(r['xy_rmse_state_m']) for r in groups[(scene,mode,method,car)]]; means.append(np.mean(values)); lows.append(np.min(values)); highs.append(np.max(values))
            ax.plot(range(len(scenes)),means,'.-',label=mode,color=color); ax.fill_between(range(len(scenes)),lows,highs,alpha=.1,color=color)
        ax.set_title(car+' '+method); ax.set_ylabel('XY RMSE at state time (m)'); ax.grid(alpha=.3); ax.set_xticks(range(len(scenes)),scenes,rotation=60,ha='right')
    axes[0,0].legend(fontsize=8); fig.suptitle('Synthetic development, three seeds: mean and full seed range'); fig.tight_layout(); fig.savefig(out/'scene_errors.png',dpi=140); plt.close(fig)
    # Fixed representative seed is protocol's first, not cherry picked.
    seed=31; scene='gyro_constant_bias'; fig,axes=plt.subplots(1,2,figsize=(11,5))
    truth=list(read_jsonl(root/'inputs'/f'{scene}_seed{seed}'/'truth.jsonl.gz'))
    for ax,car in zip(axes,['car1','car2']):
        xy=np.array([t['vehicles'][car]['pose'][:2] for t in truth]); ax.plot(xy[:,0],xy[:,1],'k--',label='truth')
        for color,mode in zip(COLORS,MODES):
            values=[r for r in read_csv(root/'runs'/f'{scene}_seed{seed}__{mode}'/'synthetic_timeseries.csv') if r['method']=='joint' and r['vehicle_id']==car]
            ax.plot([float(v['x_m']) for v in values],[float(v['y_m']) for v in values],color=color,label=mode)
        ax.set_title(car+' joint, constant gyro bias, seed31'); ax.set_xlabel('x(m)'); ax.set_ylabel('y(m)'); ax.axis('equal'); ax.legend(fontsize=7); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out/'trajectory.png',dpi=140); plt.close(fig)
    for scene in ['gyro_constant_bias','velocity_slip','imu_dropout','stationary_unobservable','gyro_axis_mismatch']:
        fig,axes=plt.subplots(3,2,figsize=(12,9),sharex=True)
        for col,car in enumerate(['car1','car2']):
            for color,mode in zip(COLORS,MODES):
                values=[r for r in read_csv(root/'runs'/f'{scene}_seed{seed}__{mode}'/'synthetic_timeseries.csv') if r['method']=='joint' and r['vehicle_id']==car]
                t=[float(v['t_s']) for v in values]
                for ax,key in [(axes[0,col],'xy_error_at_state_m'),(axes[1,col],'yaw_error_rad')]: ax.plot(t,[float(v[key]) for v in values],color=color,label=mode)
                biases=[(float(v['t_s']),float(v['gyro_bias_rad_s'])) for v in values if v['gyro_bias_rad_s']]
                if biases: axes[2,col].plot(*zip(*biases),color=color,label=mode)
                if mode=='body_imu_bias':
                    axes[2,col].plot(t,[float(v['truth_bias_rad_s']) for v in values],'k--',label='true residual bias')
                    invalid=np.array([not int(v['valid']) for v in values]); axes[0,col].fill_between(t,0,1,where=invalid,transform=axes[0,col].get_xaxis_transform(),color='red',alpha=.1,label='invalid control/state')
            for i,label in enumerate(['XY error at state time(m)','wrapped yaw error(rad)','residual gyro bias(rad/s)']):
                axes[i,col].set_ylabel(label); axes[i,col].grid(alpha=.3)
                if scene=='imu_dropout' and car=='car1': axes[i,col].axvspan(14,17,color='gray',alpha=.2)
                if scene=='velocity_slip' and car=='car1': axes[i,col].axvspan(10,24,color='gray',alpha=.2)
            axes[0,col].set_title(car); axes[2,col].set_xlabel('publication cutoff - truth origin(s)'); axes[2,col].legend(fontsize=7)
        axes[0,0].legend(fontsize=7); fig.suptitle(scene+', fixed peer joint, seed31; shading: injected gap/slip, red: unavailable'); fig.tight_layout(); fig.savefig(out/(scene+'_timeseries.png'),dpi=140); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4))
    for car in ['car1','car2']:
        values=[next(v for v in aggregates if v['scenario']=='nominal' and v['method']=='joint' and v['vehicle_id']==car and v['motion_mode']==mode)['invalid_duration_s_mean'] for mode in MODES]
        axes[0].plot(range(4),values,'o-',label=car)
    axes[0].set_ylabel('nominal unavailable(s) /40s'); axes[0].legend()
    times=[np.mean([c['elapsed_s'] for c in state['cells'] if c['motion_mode']==m]) for m in MODES]
    axes[1].bar(range(4),times,color=COLORS); axes[1].set_ylabel('wall seconds /CLI (both methods + serialization)')
    for ax in axes: ax.set_xticks(range(4),MODES,rotation=30,ha='right'); ax.grid(axis='y',alpha=.3)
    fig.tight_layout(); fig.savefig(out/'availability_compute.png',dpi=140); plt.close(fig)
    print(json.dumps(dict(status='DONE',artifacts=len(list(out.iterdir())))))


if __name__=='__main__': main()
