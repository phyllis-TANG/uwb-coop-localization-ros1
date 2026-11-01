"""Three fixed descriptive figures; whole-run seed uncertainty only."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from support import lines

COLORS=dict(M2='#666666',M3='#c65319',M3W025='#16854e')


def rows(path):
    with path.open(newline='') as f:return list(csv.DictReader(f))


def plot(analysis, output):
    analysis,output=Path(analysis),Path(output);output.mkdir(parents=True,exist_ok=False)
    table=rows(analysis/'RUN_LEVEL_INTERVALS.csv');frames=list(lines(analysis/'FRAMES.jsonl.gz'))
    seed=min(r['seed'] for r in frames)
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
    labels=['nominal','car1_wall_14','car2_wall_14']
    for mi,motion in enumerate(('static_moving','both_moving')):
        for ci,car in enumerate(('car1','car2')):
            ax=axes[mi,ci]
            for j,method in enumerate(('M3','M3W025')):
                selected=[next(r for r in table if r['motion']==motion and r['condition']==c and r['car']==car and r['method']==method and r['phase']=='all' and r['metric']=='delta_mse_vs_M2_m2') for c in labels]
                y=[float(r['mean']) for r in selected];lo=[float(r['lo95']) for r in selected];hi=[float(r['hi95']) for r in selected]
                x=[k+(j-.5)*.15 for k in range(3)]
                ax.errorbar(x,y,yerr=[[a-b for a,b in zip(y,lo)],[b-a for a,b in zip(y,hi)]],fmt='o',capsize=4,color=COLORS[method],label=method)
            ax.axhline(0,color='black',linewidth=.7);ax.grid(alpha=.2);ax.set_title(motion+' / '+car)
            ax.set_xticks(range(3),['normal','Car1 wall bias','Car2 wall bias']);ax.set_ylabel('Paired MSE change vs M2 [m²]')
    axes[0,0].legend();fig.suptitle('Whole-run paired means and 95% t intervals across four seeds')
    fig.tight_layout();fig.savefig(output/'paired_mse.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(3,2,figsize=(11,9),sharex=True)
    subset=[r for r in frames if r['seed']==seed and r['motion']=='static_moving' and r['condition']=='car1_wall_14']
    for ci,car in enumerate(('car1','car2')):
        for method in ('M2','M3','M3W025'):
            rs=[r for r in subset if r['car']==car and r['method']==method and r['squared_error_m2'] is not None]
            axes[0,ci].plot([r['time_s'] for r in rs],[r['squared_error_m2']**.5 for r in rs],color=COLORS[method],label=method)
            axes[2,ci].plot([r['time_s'] for r in rs],[r['paired_nominal_displacement_m'] for r in rs],color=COLORS[method])
        fault=[r for r in subset if r['car']==car and r['method']=='M3' and r['four_wall_statistic'] is not None]
        normal=[r for r in frames if r['seed']==seed and r['motion']=='static_moving' and r['condition']=='nominal' and r['car']==car and r['method']=='M3' and r['four_wall_statistic'] is not None]
        axes[1,ci].plot([r['time_s'] for r in fault],[r['four_wall_statistic'] for r in fault],label='fault input',color='#9641a1')
        axes[1,ci].plot([r['time_s'] for r in normal],[r['four_wall_statistic'] for r in normal],label='paired normal',color='#2565ac',linestyle='--')
        axes[2,ci].axhline(.02,color='black',linestyle=':',label='recovery displacement criterion')
        for ax in axes[:,ci]:
            ax.axvspan(24,38,color='orange',alpha=.10);ax.axvline(59,color='black',linestyle='--',linewidth=.7);ax.grid(alpha=.2)
        axes[0,ci].set_title(car);axes[0,ci].set_ylabel('Antenna XY error [m]')
        axes[1,ci].set_ylabel('Raw four-wall fit statistic')
        axes[2,ci].set_ylabel('Distance to paired normal [m]');axes[2,ci].set_xlabel('State time [s]')
    axes[0,0].legend();axes[1,0].legend();fig.suptitle(f'Fixed first test seed {seed}: Car1 wall fault; dashed line = active-factor exit')
    fig.tight_layout();fig.savefig(output/'first_seed_trace.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
    for mi,motion in enumerate(('static_moving','both_moving')):
        for ci,condition in enumerate(('car1_wall_14','car2_wall_14')):
            car='car2' if condition.startswith('car1') else 'car1';ax=axes[mi,ci]
            for method in ('M2','M3','M3W025'):
                rs=[r for r in frames if r['seed']==seed and r['motion']==motion and r['condition']==condition and r['car']==car and r['method']==method and r['paired_nominal_displacement_m'] is not None]
                ax.plot([r['time_s'] for r in rs],[r['paired_nominal_displacement_m'] for r in rs],color=COLORS[method],label=method)
            ax.axhline(.02,color='black',linestyle=':');ax.axvspan(24,38,color='orange',alpha=.1);ax.axvline(59,color='black',linestyle='--',linewidth=.7)
            ax.set_title(motion+' / '+condition+' / partner '+car);ax.set_ylabel('Distance to paired normal [m]');ax.grid(alpha=.2);ax.set_xlabel('State time [s]')
    axes[0,0].legend();fig.suptitle('Partner propagation and recovery, fixed first test seed; local raw statistic unchanged')
    fig.tight_layout();fig.savefig(output/'partner_propagation.png',dpi=180);plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analysis',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();plot(a.analysis,a.output)
