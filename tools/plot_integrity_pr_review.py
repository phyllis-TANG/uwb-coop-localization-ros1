#!/usr/bin/env python3
"""Read archived nominal CSV only; no estimator, generator or threshold selection."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--experiment',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.experiment.resolve();destination=args.output.resolve()
    destination.mkdir(parents=True,exist_ok=False)
    inputs={};evidence=[]
    for seed in [1001,1002,1003]:
        path=out/'results_reviewed/evaluated_runs'/('test_nominal_'+str(seed))/'timeseries.csv'
        inputs[str(path.relative_to(out))]=hashlib.sha256(path.read_bytes()).hexdigest()
        rows=list(csv.DictReader(path.open()))
        groups={m:[r for r in rows if r['method']==m] for m in ['M1','M2']}
        for a,b in zip(groups['M1'],groups['M2']):
            assert (a['state_time_s'],a['state_interval_end_s'],a['monitor_available'])==(b['state_time_s'],b['state_interval_end_s'],b['monitor_available'])
        for method,data in groups.items():
            available=[r for r in data if r['monitor_available']=='True']
            unavailable=[r for r in data if r['monitor_available']!='True']
            alarm=[r for r in data if r['alarm']=='True']
            duration=lambda records:sum(float(r['state_interval_end_s'])-float(r['state_time_s']) for r in records)
            evidence.append(dict(seed=seed,method=method,published_evaluation_s=duration(data),monitorable_evaluation_s=duration(available),unmonitorable_s=duration(unavailable),alarm_state_time_s=duration(alarm),alarm_states=len(alarm)))
        if seed==1001:
            target=groups['M2']
    t=[float(r['state_time_s']) for r in target];error=[float(r['error_m']) for r in target]
    statistic=[float(r['statistic']) for r in target];threshold=float(target[0]['threshold'])
    alarm=[r for r in target if r['alarm']=='True']
    assert [float(r['state_time_s']) for r in alarm]==list(range(4,17))
    assert sum(r['alarm_state_time_s'] for r in evidence if r['method']=='M2')==13
    assert sum(r['monitorable_evaluation_s'] for r in evidence if r['method']=='M2')==261
    fig,axes=plt.subplots(2,1,figsize=(10,6.5),sharex=True)
    for ax in axes:
        ax.axvspan(0,10,color='#8bb6d1',alpha=.17,label='Physical stationary [0,10)')
        ax.axvspan(10,21,color='#8ebd95',alpha=.17,label='Straight motion from t=10')
        ax.axvspan(1,3,color='#777777',alpha=.18,label='Monitor unavailable [1,3)')
        ax.axvspan(4,17,facecolor='none',edgecolor='#b52d3c',hatch='//',linewidth=1.3,label='M2 alarm on state axis [4,17)')
        ax.axvline(3,color='#555555',ls=':',lw=1)
        ax.set_xlim(0,21);ax.grid(alpha=.2)
    axes[0].plot(t,error,color='#146a9c',lw=1.7,label='Then-published antenna XY error')
    axes[0].axhline(.2,color='#c16b13',ls='--',label='Exploratory 0.20m error limit')
    axes[0].set(ylabel='Position error at state time [m]',ylim=(0,.43),title='Nominal seed 1001: one early M2 alarm event, not 13 independent failures')
    axes[0].legend(fontsize=7.5,ncol=2,loc='upper right')
    axes[1].plot(t,statistic,color='#864d9e',lw=1.7,label='M2 maximum independent-exclusion separation')
    axes[1].axhline(threshold,color='#222222',ls='--',label='Frozen threshold = 0.062191200771m')
    axes[1].scatter([float(r['state_time_s']) for r in alarm],[float(r['statistic']) for r in alarm],marker='x',color='#c3263a',label='Alarm states t=4,...,16',zorder=4)
    axes[1].set(xlabel='State measurement time [s]; first accepted graph at t=3',ylabel='M2 statistic / threshold [m]')
    axes[1].legend(fontsize=8,loc='upper right')
    fig.text(.1,.01,'State alarm [4,17) -> modeled availability [5.028213,18.027609)s. Initialization is a hypothesis, not an established cause.',fontsize=8)
    fig.tight_layout(rect=(0,.035,1,1))
    fig.savefig(destination/'nominal_1001_initial_alarm.png',dpi=180)
    fig.savefig(destination/'nominal_1001_initial_alarm.svg')
    plt.close(fig)
    with (destination/'nominal_monitoring_exposure.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(evidence[0]));writer.writeheader();writer.writerows(evidence)
    data=dict(input_sha256=inputs,threshold=threshold,rows=evidence,
        nominal_run_count=3,simulated_duration_s=270,published_state_evaluation_s=267,
        common_M1_M2_monitorable_evaluation_s=261,M1_unmonitorable_s=6,M2_unmonitorable_s=6,
        M2_alarm_state_time_s=13,M2_alarm_time_occupancy=13/261,
        M2_alarm_event_count=1,M2_runs_with_any_alarm=1,
        alarm_state_interval_s=[4,17],stationary_overlap_s=6,straight_motion_overlap_s=7,
        alarm_error_min_m=min(float(r['error_m']) for r in alarm),alarm_error_max_m=max(float(r['error_m']) for r in alarm),
        modeled_alarm_availability_interval_s=[float(alarm[0]['result_available_receipt_s']),float(next(r['result_available_receipt_s'] for r in target if float(r['state_time_s'])==17))],
        note='Read-only archival summarization/plot; no new estimator run, no threshold change; 13/261 is descriptive time occupancy, not a long-term probability.')
    (destination/'review_evidence.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))


if __name__=='__main__':main()
