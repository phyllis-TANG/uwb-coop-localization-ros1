#!/usr/bin/env python3
"""Scientific figures for the frozen three-bag covariance-policy ablation."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

CONFIGS = ['baseline', 'stationary_only', 'confidence_only', 'combined']
LABELS = ['Baseline', 'Near-zero\nOdom', 'Range\nconfidence', 'Both']
COLORS = ['#9e3b32', '#1c62a2', '#ac7b17', '#26784b']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results', type=Path)
    args = parser.parse_args(); root = args.results
    summary = json.loads((root/'summary.json').read_text())
    with (root/'trajectories.csv').open() as stream:
        records = list(csv.DictReader(stream))
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, 3, figsize=(13.8, 4.4))
    for axis, case in zip(axes, summary['cases']):
        for ci, car in enumerate(['car1', 'car2']):
            color = ['#1c62a2', '#be5a20'][ci]
            for method in ['independent', 'joint']:
                y = [100*case['configurations'][c][method]['endpoint_difference_m'][car] for c in CONFIGS]
                axis.plot(np.arange(4), y, color=color,
                    linestyle='--' if method == 'independent' else '-',
                    marker='o', markerfacecolor='white' if method == 'independent' else color,
                    label=f'{car.capitalize()} {method}')
        axis.set_title(case['case']+' | '+('Car1 static' if case['case'] == '015334' else
                        'Car2 static' if case['case'] == '033248' else 'Both moving'))
        axis.set_xticks(np.arange(4), LABELS); axis.set_ylim(bottom=0)
        axis.grid(axis='y', alpha=.22)
    axes[0].set_ylabel('Difference from manual endpoint (cm)')
    axes[2].legend(fontsize=8, loc='best')
    fig.suptitle('Full-bag offline development ablation | last-five median endpoint | lower is closer')
    fig.text(.5, .015, 'No continuous ground truth or quantified survey uncertainty; these are three known development bags.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, .93))
    for extension in ['png', 'svg']:
        fig.savefig(root/('endpoint_ablation.'+extension), dpi=170)
    plt.close(fig)

    fig, axes = plt.subplots(2, 2, figsize=(11.2, 8.2))
    references = {'015334': ('car1', np.array([1.5, 4.])),
                  '033248': ('car2', np.array([2.95, 3.04]))}
    for col, (caseid, (car, reference)) in enumerate(references.items()):
        case = next(c for c in summary['cases'] if c['case'] == caseid)
        for config, color in zip(CONFIGS, COLORS):
            rows = [r for r in records if r['case'] == caseid and r['car'] == car and
                    r['method'] == 'joint' and r['configuration'] == config]
            xy = np.asarray([[float(r['antenna_x_m']), float(r['antenna_y_m'])] for r in rows])
            t = [float(r['elapsed_s']) for r in rows]
            offset = 100*(xy-reference)
            path = 100*case['configurations'][config]['joint']['cars'][car]['estimated_antenna_path_m']
            label = f'{config}: path {path:.2f} cm'
            axes[0, col].plot(offset[:, 0], offset[:, 1], color=color, label=label, linewidth=1.4)
            axes[0, col].scatter(*offset[0], color=color, marker='o', s=20)
            axes[0, col].scatter(*offset[-1], color=color, marker='s', s=20)
            axes[1, col].plot(t, np.linalg.norm(xy-xy[0], axis=1)*100, color=color, label=config)
        axes[0, col].scatter(0, 0, marker='+', c='black', s=90, label='Manual fixed position')
        axes[0, col].set_title(caseid+' | '+car+' stationary | joint graph')
        axes[0, col].set_xlabel('X minus manual position (cm)')
        axes[0, col].set_ylabel('Y minus manual position (cm)')
        axes[0, col].set_aspect('equal', adjustable='datalim')
        axes[0, col].legend(fontsize=7.5, loc='best')
        axes[1, col].set_xlabel('Bag receipt time (s)')
        axes[1, col].set_ylabel('Distance from first estimate (cm)')
        for axis in axes[:, col]: axis.grid(alpha=.2)
    fig.suptitle('Stationary trajectory deformation falls; absolute position can remain shifted')
    fig.text(.5, .012, 'Top: circle = first estimate; square = last. Bottom: relative motion, not absolute positioning accuracy.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .04, 1, .95))
    for extension in ['png', 'svg']:
        fig.savefig(root/('stationary_deformation.'+extension), dpi=170)
    plt.close(fig)

    static = json.loads((root/'range_confidence.json').read_text())
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.5), sharey=True)
    for axis, car in zip(axes, ['car1', 'car2']):
        keys = sorted(static['scales']['wall_sigma_m'][car])
        for i, row in enumerate(static['training']+static['validation']):
            is_validation = i == len(static['training'])
            axis.plot(range(len(keys)), [100*row['wall_errors_m'][car][k] for k in keys],
                linestyle='--' if is_validation else '-', marker='*' if is_validation else 'o',
                label=row['id']+(' validation' if is_validation else ' training'), alpha=.85)
        axis.axhline(0, c='black', linewidth=.7)
        axis.set_xticks(range(len(keys)), keys); axis.set_title(car.capitalize())
        axis.grid(axis='y', alpha=.2)
    axes[0].set_ylabel('Corrected range median minus geometry (cm)')
    axes[1].legend(fontsize=8)
    fig.suptitle('Fixed correction does not transfer uniformly across static placements')
    fig.text(.5, .015, 'All PR38 range means unchanged. Confidence policy only changes scale; this plot cannot improve from reweighting.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, .94))
    for extension in ['png', 'svg']:
        fig.savefig(root/('static_range_transfer.'+extension), dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    main()
