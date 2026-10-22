#!/usr/bin/env python3
"""Plot frozen fixed-lag replay results, without recomputing localization."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ARMS = ('legacy_cold_full_history', 'analytic_warm_full_history', 'analytic_warm_fixed_20s')
LABELS = ('Full history / cold', 'Full history / warm + analytic', '20 s lag / warm + analytic')
COLORS = ('#777777', '#1275ae', '#d05b15')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    args = parser.parse_args()
    protocol = json.loads((args.results/'protocol.json').read_text())
    fig, axes = plt.subplots(3, 2, figsize=(12, 11), constrained_layout=True)
    for col, case in enumerate(protocol['cases']):
        all_rows = [json.loads((args.results/case['id']/arm/'updates.json').read_text()) for arm in ARMS]
        for arm_index, (rows, label, color) in enumerate(zip(all_rows, LABELS, COLORS)):
            rows = [r for r in rows if r['pose'] is not None]
            t = np.array([r['state_time_s'] for r in rows])
            xy = np.array([r['antenna_xy_m'] for r in rows])
            axes[0, col].plot(xy[:, 0], xy[:, 1], color=color, label=label, lw=1.5, alpha=.9)
            solved = [r for r in rows if r['graph_states'] >= 3]
            axes[1, col].plot([r['state_time_s'] for r in solved],
                [1000*r['update_wall_s'] for r in solved], color=color, label=label, lw=1.3)
            accepted = [r for r in rows if r['accepted_graph']][1:]
            axes[2, col].plot([r['state_time_s'] for r in accepted],
                [100*r['position_correction_m'] for r in accepted], color=color, label=label, lw=1.3)
            if arm_index == 0:
                odom = np.array([r['aligned_odom_antenna_xy_m'] for r in rows])
                axes[0, col].plot(odom[:, 0], odom[:, 1], '--', color='#8e71ad', lw=1.1, label='Aligned Odom')
        start, end = protocol['model']['start_antenna_xyz_m'], case['end_antenna_xyz_m']
        axes[0, col].scatter(*start[:2], c='black', marker='o', s=35, label='Start input', zorder=5)
        axes[0, col].scatter(*end[:2], c='#b72a38', marker='x', s=65, label='Manual end reference', zorder=5)
        axes[0, col].set(title=f"{case['id']}: {case['role']}", xlabel='Antenna x (m)', ylabel='Antenna y (m)')
        axes[0, col].set_aspect('equal', adjustable='datalim')
        axes[1, col].axhline(1000, ls='--', color='#b72a38', lw=1, label='1 s update period')
        axes[1, col].set(yscale='log', xlabel='State time (s)', ylabel='Complete update (ms)')
        axes[2, col].set(xlabel='State time (s)', ylabel='Odom-propagated correction (cm)')
        for row in range(3):
            axes[row, col].grid(alpha=.2)
    axes[0, 0].legend(fontsize=8, loc='best')
    axes[1, 0].legend(fontsize=8, loc='upper left')
    axes[2, 0].legend(fontsize=8, loc='upper right')
    fig.suptitle('Receipt-ordered Odom + UWB replay: fixed 20 s lag\n'
                 'Frozen weights and endpoint windows; no independent IMU factors or continuous ground truth', fontsize=13)
    fig.savefig(args.results/'fixed_lag_comparison.png', dpi=160)
    fig.savefig(args.results/'fixed_lag_comparison.svg')
    plt.close(fig)


if __name__ == '__main__':
    main()
