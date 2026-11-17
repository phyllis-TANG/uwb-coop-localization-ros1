"""All-condition descriptive figures, no optimizer, no post-hoc case selection."""
import argparse,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(src,out):
 out.mkdir(parents=True,exist_ok=False)
 with src.open() as f:rs=list(csv.DictReader(f))
 for study in ['new','reuse']:
  fig,axs=plt.subplots(2,2,figsize=(12,8))
  for row,m in enumerate(['B0','B2']):
   for col,car in enumerate(['1','2']):
    ax=axs[row,col]
    for view,marker in [('endpoint_GN','o'),('endpoint_exact','x'),('truth_GN','+')]:
     data=[r for r in rs if r['study']==study and r['method']==m and r['car']==car and r['view']==view and r.get('prediction_error_rms_mean')]
     ax.scatter([float(r['actual_shift_rms_mean']) for r in data],[float(r['prediction_error_rms_mean']) for r in data],label=view,marker=marker,alpha=.75)
    ax.set(xscale='log',yscale='log',xlabel='Actual paired shift RMS (m)',ylabel='Prediction error RMS (m)',title=f'{m}, Car {car}, all conditions');ax.grid(alpha=.2);ax.legend(fontsize=8)
  fig.suptitle(f'{study}: center perturbation propagation (seed means)');fig.tight_layout();fig.savefig(out/f'{study}_propagation.png',dpi=170);plt.close(fig)
 data=[r for r in rs if r['study']=='reuse' and r['view']=='endpoint_GN'];fig,axs=plt.subplots(1,2,figsize=(14,6))
 for ax,car in zip(axs,['1','2']):
  ds=[r for r in data if r['car']==car];labels=[f"{r['geometry']} {r['sigma']} {r['method']}" for r in ds];x=np.arange(len(ds))
  ax.bar(x-.2,[float(r['base_mse_mean']) for r in ds],.4,label='fixed correct');ax.bar(x+.2,[float(r['target_mse_mean']) for r in ds],.4,label='fixed survey');ax.set_xticks(x,labels,rotation=80);ax.set_ylabel('MSE (m²), all finite estimates');ax.set_title(f'Car {car}');ax.legend()
 fig.tight_layout();fig.savefig(out/'reused_prior_mse.png',dpi=170);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.summary,a.out)
