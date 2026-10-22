#!/usr/bin/env python3
"""Plot recorded published states and after-EOF estimates without truth interpolation."""
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path):
    with path.open() as stream:
        return list(csv.DictReader(stream))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads((args.results/'protocol.json').read_text())
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    colors = {'005135': '#1676ae', '004023': '#d45724'}
    for i, case in enumerate(protocol['cases']):
        rows = read_csv(args.results/case['id']/'published.csv')
        batch = read_csv(args.results/case['id']/'offline_batch.csv')
        t = np.array([float(r['state_time_s']) for r in rows])
        xy = np.array([[float(r['antenna_x_m']), float(r['antenna_y_m'])] for r in rows])
        odom = np.array([[float(r['aligned_odom_antenna_x_m']),
                          float(r['aligned_odom_antenna_y_m'])] for r in rows])
        after = np.array([[float(r['antenna_x_m']), float(r['antenna_y_m'])] for r in batch])
        ax = axes[0, i]
        ax.plot(odom[:, 0], odom[:, 1], '--', color='#888888', lw=1.4, label='Aligned Odom')
        ax.plot(after[:, 0], after[:, 1], color='#1676ae', lw=1.8, label='After-EOF batch')
        ax.plot(xy[:, 0], xy[:, 1], color='#d45724', lw=1.2, label='Published at each update')
        ax.scatter(*protocol['model']['start_antenna_xyz_m'][:2], marker='o',
                   s=42, color='black', label='External start input', zorder=5)
        ax.scatter(*case['end_antenna_xyz_m'][:2], marker='x', s=70,
                   color='#a51d3b', linewidth=2, label='Manual endpoint reference', zorder=5)
        ax.set_title(case['id']+' : '+case['role'])
        ax.set_xlabel('Room X [m]')
        ax.set_ylabel('Room Y [m]')
        ax.set_aspect('equal', adjustable='datalim')
        ax.grid(alpha=.2)
        if i == 0:
            ax.legend(fontsize=8, loc='best')
        color = colors[case['id']]
        axes[1, 0].plot(t, [1000*float(r['solve_wall_s']) for r in rows],
                        color=color, label=case['id'], lw=1.3)
        if len(after) != len(xy):
            raise ValueError('Plot requires identical frozen two-bag grids')
        axes[1, 1].plot(t, 100*np.linalg.norm(xy-after, axis=1), color=color,
                        label=case['id'], lw=1.3)
    axes[1, 0].axhline(1000, color='#555555', ls='--', lw=1, label='1 s update budget')
    axes[1, 0].set(title='Measured solver wall time on this machine',
                   xlabel='State time since first bag receipt [s]', ylabel='Solve time [ms]')
    axes[1, 1].set(title='Difference between estimates (not trajectory error)',
                   xlabel='State time since first bag receipt [s]', ylabel='Published vs after-EOF position [cm]')
    for ax in axes[1]:
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.suptitle('Single-car receipt-ordered reference replay', fontsize=14)
    fig.text(.5, .015,
             '1 Hz states, 1 s designed buffer; growing graph; conditional body reference; no continuous ground truth.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .96))
    fig.savefig(args.results/'replay_comparison.png', dpi=160)
    fig.savefig(args.results/'replay_comparison.svg')


if __name__ == '__main__':
    main()
