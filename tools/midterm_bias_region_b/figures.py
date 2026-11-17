"""Coverage-size display for every existing correct/survey condition; fixed region choices."""
import argparse,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(src,out):
 out.mkdir(parents=True,exist_ok=False)
 with src.open() as f:rows=list(csv.DictReader(f))
 styles=[('curvature_ellipse',0.,'curvature ellipse','o'),('noise_ellipse',0.,'noise ellipse','x'),('noise_circle',0.,'noise circle rho0','s'),('combined_circle',.01,'circle rho.01','^'),('combined_circle',.05,'circle rho.05','D')]
 for mechanism in ['fixed_correct','fixed_survey','perturbed_survey']:
  for method in ['B0','B2']:
   fig,axes=plt.subplots(2,3,figsize=(15,8))
   for car in [1,2]:
    for col,view in enumerate(['endpoint_GN','endpoint_exact','oracle_truth_GN']):
     ax=axes[car-1,col]
     for kind,rho,label,mark in styles:
      rs=[r for r in rows if r['mechanism']==mechanism and r['method']==method and r['car']==str(car) and r['view']==view and r['kind']==kind and float(r['rho'])==rho and r['subset']=='all' and r['coverage_available']]
      if rs:ax.scatter([float(r['radius_mean']) for r in rs],[float(r['coverage_available']) for r in rs],label=label,marker=mark,alpha=.8)
     ax.axhline(.95,color='black',ls='--',lw=.7);ax.set(xscale='log',ylim=(-.03,1.03),xlabel='Mean max radius (m)',ylabel='Point-average coverage',title=f'Car{car} {view}');ax.grid(alpha=.2);ax.legend(fontsize=7)
   fig.suptitle(f'{mechanism}, {method}: all conditions; six epochs per seed');fig.tight_layout();fig.savefig(out/f'{mechanism}_{method}.png',dpi=140);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.summary,a.out)
