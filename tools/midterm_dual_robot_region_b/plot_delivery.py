"""Post-freeze static presentation; all fixed first-case output rectangles shown."""
import argparse,csv
from fractions import Fraction as F
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle
from common import read

def plots(results,analysis,out):
 out.mkdir(parents=True,exist_ok=True)
 for case in ['normal_b0_zero','near_collinear_b0_zero','collinear_b0_zero','forced_budget']:
  fig,axes=plt.subplots(2,3,figsize=(13,8),constrained_layout=True)
  for j,method in enumerate(['J5','P4','N4']):
   path=results/'deterministic'/(case+'_'+method+'.result.json.gz')
   if not path.exists():
    for i in (0,1):axes[i,j].text(.5,.5,'Not in authorized plan',ha='center',transform=axes[i,j].transAxes);axes[i,j].set_axis_off()
    continue
   r=read(path)
   if r.get('status')!='COMPLETED':
    for i in (0,1):axes[i,j].set_title(method+' incomplete')
    continue
   for i,car in enumerate(['p','s']):
    ax=axes[i,j];z=r['projections'][car];patches=[]
    for b in z['rectangles']:
     (xl,xu),(yl,yu)=[[float(F(v)) for v in a] for a in b];patches.append(Rectangle((xl,yl),xu-xl,yu-yl))
    ax.add_collection(PatchCollection(patches,facecolor='#56a6cd',edgecolor='none',alpha=.65,rasterized=True))
    pp=[]
    for b in z['inside_rectangles']:
     (xl,xu),(yl,yu)=[[float(F(v)) for v in a] for a in b];pp.append(Rectangle((xl,yl),xu-xl,yu-yl))
    ax.add_collection(PatchCollection(pp,facecolor='#18794e',edgecolor='none',alpha=.7,rasterized=True))
    p=r['case']['evaluation']['truth'][i*2:i*2+2];ax.plot(*[float(F(v)) for v in p],marker='x',color='black',ms=7)
    if z['hull']:
     hh=[[float(F(v)) for v in a] for a in z['hull']];wx=max(hh[0][1]-hh[0][0],.1);wy=max(hh[1][1]-hh[1][0],.1);ax.set_xlim(hh[0][0]-.1*wx,hh[0][1]+.1*wx);ax.set_ylim(hh[1][0]-.1*wy,hh[1][1]+.1*wy)
    ax.set_aspect('equal',adjustable='box');ax.set_xlabel('x [m]');ax.set_ylabel('y [m]');ax.set_title(f'{method} / robot {car}\n'+r['result']['termination']);ax.grid(alpha=.2)
  fig.suptitle(case+' | blue: full outer projection; green: certified inner; black x: evaluation truth');fig.savefig(out/(case+'.png'),dpi=160);plt.close(fig)
 rows=list(csv.DictReader((analysis/'RUNS.csv').open()));rs=[r for r in rows if r['stage']=='deterministic' and r['status']=='COMPLETED']
 ids=list(dict.fromkeys(r['case'] for r in rs));fig,axes=plt.subplots(2,1,figsize=(14,8),constrained_layout=True)
 for method,color in [('J5','#9459b0'),('P4','#007f8b'),('N4','#d78b00')]:
  vals={r['case']:r for r in rs if r['method']==method};x=[i for i,c in enumerate(ids) if c in vals];axes[0].plot(x,[float(vals[ids[i]]['wall_seconds']) for i in x],'.-',label=method,color=color);axes[1].plot(x,[int(vals[ids[i]]['processed']) for i in x],'.-',label=method,color=color)
 axes[0].axhline(2,color='black',ls='--',lw=1,label='2 s median gate reference');axes[0].set_ylabel('Full method cost [s]');axes[1].set_ylabel('Processed boxes');axes[1].set_xticks(range(len(ids)),ids,rotation=65,ha='right');axes[0].legend(ncol=4);axes[1].legend()
 for ax in axes:ax.grid(alpha=.2)
 fig.savefig(out/'COST_AND_BOXES.png',dpi=160);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();plots(a.results,a.analysis,a.out)
