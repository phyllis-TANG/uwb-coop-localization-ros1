#!/usr/bin/env python3
"""Scientific figures for saved independent/joint two-car comparison results."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    args=parser.parse_args()
    summary=json.loads((args.results/'summary.json').read_text())
    protocol=json.loads((args.results/'protocol.json').read_text())
    with (args.results/'trajectories.csv').open(newline='') as stream:rows=list(csv.DictReader(stream))
    fig,axes=plt.subplots(2,3,figsize=(14,8),constrained_layout=True)
    for col,case in enumerate(summary['cases']):
        definition=protocol['cases'][col]
        for ci,(car,color) in enumerate([('car1','#1779ac'),('car2','#cc5b18')]):
            ax=axes[ci,col]
            for method,style in [('independent','--'),('joint','-')]:
                data=[r for r in rows if r['case']==case['case'] and r['configuration']=='per_car_walls' and r['car']==car and r['method']==method]
                ax.plot([float(r['antenna_x_m']) for r in data],[float(r['antenna_y_m']) for r in data],
                        style,color=color,lw=1.5,label=method)
            start=definition['start_antenna_xyz_m'][car]
            end=definition['evaluation_only']['end_antenna_xyz_m'][car]
            ax.scatter(*start[:2],c='black',s=25,label='Start prior',zorder=5)
            ax.scatter(*end[:2],c='#ad2436',marker='x',s=55,label='Manual end reference',zorder=5)
            ax.set(title=f"{case['case']} / {car}",xlabel='Antenna x (m)',ylabel='Antenna y (m)')
            ax.set_aspect('equal',adjustable='datalim');ax.grid(alpha=.2)
            if col==0 and ci==0:ax.legend(fontsize=8)
    fig.suptitle('Per-car wall correction: independent vs joint offline estimates\n'
                 'Car1 calibrated on a separate static bag; Car2 retains P1 correction; no continuous ground truth',fontsize=12)
    fig.savefig(args.results/'primary_trajectories.png',dpi=160)
    fig.savefig(args.results/'primary_trajectories.svg');plt.close(fig)
    names=['raw_walls','car2_p1_only','per_car_walls','peer_sigma_0p4','withhold_car1_walls',
           'withhold_car2_walls','peer_car2_minus_0p1s','peer_car2_plus_0p1s']
    labels=['Raw walls','Car2 P1 only','Per-car correction','Peer sigma 0.4 m',
            'Withhold Car1 walls','Withhold Car2 walls','Car2 peer bin -0.1 s','Car2 peer bin +0.1 s']
    fig,axes=plt.subplots(1,3,figsize=(15,5.5),constrained_layout=True,sharey=True)
    for ax,case in zip(axes,summary['cases']):
        for ci,(car,color) in enumerate([('car1','#1779ac'),('car2','#cc5b18')]):
            changes=[100*case['configurations'][name]['effect']['endpoint_difference_joint_minus_independent_m'][car]
                     for name in names]
            ax.barh(np.arange(len(names))+(ci-.5)*.32,changes,height=.3,color=color,label=car)
        ax.axvline(0,color='black',lw=1)
        ax.set(title=case['case'],xlabel='Joint minus independent endpoint difference (cm)',yticks=np.arange(len(names)),yticklabels=labels)
        ax.grid(axis='x',alpha=.2)
    axes[0].invert_yaxis();axes[0].legend()
    fig.suptitle('Signed endpoint comparison: left = smaller manual-reference difference\n'
                 'Wall withholding is synthetic missing data; configurations are not independent repetitions',fontsize=12)
    fig.savefig(args.results/'signed_endpoint_effects.png',dpi=160)
    fig.savefig(args.results/'signed_endpoint_effects.svg');plt.close(fig)


if __name__=='__main__':main()
