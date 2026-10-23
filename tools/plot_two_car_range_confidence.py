#!/usr/bin/env python3
"""Scientific diagnostics and all confidence-strategy endpoint comparisons."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def read_csv(path):
    with path.open() as f: return list(csv.DictReader(f))


def save(fig, root, name):
    for ext in ['png', 'svg']: fig.savefig(root/(name+'.'+ext), dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('docs', type=Path)
    args = parser.parse_args(); docs = args.docs; output = docs/'results'
    plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none',
                         'axes.spines.top': False, 'axes.spines.right': False})
    ranges = read_csv(docs/'diagnostics/range_windows.csv')
    clocks = read_csv(docs/'diagnostics/clock_windows.csv')
    peers = read_csv(docs/'diagnostics/peer_windows.csv')
    fig, axes = plt.subplots(2, 2, figsize=(12.8, 8.2))
    for case, color in zip(['013206', '013951', '015009'], ['#2770a5', '#c26b24', '#268451']):
        rows = [r for r in ranges if r['bag'] == case and r['car'] == 'car2' and r['link'] == 'node_10']
        t = [float(r['center_s']) for r in rows]
        axes[0, 0].plot(t, [float(r['raw_median_m']) for r in rows], color=color, label=case)
        axes[0, 0].fill_between(t, [float(r['raw_p05_m']) for r in rows],
                                [float(r['raw_p95_m']) for r in rows], color=color, alpha=.12)
        axes[0, 1].plot(t, [100*float(r['corrected_minus_static_geometry_m']) for r in rows], color=color, label=case)
        p = [r for r in peers if r['bag'] == case and r['directional_difference_m']]
        axes[1, 0].plot([float(r['center_s']) for r in p],
                       [100*float(r['directional_difference_m']) for r in p], color=color, label=case)
        c = [r for r in clocks if r['bag'] == case and r['car'] == 'car2']
        axes[1, 1].plot([float(r['center_s']) for r in c],
                       [float(r['receipt_minus_header_median_ms']) for r in c], color=color, label=case)
    axes[0, 0].set_ylabel('Car2/node_10 raw range (m)')
    axes[0, 0].set_title('Stable within each recording; different levels across recordings')
    axes[0, 0].legend(); axes[0, 0].text(.02, .96, 'Shading: within-bin 5th-95th percentiles',
        transform=axes[0, 0].transAxes, va='top', fontsize=8)
    axes[0, 1].set_ylabel('Corrected range minus static geometry (cm)')
    axes[0, 1].axhline(0, color='black', linewidth=.8)
    axes[0, 1].set_title('Same recorded Car2 reference: [2, 2, 0.2] m')
    axes[1, 0].set_ylabel('Car1-to-Car2 minus reverse median (cm)')
    axes[1, 0].set_title('Reciprocal agreement alone does not establish accuracy')
    axes[1, 1].set_ylabel('Receipt minus header time (ms)')
    axes[1, 1].set_title('Clock offsets vary; recorded static Odom stays unchanged')
    for ax in axes.ravel(): ax.set_xlabel('Seconds since each bag start'); ax.grid(alpha=.2)
    fig.suptitle('Raw static evidence | the 92.5 cm difference lies between recorded sessions')
    fig.tight_layout(rect=(0, 0, 1, .95)); save(fig, output, 'static_node10_diagnosis')

    confidence = read_csv(output/'confidence.csv')
    fig, axes = plt.subplots(3, 2, figsize=(12.8, 9.2))
    for row, case in enumerate(['015334', '033248', '050447']):
        for col, factor in enumerate(['car2/node_10', 'peer']):
            ax = axes[row, col]
            values = [v for v in confidence if v['case'] == case and v['factor'] == factor]
            t = [float(v['elapsed_s']) for v in values]
            ax.plot(t, [float(v['signed_z']) if v['signed_z'] else np.nan for v in values],
                    color='#2770a5', label='Omitted-link consistency score')
            for y in [-2, 2]: ax.axhline(y, color='gray', linewidth=.7, linestyle='--')
            right = ax.twinx()
            right.plot(t, [float(v['weight']) for v in values], color='#c26b24', label='Applied weight')
            right.set_ylim(0, 1.08); right.set_ylabel('Weight', color='#c26b24')
            right.spines['right'].set_visible(True)
            ax.set_ylabel('Signed score z', color='#2770a5'); ax.set_title(case+' | '+factor)
            ax.grid(alpha=.2)
            if row == 2: ax.set_xlabel('Keyframe time (s)')
    fig.suptitle('Adaptive weights use the preceding three scores | predictions exclude the checked measurement')
    fig.text(.5, .01, 'Scores use approximate predictor covariance. A large score identifies disagreement, not the physical source of the error.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .035, 1, .95)); save(fig, output, 'confidence_timeline')

    summary = json.loads((output/'summary.json').read_text())
    fig, axes = plt.subplots(2, 3, figsize=(13.4, 7.7))
    for col, case in enumerate(summary['cases']):
        for row, suffix in enumerate(['', '_stationary']):
            ax = axes[row, col]
            for ci, car in enumerate(['car1', 'car2']):
                color = ['#2770a5', '#c26b24'][ci]
                for method in ['independent', 'joint']:
                    y = [100*case['configurations'][s+suffix][method]['endpoint_difference_m'][car]
                         for s in ['original', 'fixed', 'adaptive']]
                    ax.plot(range(3), y, marker='o', color=color,
                        linestyle='--' if method == 'independent' else '-',
                        markerfacecolor='white' if method == 'independent' else color,
                        label=car.capitalize()+' '+method)
            ax.set_xticks(range(3), ['Original', 'Fixed scale', 'Adaptive'])
            ax.set_ylim(bottom=0); ax.grid(axis='y', alpha=.2)
            ax.set_title(case['case']+' | near-zero Odom '+('off' if not suffix else 'on'))
            if col == 0: ax.set_ylabel('Difference from manual endpoint (cm)')
    axes[0, 2].legend(fontsize=8)
    fig.suptitle('Complete development comparison | adaptive endpoint changes are mostly small')
    fig.text(.5, .01, 'No endpoint tuning; no continuous ground truth or independent blind-test claim. Smaller fitted residual is not independent accuracy evidence.', ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .035, 1, .94)); save(fig, output, 'confidence_endpoint_comparison')


if __name__ == '__main__': main()
