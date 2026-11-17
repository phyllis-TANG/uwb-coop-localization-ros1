"""Deterministic illustration of saved closed-form bounds; no statistical samples."""
import argparse,csv
from pathlib import Path
from fractions import Fraction
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 with (a.results/'SENSITIVITY.csv').open() as f:rs=list(csv.DictReader(f))
 fig,ax=plt.subplots(1,2,figsize=(12,5))
 for d in ['0','1/10','1','5']:
  rr=[r for r in rs if r['d_m']==d];ax[0].plot([float(Fraction(r['rho_m'])) for r in rr],[float(Fraction(r['exact_scalar_width'])) for r in rr],'o-',label=f'd0={float(Fraction(d)):g} m')
 rr=[r for r in rs if r['d_m']=='0'];ax[0].plot([float(Fraction(r['rho_m'])) for r in rr],[float(Fraction(r['relaxed_width'])) for r in rr],'k--',label='symmetric relaxation')
 ax[0].set(xlabel='Reference ball radius rho [m]',ylabel='Biased scalar prediction width [m]',title='20 frozen closed-form rows; b in [-.6,.6] m');ax[0].legend(fontsize=8)
 ax[1].add_patch(Rectangle((-1,-1),2,2,facecolor='#f6bf60',alpha=.3,label='independent row envelope'))
 ax[1].plot([-1,1],[1,-1],color='#2166ac',lw=3,label='shared reference: e2=-e1');ax[1].plot([-1,1],[-1,1],'--',color='#992222',label='wrong single effective bias')
 ax[1].scatter([1,1],[-1,1],c=['#2166ac','#992222'],s=55);ax[1].annotate('feasible (1,-1)',(1,-1),xytext=(.05,-1.32));ax[1].annotate('box-only (1,1)',(1,1),xytext=(.15,1.15));ax[1].set(xlim=(-1.5,1.5),ylim=(-1.5,1.5),xlabel='Range shift e1 [m]',ylabel='Range shift e2 [m]',title='Shared geometry is not a shared scalar bias');ax[1].set_aspect('equal');ax[1].legend(loc='lower left',fontsize=7)
 fig.suptitle('Reference-position uncertainty: deterministic inclusion, not empirical coverage');fig.tight_layout();fig.savefig(a.out/'REFERENCE_CONTRACT.png',dpi=160);plt.close(fig)
