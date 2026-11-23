"""Paired radius comparisons from checked exact squared bounds."""
import csv
import json
from fractions import Fraction
from pathlib import Path

import matplotlib.pyplot as plt

D=Path(__file__).resolve().parent/'results'
rows=list(csv.DictReader((D/'rows.csv').open()))
index={(r['seed'],r['t'],r['layout'],r['mode'],r['car']):r for r in rows}


def bounds(r):
    key='parallel_{seed}_{t}_{layout}_{mode}_{car}'.format(**r)
    c=json.loads((D/'certificates'/(key+'.json')).read_text())
    return Fraction(c['any_lower_squared']),Fraction(c['outer_squared'])


pairs=[]
for key,r in index.items():
    seed,t,layout,mode,car=key
    baselines=[]
    if layout=='equal_area_square':
        baselines.append(('layout',index[seed,t,'original',mode,car]))
    if mode!='anchor_only':
        baselines.append(('peer',index[seed,t,layout,'anchor_only',car]))
    for change,old in baselines:
        lo,hi=bounds(r)
        oldlo,oldhi=bounds(old)
        result='DECREASE' if hi<oldlo else 'INCREASE' if lo>oldhi else 'OVERLAP'
        pairs.append(dict(seed=seed,t=t,car=car,layout=layout,mode=mode,comparison=change,
                          result=result,old_lower_squared=str(oldlo),new_upper_squared=str(hi),
                          old_upper_squared=str(oldhi),new_lower_squared=str(lo)))
with (D/'radius_comparisons.csv').open('w') as stream:
    w=csv.DictWriter(stream,fieldnames=list(pairs[0]),lineterminator='\n')
    w.writeheader();w.writerows(pairs)

fig,axes=plt.subplots(2,2,sharex=True,sharey=True,figsize=(11,7),layout='constrained')
modes=['anchor_only','peer60','peer15','peer05']
colors=['#226b9b','#b15c22','#477a48']
for row,t in enumerate(('4','14')):
    for col,car in enumerate(('Car1','Car2')):
        ax=axes[row,col]
        for s,seed in enumerate(sorted({r['seed'] for r in rows})):
            for j,layout in enumerate(('original','equal_area_square')):
                for x,mode in enumerate(modes):
                    r=index[seed,t,layout,mode,car]
                    at=x+(s-1)*.23+(j-.5)*.086
                    l,u=float(r['lower_cm']),float(r['upper_cm'])
                    ax.vlines(at,l,u,colors=colors[s],linestyles=['solid','dashed'][j])
                    ax.scatter([at,at],[l,u],s=14,marker=['o','s'][j],color=colors[s],
                               label=f'{seed} · {["rectangle","square"][j]}' if x==0 else None)
        ax.axhline(20,ls=':',color='grey');ax.axhline(10,ls=':',color='grey')
        ax.set(title=f'{car} · {t} s',xticks=range(4),xticklabels=['Anchors','±60 cm','±15 cm','±5 cm'])
        if col==0:ax.set_ylabel('Certified radius bracket (cm)')
fig.legend(*axes[0,0].get_legend_handles_labels(),loc='outside lower center',ncol=3,fontsize=9)
fig.savefig(D/'paired.png',dpi=160)
