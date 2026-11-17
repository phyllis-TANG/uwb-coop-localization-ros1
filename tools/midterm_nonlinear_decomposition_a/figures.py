"""Static diagnostic figures; all estimates are saved endpoints or direct affine solutions."""
from common import *
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main(src,summ,out):
 out.mkdir(parents=True,exist_ok=False);ds=readcsv(summ/'DECOMPOSITION_SUMMARY.csv');rg=readcsv(summ/'REGION_SUMMARY.csv')
 def value(batch,condition,method,mode,metric):return float(next(r['mean'] for r in ds if (r['batch'],r['condition'],r['method'],r['mode'],r['metric'])==(batch,condition,method,mode,metric)))
 fig,axs=plt.subplots(1,2,figsize=(12,4.5))
 for ax,m in zip(axs,['B2','B3']):
  for metric,label in [('gradient_position_rms','nonzero gradient'),('remainder_position_rms','residual remainder'),('jacobian_position_rms','Jacobian change'),('difference_position_rms','NL - affine')]:
   ax.plot([0,.1,.5],[value('PR119',f'g0{i}',m,'selected',metric) for i in range(3)],'o-',label=label)
  ax.set(yscale='log',xlabel='Anchor perturbation [m]',ylabel='Mean seed position RMS [m]',title=m+' selected; 40 seeds/condition');ax.legend(fontsize=8)
 fig.suptitle('PR119 algebraic decomposition: norms are not additive contributions');fig.tight_layout();fig.savefig(out/'DECOMPOSITION_GEOMETRY.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(10,5));xx=np.arange(4);width=.18
 for k,(metric,label) in enumerate([('gradient_position_rms','gradient'),('remainder_position_rms','remainder'),('jacobian_position_rms','Jacobian change'),('difference_position_rms','NL - affine')]):ax.bar(xx+(k-1.5)*width,[value('PR121',c,'B2','all_finite',metric) for c in ['i00','i05','i10','i15']],width,label=label)
 ax.set(yscale='log',ylabel='Mean seed position RMS [m]',xticks=xx,xticklabels=['good / .5','good / .05','weak / .5','weak / .05'],title='PR121 zero center offset: 30 seeds/condition, all finite endpoints');ax.legend();fig.tight_layout();fig.savefig(out/'DECOMPOSITION_PRIOR.png',dpi=150);plt.close(fig)
 fig,axs=plt.subplots(2,2,figsize=(14,8))
 for col,scope in enumerate(['point95','joint95']):
  for row,model in enumerate(['AFFINE','NL_COMPARE']):
   ax=axs[row,col];arr=np.zeros((4,5));labels=[]
   for i,(geo,sigma) in enumerate([('good','.5'),('good','.05'),('weak','.5'),('weak','.05')]):
    labels.append(geo+' / '+sigma)
    for j,delta in enumerate([0,.01,-.01,.05,-.05]):
     r=next(r for r in rg if r['geometry']==geo and float(r['sigma'])==float(sigma) and float(r['offset_m'])==delta and r['model']==model and r['scope']==scope and r['kind']=='outer_circle' and float(r['rho'])==.05 and r['car']=='0' and r['subset']=='all');arr[i,j]=float(r['all_covered_full_plan'])
   im=ax.imshow(arr,vmin=0,vmax=1,cmap='viridis',aspect='auto');ax.set(xticks=range(5),xticklabels=['0','+.01','-.01','+.05','-.05'],yticks=range(4),yticklabels=labels,xlabel='Fixed Car1 Y center offset [m]',title=model+' / '+scope)
   for i in range(4):
    for j in range(5):ax.text(j,i,f'{round(arr[i,j]*30)}/30',ha='center',va='center',color='white' if arr[i,j]<.7 else 'black')
 fig.suptitle('All 12 blocks covered: outer circle rho=.05 m; all regions available\npoint95: empirical conjunction only; joint95: affine union-bound design, NL has no guarantee');fig.tight_layout();fig.savefig(out/'JOINT_COVERAGE.png',dpi=150);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(12,5))
 for scope in ['point95','joint95']:
  for rho in [0,.01,.05]:
   rr=[next(r for r in rg if r['condition']==c and r['model']=='AFFINE' and r['scope']==scope and r['kind']=='outer_circle' and float(r['rho'])==rho and r['car']=='0' and r['subset']=='all') for c in ['i00','i05','i10','i15']]
   label=f'{scope}, rho={rho}';axs[0].plot(range(4),[float(r['radius_mean']) for r in rr],'o-',label=label);axs[1].plot(range(4),[float(r['coverage_available']) for r in rr],'o-',label=label)
 for ax in axs:ax.set(xticks=range(4),xticklabels=['good/.5','good/.05','weak/.5','weak/.05']);ax.tick_params(axis='x',rotation=15)
 axs[0].set(ylabel='Mean block outer radius [m]',title='Zero fixed offset; 30 seeds, 360 planned/available points');axs[1].set(ylabel='Point-average empirical coverage',title='12 points clustered per seed');axs[1].legend(fontsize=8);fig.tight_layout();fig.savefig(out/'SIZE_COVERAGE.png',dpi=150);plt.close(fig)
 mats=list(records(src/'REGION_MATRICES.jsonl.gz'));mat=next(r for r in mats if r['id']=='i10-s391170001' and r['epoch']==0 and r['car']==1);P=np.array(mat['covariance']);rad=np.sqrt(chi2.ppf(.95,1)*np.linalg.eigvalsh(P)[-1]);pr=readcsv(src/'REGIONS.csv.gz');fig,ax=plt.subplots(figsize=(7,5))
 for model,mark in [('AFFINE','o'),('NL_COMPARE','x')]:
  rr=[r for r in pr if r['condition']=='i10' and r['model']==model and r['scope']=='point95' and r['kind']=='noise_support' and r['epoch']=='0' and r['car']=='1'];ax.scatter([float(r['error_x']) for r in rr],[float(r['error_y']) for r in rr],marker=mark,label=model+' (30 saved seeds)')
 ax.plot([-rad,rad],[0,0],'k-',lw=3,label='rank-1 Gaussian 95% segment');ax.set(xlabel='Position X error [m]',ylabel='Position Y error [m]',title='weak / prior sigma=.5 / center offset=0 / epoch0 car1');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(out/'SINGULAR_SUPPORT.png',dpi=150);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--summary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();protect();main(a.input,a.summary,a.out)
