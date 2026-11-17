"""Figures from saved tables, no optimization, all planned denominators retained."""
from common import *
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load(p):return list(csv.DictReader(p.open()))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);cov=load(a.results/'summary/COVERAGE.csv');met=load(a.results/'summary/METRICS.csv');branch=load(a.results/'summary/BRANCH.csv');weak=load(a.results/'contrasts/WEAK_SUMMARY.csv');end=load(a.results/'readback/ENDPOINT_METRICS.csv');scales=[1.,.5,.25]
    fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True,sharey=True)
    for row,g in enumerate(['good','weak']):
      for col,m in enumerate(['B2','B3']):
        ax=axs[row,col]
        for car,color in [(1,'tab:blue'),(2,'tab:orange')]:
          for mode,ls in [('original','--'),('selected','-')]:
            z=[next(z for z in cov if z['geometry']==g and z['method']==m and float(z['noise_scale'])==s and z['car']==str(car) and z['view']=='curvature' and z['aggregation']=='point_mean' and z['level']=='0.95' and z['mode']==mode) for s in scales]
            yy=[float(r['planned_valid_and_covered']) for r in z];ax.plot(range(3),yy,'o'+ls,color=color,label=f'car {car} {mode}')
            if mode=='selected':
              for x,r in enumerate(z):
                if r['planned_rate_ci_low']:ax.vlines(x,float(r['planned_rate_ci_low']),float(r['planned_rate_ci_high']),color=color,alpha=.4)
        ax.axhline(.95,color='gray',ls=':');ax.set_title(f'{g}, {m}');ax.set_ylim(.6,1.02);ax.set_ylabel('Covered / 240 planned points');ax.set_xticks(range(3),['1','1/2','1/4']);ax.set_xlabel('Noise scale alpha');ax.legend(fontsize=8)
    fig.suptitle('95% pointwise GN ellipses; 40 seed clusters × 6 epochs\nBars: paired-seed bootstrap pointwise CI; not trajectory coverage');fig.tight_layout();fig.savefig(out/'COVERAGE.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,5))
    for g,ls in [('good','--'),('weak','-')]:
      for m,color in [('B2','tab:blue'),('B3','tab:orange')]:
        z=[next(r for r in branch if r['geometry']==g and r['method']==m and float(r['noise_scale'])==s) for s in scales];axs[0].plot(range(3),[int(r['multiple_accepted_groups'])/40 for r in z],'o'+ls,color=color,label=f'{g} {m}')
        z=[[r for r in end if r['geometry']==g and r['method']==m and float(r['noise_scale'])==s] for s in scales];axs[1].plot(range(3),[sum(r['accepted']=='True' for r in a)/200 for a in z],'x'+ls,color=color,label=f'{g} {m}')
    axs[0].set_ylabel('Seeds with >1 accepted group / 40');axs[1].set_ylabel('Accepted configurations / 200')
    for ax in axs:ax.set_xticks(range(3),['1','1/2','1/4']);ax.set_xlabel('Noise scale alpha');ax.set_ylim(-.02,1.02);ax.legend()
    fig.suptitle('Group frequency and numerical acceptance (failures retained)\nAll 480 units have selected estimates; weak B3 alpha=1/4 has 39/40 with >=2 accepted candidates');fig.tight_layout();fig.savefig(out/'GROUPS_AND_FAILURES.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for g,ls in [('good','--'),('weak','-')]:
      for m,color in [('B2','tab:blue'),('B3','tab:orange')]:
        for ax,metric in zip(axs,['overall_relative_norm','weak_relative_norm']):
          z=[next(r for r in weak if r['geometry']==g and r['method']==m and float(r['noise_scale'])==s and r['car']=='1' and r['metric']==metric) for s in scales];ax.plot(range(3),[float(r['mean']) for r in z],'o'+ls,color=color,label=f'{g} {m}')
    axs[0].set_ylabel('Mean ||E-G||F / ||G||F');axs[1].set_ylabel('Mean projected second-order / GN spectral norm')
    for ax in axs:ax.set_yscale('log');ax.set_xticks(range(3),['1','1/2','1/4']);ax.set_xlabel('Noise scale alpha');ax.legend()
    fig.suptitle('Selected endpoints: whole-matrix and weakest-subspace diagnostics\n40 seed units per geometry/method/scale; dimensionless, fixed state scales');fig.tight_layout();fig.savefig(out/'WEAK_CURVATURE.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(2,2,figsize=(12,8))
    for row,g in enumerate(['good','weak']):
      for col,m in enumerate(['B2','B3']):
        ax=axs[row,col]
        for car,color in [(1,'tab:blue'),(2,'tab:orange')]:
          z=[next(r for r in met if r['geometry']==g and r['method']==m and float(r['noise_scale'])==s and r['car']==str(car) and r['mode']=='selected') for s in scales];ax.plot(range(3),[float(r['mean_rmse_m']) for r in z],'o-',color=color,label=f'car{car} RMSE');ax.plot(range(3),[float(r['mean_curvature_sqrt_trace_m']) for r in z],'s--',color=color,label=f'car{car} sqrt(trace)')
        ax.set_title(f'{g} {m}');ax.set_ylabel('Mean over 40 seeds [m]');ax.set_xticks(range(3),['1','1/2','1/4']);ax.set_xlabel('Noise scale alpha');ax.legend(fontsize=8)
    fig.suptitle('Selected estimates: error and local interval scale (not an error bound)');fig.tight_layout();fig.savefig(out/'ERROR_AND_SIZE.png',dpi=170);plt.close(fig)
    old=load(DOC/'legacy_diagnostic/WEAK_DIRECTIONS.csv');fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,g in zip(axs,['good','weak']):
      for mech,marker in [('fixed_correct','o'),('fixed_survey','x')]:
        for sig,color in [(.5,'tab:blue'),(.05,'tab:orange')]:
          z=[r for r in old if r['geometry']==g and r['mechanism']==mech and float(r['prior_sigma'])==sig];ax.scatter([float(r['overall_relative_frobenius']) for r in z],[float(r['weak_second_order_signed_ratio']) for r in z],marker=marker,color=color,label=f'{mech}, prior {sig} m')
      ax.set_title(g);ax.set_xlabel('Whole-matrix relative Frobenius difference');ax.set_ylabel('Signed weakest-direction second-order / GN');ax.legend(fontsize=8)
    fig.suptitle('PR112: 48 preselected saved endpoints only; no new independent samples');fig.tight_layout();fig.savefig(out/'LEGACY_WEAK_DIRECTIONS.png',dpi=170);plt.close(fig)
if __name__=='__main__':main()
