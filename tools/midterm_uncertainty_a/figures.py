"""Static research figures from saved diagnostics only; no optimization."""
import argparse,csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
from scipy.stats import chi2
from summarize import VIEWS,dump,table

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--summary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 read=lambda p:list(csv.DictReader(p.open()))
 runs=read(a.input/'RUNS.csv');cov=read(a.summary/'COVERAGE.csv');bias=read(a.summary/'BIAS_COVERAGE.csv');prior=read(a.summary/'PRIOR_COMPARISONS.csv');info=read(a.input/'INFORMATION.csv');ref=json.loads((a.input/'REFERENCE_INFORMATION.json').read_text());z=np.load(a.input/'MARGINALS.npz');cs=z['covariance_components'];e=z['position_error'];q=z['position_q']
 labels=[]
 for i in range(36):
  r=next(r for r in runs if r['id']==f'c{i:02d}');labels.append(f"{r['id']} {r['geometry']}/{r['motion']} {r['kind']} {r['bias_m']}m {r['panel']}")
 for level in [.95,.99]:
  fig,axes=plt.subplots(1,3,figsize=(18,14),sharey=True)
  for vi,view in enumerate(VIEWS):
   mat=np.empty((36,8))
   for ci in range(36):
    for mi,m in enumerate(['B0','B1','B2','B3']):
     for car in [1,2]:
      r=next(r for r in cov if r['id']==f'c{ci:02d}' and r['view']==view and r['method']==m and r['car']==str(car) and r['subset']=='all' and r['aggregation']=='point_average' and r['level']==str(level));mat[ci,mi*2+car-1]=float(r['covered_over_full_plan'])
   im=axes[vi].imshow(mat,vmin=0,vmax=1,cmap='viridis',aspect='auto');axes[vi].set_title(view);axes[vi].set_xticks(range(8),[f'{m}\ncar{c}' for m in ['B0','B1','B2','B3'] for c in [1,2]],fontsize=8);axes[vi].set_yticks(range(36),labels,fontsize=8)
  fig.suptitle(f'Nominal {level:.0%} pointwise ellipses: valid AND covered / planned\nEach cell: 50 seed clusters x 6 times = 300 points; unavailable 0/300; includes nonstationary results',fontsize=11);fig.colorbar(im,cax=fig.add_axes([.92,.2,.012,.6]),label='Coverage fraction');fig.subplots_adjust(left=.24,right=.89,wspace=.05,top=.93,bottom=.05);fig.savefig(a.out/f'coverage_{int(level*100)}.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(1,2,figsize=(12,5))
 for mi,m in enumerate(['B0','B1','B2','B3']):
  ids=np.array([i for i,r in enumerate(runs) if r['method']==m]);unc=np.sqrt(np.mean(cs[ids,0,:,0]+cs[ids,0,:,2],axis=1));err=np.sqrt(np.mean(np.sum(e[ids]**2,axis=2),axis=1));res=np.array([float(runs[i]['data_residual_rms']) for i in ids]);axes[0].scatter(unc,err,s=5,alpha=.22,label=m);axes[1].scatter(res,err,s=5,alpha=.22,label=m)
 axes[0].plot([.01,10],[.01,10],'k--',lw=.7);axes[0].set(xscale='log',yscale='log',xlabel='sqrt(mean position trace(C)) [m]',ylabel='Position RMSE [m]',title='Total curvature: 7200 saved runs');axes[1].set(yscale='log',xlabel='Whitened data residual RMS [unitless]',ylabel='Position RMSE [m]',title='Residual size is not error calibration');axes[0].legend();fig.suptitle('All finite endpoints, including 25 nonstationary; dots are paired, not independent n');fig.tight_layout();fig.savefig(a.out/'error_uncertainty.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(14,4.5))
 for ax,g in zip(axes,['good','weak','near']):
  rr=[r for r in prior if r['geometry']==g and r['method']=='B2' and r['view']=='total_curvature' and r['comparison']=='strong-core'];xx=np.arange(2);w=.18
  for off,key,label in [(-1.5,'core_mse','core MSE'),(-.5,'other_mse','strong MSE'),(.5,'core_trace','core trace(C)'),(1.5,'other_trace','strong trace(C)')]:ax.bar(xx+off*w,[float(r[key]) for r in rr],w,label=label)
  ax.set(xticks=xx,xticklabels=['car1','car2'],yscale='log',ylabel='Squared distance [m²]',title=g+' / static / peer +0.3m')
 axes[0].legend(fontsize=7);fig.suptitle('B2: fixed erroneous stronger prior; 50 paired seeds per geometry, all intervals available');fig.tight_layout();fig.savefig(a.out/'strong_prior.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(2,1,figsize=(13,7),sharex=True)
 for vi,view in enumerate(VIEWS):
  rr=sorted([r for r in bias if r['view']==view and r['level']=='0.95' and r['subset']=='all'],key=lambda r:r['id']);axes[0].plot(range(36),[float(r['coverage_available']) for r in rr],'.-',label=view);axes[1].plot(range(36),[float(r['mean_position_bias_R2']) for r in rr],'.-',label=view)
 axes[0].axhline(.95,color='k',ls='--');axes[0].set(ylabel='Bias coverage / 50',ylim=(0,1.02));axes[0].legend(fontsize=8);axes[1].set(ylabel='Mean local position-bias R²',xticks=range(36),xticklabels=[f'c{i:02d}' for i in range(36)],xlabel='Condition (full geometry/motion labels in coverage figures)');axes[1].tick_params(axis='x',rotation=90);fig.suptitle('B2 nominal 95% bias intervals and local coupling; 50 seeds/condition; unavailable 0; all labels retained');fig.tight_layout();fig.savefig(a.out/'bias_coupling.png',dpi=160);plt.close(fig)
 cases=json.loads((a.summary/'CASES.json').read_text());w=cases['worst_B2_total_point'];comp=w['covariance_components'];c=np.array([[comp[0],comp[1]],[comp[1],comp[2]]]);s,v=np.linalg.eigh(c);angle=np.degrees(np.arctan2(v[1,0],v[0,0]));fig,axes=plt.subplots(1,2,figsize=(12,5))
 for level in [.95,.99]:
  axes[0].add_patch(Ellipse((0,0),2*np.sqrt(chi2.ppf(level,2)*s[0]),2*np.sqrt(chi2.ppf(level,2)*s[1]),angle=angle,fill=False,label=f'{level:.0%}'))
 axes[0].scatter(*w['error'],color='red',label='Saved error');axes[0].set(xlim=(-.09,.14),ylim=(-.09,.09),xlabel='x error [m]',ylabel='y error [m]',title=f"{w['unit']} B2 car1 t0\nACCEPTED, q={w['q']:.2f}");axes[0].set_aspect('equal');axes[0].legend()
 for matrix in ['data','total']:
  rr=next(r for r in ref if r['condition_id']=='c26' and r['method']=='B2' and r['matrix']==matrix);sv=np.array(rr['singular_values']);axes[1].semilogy(range(1,len(sv)+1),sv/sv[0],'.-',label=f'{matrix} rank {rr["rank"]}/25')
 axes[1].axhline(1e-8,color='k',ls='--',label='rank threshold');axes[1].set(xlabel='Scaled Jacobian singular value index',ylabel='s / s_max',title='c26 weak/static/peer, no prior\nTRUTH REFERENCE, not saved endpoint');axes[1].legend();fig.suptitle('Largest B2 total q; reference rank loss illustrated separately (no endpoint interval unavailable)');fig.tight_layout();fig.savefig(a.out/'representative_cases.png',dpi=160);plt.close(fig)
 summary=[]
 for view in VIEWS:
  for method in ['B0','B1','B2','B3']:
   rr=[r for r in cov if r['view']==view and r['method']==method and r['subset']=='all' and r['aggregation']=='point_average' and r['level']=='0.95'];rates=[float(r['coverage_available']) for r in rr];summary.append(dict(view=view,method=method,conditions=36,car_condition_cells=72,planned_points=sum(int(r['planned']) for r in rr),available_points=sum(int(r['available']) for r in rr),covered_points=sum(int(r['covered']) for r in rr),min_cell_coverage=min(rates),max_cell_coverage=max(rates),mean_cell_coverage=np.mean(rates)))
 table(a.out.parent/'OVERVIEW.csv',summary)
 stat=dict(endpoint_information_rows=len(info),endpoint_deficient=sum(r['reason']!='AVAILABLE' for r in info),reference_information_rows=len(ref),reference_deficient=sum(r['reason']!='AVAILABLE' for r in ref),endpoint_rank_sensitivity_disagreements={key:sum(r[key]!=r['rank'] for r in info) for key in ['rank_1e-06','rank_1e-10','rank_1e-12']},endpoint_max_scaled_jacobian_condition=max(float(r['condition']) for r in info),reference_deficient_cases=[dict(condition=r['condition_id'],method=r['method'],matrix=r['matrix'],rank=r['rank'],dimension=r['dimension']) for r in ref if r['reason']!='AVAILABLE'])
 dump(a.out.parent/'RANK_SUMMARY.json',stat)
if __name__=='__main__':main()
