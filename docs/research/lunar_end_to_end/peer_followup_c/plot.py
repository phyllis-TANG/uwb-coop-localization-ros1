"""Plot every same-seed/layout/mode pair using the certified endpoints."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
with (HERE/'results/rows.csv').open() as f:
    rows = list(csv.DictReader(f))
modes = ['anchor_only','peer_60','peer_15','peer_05']
layouts = ['original','equal_area_square']
colors = ['#aa492b','#18689a']
fig, axes = plt.subplots(2,2,figsize=(12,7.7),sharex=True,sharey=True)
for ax, (t,car) in zip(axes.flat, [(t,c) for t in (4,14) for c in ('Car1','Car2')]):
    for r in rows:
        if (int(r['t']),r['car'])!=(t,car):
            continue
        i = layouts.index(r['layout'])
        x = (int(r['seed'])-2026112311)*5+modes.index(r['mode'])+(i-.5)*.25
        lo,hi = float(r['lower_cm']),float(r['upper_cm'])
        ax.plot([x,x],[lo,hi],color=colors[i],lw=2)
        ax.plot([x,x],[lo,hi],'_',color=colors[i],ms=5)
    for y in (10,20):
        ax.axhline(y,color='0.42',lw=.9,ls='--',zorder=0)
    for x in (4,9):
        ax.axvline(x,color='0.88',lw=.8)
    d = next(float(r['true_peer_m']) for r in rows if int(r['t'])==t)
    ax.set_title(f'{car}    |    {t} s    |    separation {d:.3f} m',loc='left')
    ax.set_xticks([5*j+i for j in range(3) for i in range(4)],['A','60','15','5']*3)
    ax.tick_params(axis='x',labelbottom=True)
    ax.spines[['top','right']].set_visible(False)
for ax in axes[:,0]:
    ax.set_ylabel('Minimum covering radius (cm)')
for ax in axes[-1]:
    ax.set_xlabel('2026112311             2026112312             2026112313')
fig.legend([Line2D([],[],color=c,lw=3) for c in colors],['Original rectangle','Equal-area square'],
           ncol=2,loc='upper center',frameon=False)
fig.text(.5,.014,'Bars span certified lower to upper bounds. A = anchors only. 60 / 15 / 5 = allowed peer bias (±cm).',
         ha='center')
fig.tight_layout(rect=[0,.048,1,.945])
fig.savefig(HERE/'paired.png',dpi=160)
