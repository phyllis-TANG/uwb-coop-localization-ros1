"""Reconstruct report values from immutable epoch and evaluation archives."""
import csv
import gzip
import json
from math import dist
from statistics import NormalDist

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from development import EVAL, OUT, ROOT, blob

ARCHIVE = '32730dd3c405503b5ccacbde1c2f4f26ae9546cb'
K = NormalDist().inv_cdf(1 - .005/2)


def extract(scene):
    name = OUT.relative_to(ROOT) / f'{scene}_survey_links.json.gz'
    epochs = json.loads(gzip.decompress(blob(ARCHIVE, name)))[:2]
    truth = json.loads(gzip.decompress(blob(EVAL,
        f'docs/research/ground_continuous_b/runs/101_{scene}/truth.json.gz')))
    output = []
    for i in range(2):
        levels, errors = [], []
        for e in epochs:
            car = e['cars'][i]
            radius = np.linalg.norm(np.array(car['history_B']) + K*np.sqrt(e['covariance_diag'][2*i:2*i+2]))
            assert e['action'] == 'ACCEPT'
            np.testing.assert_allclose(radius, car['hcpl']['history'], rtol=0, atol=1e-14)
            levels.append(100*radius)
            errors.append(100*dist(car['xy'], truth[20*e['t']][i]))
        a, b = epochs
        indices = [j for j in range(len(truth)) if a['ready'] <= j/20 < b['ready'] and j/20 <= a['expiry']]
        assert len(indices) == 20 and levels[0] <= 10 < levels[1]
        held = [100*dist(a['cars'][i]['xy'], truth[j][i]) for j in indices]
        times = np.array(indices)/20
        output.append((levels, errors, times, held))
    return output


def main():
    rows = extract('nominal')
    for normal, wall in zip(rows, extract('wall'), strict=True):
        for a,b in zip(normal,wall, strict=True):
            np.testing.assert_array_equal(a,b)
    fig, axes = plt.subplots(1,2,figsize=(9,3.8),sharey=True,layout='constrained')
    with (OUT/'first_second.csv').open('w') as table:
        writer = csv.writer(table, lineterminator='\n')
        writer.writerow(['car','state1_error_cm','state1_hcpl_cm','state2_error_cm','state2_hcpl_cm',
                         'first_tick_s','last_tick_s','held_ticks','max_held_error_cm','above_held_hcpl','above_al'])
        for i,(ax,(levels,errors,times,held)) in enumerate(zip(axes,rows,strict=True),1):
            writer.writerow([i,errors[0],levels[0],errors[1],levels[1],times[0],times[-1],len(times),
                             max(held),sum(np.array(held)>levels[0]),sum(np.array(held)>10)])
            ax.axhline(10,color='#993527',ls='--',label='Alert limit (10 cm)')
            ax.plot(times,held,'.-',color='#00786d',label='Error of held XY at vehicle tick')
            ax.scatter([1,2],levels,marker='D',color='#235591',label='HCPL at state time',zorder=4)
            ax.scatter([1,2],errors,marker='x',color='black',label='Error at state time',zorder=4)
            ax.hlines(levels[0],times[0],times[-1],color='#235591',linestyle=':',label='Held first-state HCPL')
            ax.set(title=f'Car {i}',xlabel='Time (s)',ylim=(0,16))
            ax.grid(axis='y',alpha=.2)
    axes[0].set_ylabel('Horizontal distance (cm)')
    fig.legend(*axes[0].get_legend_handles_labels(),loc='outside lower center',ncol=3,fontsize=8)
    fig.savefig(OUT/'first_second.png',dpi=200)
    plt.close(fig)


if __name__ == '__main__':
    main()
