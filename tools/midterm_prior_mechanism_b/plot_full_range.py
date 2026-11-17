"""Presentation-only replacement: retain every finite condition in scatter axes."""
import argparse,csv,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def plot(inp,out):
    if out.exists():raise FileExistsError(out)
    rows=list(csv.DictReader(inp.open()));fig,axes=plt.subplots(1,2,figsize=(11,5))
    for car,ax in enumerate(axes,1):
        vals=[]
        for m in ['B0','B1','B2','B3']:
            a=[r for r in rows if r['method']==m and r['model']=='truth_linearized'];pairs=[]
            for x in a:
                y=next(r for r in rows if r['method']==m and r['model']=='nonlinear' and r['id']==x['id'])
                if x[f'mse{car}'] and y[f'mse{car}']:pairs.append((float(x[f'mse{car}']),float(y[f'mse{car}'])))
            if pairs:
                p=np.array(pairs);vals.extend(p.ravel());ax.scatter(p[:,0],p[:,1],label=f'{m} ({len(p)} pairs)',alpha=.7)
        lo=10**math.floor(math.log10(min(x for x in vals if x>0)));hi=10**math.ceil(math.log10(max(vals)));ax.plot([lo,hi],[lo,hi],'k--',lw=.8);ax.set(xscale='log',yscale='log',xlim=(lo,hi),ylim=(lo,hi),xlabel='truth-linearized MSE (m2)',ylabel='nonlinear MSE (m2)',title=f'All finite paired conditions / Car{car}');ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(out,dpi=160);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();plot(a.input,a.out)
