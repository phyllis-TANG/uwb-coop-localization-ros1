"""Static scientific figures from tables only; no fitting."""
from common import *
import csv,argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    cov=list(csv.DictReader((args.results/'summary/COVERAGE.csv').open()));met=list(csv.DictReader((args.results/'summary/METRICS.csv').open()));branch=list(csv.DictReader((args.results/'summary/BRANCH.csv').open()));labels=['good correct .5','good survey .5','good correct .05','good survey .05','weak correct .5','weak survey .5','weak correct .05','weak survey .05']
    fig,axs=plt.subplots(3,2,figsize=(14,11),sharex=True,sharey=True)
    for i,m in enumerate(CFG['methods']):
      for car in [1,2]:
        ax=axs[i,car-1]
        for mode,marker in [('original','o'),('selected','s')]:
          a=[next(z for z in cov if z['condition']==c and z['method']==m and z['car']==str(car) and z['mode']==mode and z['view']=='curvature' and z['aggregation']=='point_mean' and z['level']=='0.95') for c in CFG['conditions']];yy=[float(z['planned_valid_and_covered']) for z in a];ax.plot(range(8),yy,marker+'-',label=mode)
          for k,z in enumerate(a):
            if z['planned_rate_ci_low']:ax.vlines(k,float(z['planned_rate_ci_low']),float(z['planned_rate_ci_high']),alpha=.4)
            if int(z['unavailable']):ax.plot(k,yy[k],'rx')
        ax.axhline(.95,color='gray',ls=':');ax.set_title(f'{m}, car {car}');ax.set_ylim(-.03,1.03);ax.set_xticks(range(8),labels,rotation=45,ha='right');ax.set_ylabel('Valid & covered / 180 points');ax.legend()
    fig.suptitle('95% pointwise GN ellipses; 30 seed clusters × 6 epochs per cell\nBars: seed bootstrap CI; red x: unavailable; not trajectory guarantee');fig.tight_layout();fig.savefig(out/'COVERAGE.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(12,5))
    for m,marker in zip(CFG['methods'],['o','s','^']):
      for mode,alpha in [('original',.4),('selected',1.)]:
        z=[r for r in met if r['method']==m and r['mode']==mode];axs[0].scatter([float(r['mean_curvature_sqrt_trace_m']) for r in z],[float(r['mean_rmse_m']) for r in z],marker=marker,alpha=alpha,label=f'{m} {mode}')
      z=[r for r in branch if r['method']==m];axs[1].plot(range(8),[int(r['multiple_accepted_groups'])/30 for r in z],marker+'-',label=m)
    axs[0].set(xlabel='Mean sqrt(trace(C_GN)) [m]',ylabel='Mean per-seed per-car RMSE [m]');axs[0].legend(fontsize=8);axs[1].set(xticks=range(8),xticklabels=labels,ylabel='Seeds with >1 accepted endpoint group / 30');axs[1].tick_params(axis='x',rotation=65);axs[1].legend();fig.suptitle('Error/interval size and endpoint-group diagnostics; all planned samples');fig.tight_layout();fig.savefig(out/'ERROR_AND_GROUPS.png',dpi=160);plt.close(fig)
    pr=list(csv.DictReader((args.results/'diagnostics/PROFILES.csv').open()));fig,axs=plt.subplots(2,4,figsize=(15,7))
    for ax,c,l in zip(axs.ravel(),CFG['conditions'],labels):
      for m in CFG['methods']:
        z=[r for r in pr if r['id'].startswith(c+'-') and r['method']==m];v=[float(r['cost']) for r in z];ax.plot([float(r['lambda_value']) for r in z],np.array(v)-min(v),label=m)
      ax.set_title(l);ax.set_xlabel('lambda, I0 to farthest accepted');ax.set_ylabel('Cost minus profile minimum');ax.legend()
    fig.suptitle('Preselected seed 281117001; line profiles are not re-optimization');fig.tight_layout();fig.savefig(out/'PROFILES.png',dpi=160);plt.close(fig)
if __name__=='__main__':main()
