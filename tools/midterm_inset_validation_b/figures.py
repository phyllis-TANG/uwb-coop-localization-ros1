"""Full predeclared center grid, paired linear/nonlinear comparisons."""
import argparse,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(src,out):
 out.mkdir(parents=True,exist_ok=False)
 with src.open() as f:rs=list(csv.DictReader(f))
 for geometry in ['good','weak']:
  for sigma in [.5,.05]:
   fig,axes=plt.subplots(2,3,figsize=(14,8))
   for car in [1,2]:
    for col,rho in enumerate([0,.01,.05]):
     ax=axes[car-1,col];kind='noise_circle' if rho==0 else 'combined_circle'
     for model,view,style in [('NL','GN','o-'),('NL','exact','s-'),('LINEAR','GN','^-'),('LINEAR','exact','x:')]:
      rows=sorted([r for r in rs if r['geometry']==geometry and float(r['sigma'])==sigma and r['subset']=='all' and r['model']==model and r['view']==view and r['car']==str(car) and r['kind']==kind and float(r['rho'])==rho],key=lambda r:float(r['delta']))
      ax.plot([float(r['delta']) for r in rows],[float(r['coverage_available']) if r['coverage_available'] else float('nan') for r in rows],style,label=model+' '+view)
     ax.axhline(.95,color='black',ls='--',lw=.7);ax.set(ylim=(-.02,1.02),xlabel='Car1 Y prior offset (m)',ylabel='Available-point coverage',title=f'Car{car}, rho={rho}');ax.grid(alpha=.2);ax.legend(fontsize=7)
   fig.suptitle(f'{geometry}, prior sigma={sigma}; linear weak t0 unavailable, see denominators');fig.tight_layout();fig.savefig(out/f'{geometry}_{sigma}_coverage.png',dpi=150);plt.close(fig)
 for metric in ['radius_mean','rmse_from_mean_mse']:
  fig,axes=plt.subplots(2,2,figsize=(12,8))
  for row,g in enumerate(['good','weak']):
   for col,car in enumerate([1,2]):
    ax=axes[row,col]
    for model in ['NL','LINEAR']:
     for sigma in [.5,.05]:
      data=sorted([r for r in rs if r['geometry']==g and r['car']==str(car) and r['model']==model and r['view']=='GN' and r['kind']=='combined_circle' and float(r['rho'])==.05 and float(r['sigma'])==sigma and r['subset']=='all'],key=lambda r:float(r['delta']))
      ax.plot([float(r['delta']) for r in data],[float(r[metric]) for r in data],'o-',label=f'{model} sigma={sigma}')
    ax.set(xlabel='Car1 Y prior offset (m)',ylabel=metric+' (m)',title=f'{g} Car{car}');ax.legend(fontsize=7);ax.grid(alpha=.2)
  fig.tight_layout();fig.savefig(out/f'{metric}.png',dpi=150);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.summary,a.out)
