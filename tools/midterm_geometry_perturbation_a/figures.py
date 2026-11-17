"""Scientific figures from saved tables only; planned seed/point denominators explicit."""
from common import *
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def load(p):return list(csv.DictReader(p.open()))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);p=a.results;cov=load(p/'summary/COVERAGE.csv');metrics=load(p/'summary/METRICS.csv');weak=load(p/'contrasts/WEAK_SUMMARY.csv');branch=load(p/'summary/BRANCH.csv');ends=load(p/'readback/ENDPOINT_METRICS.csv');delta=[0.,.1,.5]
    fig,axs=plt.subplots(1,2,figsize=(12,5),sharey=True)
    for ax,m in zip(axs,['B2','B3']):
      for car,color in [(1,'tab:blue'),(2,'tab:orange')]:
       for mode,style in [('original','--'),('selected','-')]:
        z=[next(r for r in cov if r['method']==m and float(r['perturbation_m'])==v and r['car']==str(car) and r['mode']==mode and r['view']=='curvature' and r['level']=='0.95' and r['aggregation']=='point_mean') for v in delta];yy=[float(r['planned_valid_and_covered']) for r in z];ax.plot(delta,yy,'o'+style,color=color,label=f'car {car} {mode}')
        if mode=='selected':
         for x,r in zip(delta,z):
          if r['planned_rate_ci_low']:ax.vlines(x,float(r['planned_rate_ci_low']),float(r['planned_rate_ci_high']),color=color,alpha=.4)
      ax.axhline(.95,ls=':',color='gray');ax.set(title=m,xlabel='Anchor perturbation amplitude [m]',ylabel='Covered / 240 planned points',ylim=(.65,1.02),xticks=delta);ax.legend(fontsize=8)
    fig.suptitle('95% pointwise GN ellipses: 40 paired seed clusters × 6 epochs\nAll main intervals available; bars: seed-cluster pointwise CI, not trajectory guarantee');fig.tight_layout();fig.savefig(out/'COVERAGE.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for m,color in [('B2','tab:blue'),('B3','tab:orange')]:
      z=[next(r for r in branch if r['method']==m and float(r['perturbation_m'])==v) for v in delta];axs[0].plot(delta,[int(r['multiple_accepted_groups'])/40 for r in z],'o-',label=m,color=color)
      rates=[]
      for v in delta:
        rr=[r for r in ends if r['method']==m and float(r['perturbation_m'])==v];rates.append(sum(r['accepted']=='True' for r in rr)/200)
      axs[1].plot(delta,rates,'x-',label=m,color=color)
    axs[0].set_ylabel('Seeds with >1 accepted group / 40');axs[1].set_ylabel('Accepted / 200 configurations')
    for ax in axs:ax.set(xlabel='Anchor perturbation amplitude [m]',xticks=delta,ylim=(-.02,1.02));ax.legend()
    fig.suptitle('Same 5 starts and paired noise across geometry\n19 non-accepted final states retained (16 nonstationary, 3 budget exhausted)');fig.tight_layout();fig.savefig(out/'GROUPS_AND_FAILURES.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,m in zip(axs,['B2','B3']):
      for car,color in [(1,'tab:blue'),(2,'tab:orange')]:
        z=[next(r for r in metrics if r['method']==m and float(r['perturbation_m'])==v and r['car']==str(car) and r['mode']=='selected') for v in delta];ax.plot(delta,[float(r['mean_rmse_m']) for r in z],'o-',color=color,label=f'car {car} RMSE');ax.plot(delta,[float(r['mean_curvature_sqrt_trace_m']) for r in z],'s--',color=color,label=f'car {car} sqrt(trace)')
      ax.set(title=m,xlabel='Anchor perturbation amplitude [m]',ylabel='Mean over 40 seeds [m]',xticks=delta);ax.legend()
    fig.suptitle('Selected error and interval size; coverage must be read alongside both');fig.tight_layout();fig.savefig(out/'ERROR_AND_SIZE.png',dpi=170);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for m,color in [('B2','tab:blue'),('B3','tab:orange')]:
      for ax,metric in zip(axs,['weak_relative_norm','overall_relative_norm']):
        z=[next(r for r in weak if r['method']==m and float(r['perturbation_m'])==v and r['metric']==metric and r['car']=='1') for v in delta];ax.plot(delta,[float(r['mean']) for r in z],'o-',label=m,color=color)
    axs[0].set_ylabel('Weak-subspace second-order/GN norm ratio');axs[1].set_ylabel('Whole Hessian relative Frobenius difference')
    for ax in axs:ax.set(xlabel='Anchor perturbation amplitude [m]',xticks=delta);ax.set_yscale('log');ax.legend()
    fig.suptitle('Selected endpoints: 40 seed units, dimensionless fixed state scales');fig.tight_layout();fig.savefig(out/'CURVATURE.png',dpi=170);plt.close(fig)
    truth=load(p/'information/TRUTH_DESIGN_INFORMATION.csv');fig,axs=plt.subplots(1,2,figsize=(12,5))
    for ax,m in zip(axs,['B2','B3']):
      for comp,style in [('range','o-'),('range_motion','s--'),('total','^-')]:
        z=[next(r for r in truth if r['method']==m and float(r['perturbation_m'])==v and r['component']==comp) for v in delta];ax.plot(delta,[float(r['effective_min']) for r in z],style,label=comp)
      ax.set(title=m,xlabel='Anchor perturbation amplitude [m]',ylabel='Minimum effective transverse information [1/m²]',xticks=delta);ax.legend()
    fig.suptitle('Offline truth-design information, nuisance longitudinal/bias directions eliminated\n6 deterministic design points, not additional seeds; numerical ~-2e-13 denotes zero');fig.tight_layout();fig.savefig(out/'TRANSVERSE_INFORMATION.png',dpi=170);plt.close(fig)
if __name__=='__main__':main()
