"""Render normal and collinear panels exclusively from verified table entries."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

p=argparse.ArgumentParser()
p.add_argument('table',type=Path)
p.add_argument('output',type=Path)
args=p.parse_args()
table=json.loads(args.table.read_text())
sample=table['ledger']=='fixtures'
fig,axes=plt.subplots(2,2,figsize=(8,7),layout='constrained')
for i,geometry in enumerate(('normal','collinear')):
    case=geometry if sample else geometry+'_b0_zero'
    row=next(r for r in table['rows'] if r['case']==case and r['arm']=='contracted' and r['inclusion']=='PASS' and r['mechanism']=='PASS')
    data=row['figure_data']
    for j,car in enumerate(('p','s')):
        ax=axes[i,j]
        def draw(box,**style):
            (l,r),(b,t)=[[float(Fraction(v)) for v in pair] for pair in box]
            ax.add_patch(Rectangle((l,b),r-l,t-b,**style))
        for box in data['projections'][car]:
            draw(box,facecolor='#97c9e2',edgecolor='none')
        draw(data['original'][2*j:2*j+2],fill=False,edgecolor='#333333',linestyle='--')
        draw(data['contracted'][2*j:2*j+2],fill=False,edgecolor='#a34b13',linewidth=1.5)
        if i:
            x,y=(0,(1,-1)[j]) if sample else ((-1,1),(2,1.5))[j]
            ax.scatter([x,x],[y,-y],marker='x',color='#7a2079')
        ax.autoscale()
        ax.set(aspect='equal',title=f'{geometry.capitalize()} · vehicle {car}',xlabel='x (m)',ylabel='y (m)')
fig.suptitle('Mechanism fixtures' if sample else 'Certified P4 pilot projections')
fig.supxlabel('Dashed: original domain    Orange: certified root    Blue: projection    ×: mirror witnesses',fontsize=9)
fig.savefig(args.output,dpi=175)
