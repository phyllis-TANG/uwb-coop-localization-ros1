"""Plots and descriptive cross-condition ranges; no pooled inferential sample."""
import argparse
from collections import defaultdict
from common import *
sys.path.insert(0,str(Path(__file__).resolve().parent))
from summarize import load
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',choices=list(CFG['batches']),required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--summary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
 rows,z,_,_=load(args.input);tables=csvread(args.summary/'COVERAGE.csv.gz');rates=[r for r in tables if r['subset']=='all' and r['aggregation']=='point_average'];lookup={(r['id'],r['method'],r['car'],r['view'],r['level']):r for r in rates};cid=sorted({r['id'] for r in rows});meta={r['id']:r for r in rows};n=CFG['batches'][args.batch]['seeds'];marks=defaultdict(set)
 for r in rows:marks[r['id'],r['method']].add(r['category'])
 labels=[f"{c} {meta[c]['geometry']}/{meta[c]['motion']} {meta[c]['candidate']} {meta[c]['injection']}"+(f" {meta[c]['noise_model']}" if args.batch=='noise' else '') for c in cid]
 for level in CFG['levels']:
  fig,axes=plt.subplots(1,3,figsize=(20,25),sharey=True)
  for v,view in enumerate(VIEWS):
   mat=np.array([[float(lookup[c,m,str(car),view,str(level)]['covered_over_full_plan']) for m in METHODS for car in [1,2]] for c in cid]);im=axes[v].imshow(mat,aspect='auto',vmin=0,vmax=1,cmap='viridis');axes[v].set_title(view,fontsize=12);axes[v].set_yticks(range(72),labels,fontsize=7);axes[v].set_xticks(range(8),[f'{m.replace("_full_oracle", "*")}\ncar{c}' for m in METHODS for c in [1,2]],fontsize=8)
   for i,c in enumerate(cid):
    for j,m in enumerate(METHODS):
     for car in [1,2]:
      if 'NOT_STATIONARY' in marks[c,m]:axes[v].plot(j*2+car-1-.15,i,'+',color='white',ms=3)
      if 'BUDGET_EXHAUSTED' in marks[c,m]:axes[v].plot(j*2+car-1+.15,i,'x',color='red',ms=3)
      if int(lookup[c,m,str(car),view,str(level)]['unavailable']):axes[v].text(j*2+car-1,i,'!',ha='center',color='red',fontsize=6)
  fig.suptitle(f'{args.batch}: nominal {level:.0%} POINTWISE coverage, valid & covered / planned\nEach cell: {n} seed clusters x 6 times = {n*6} points. + nonstationary present; red x budget present; ! unavailable\nAll finite final states included. B3* is full bias oracle; C is known-noise OFFLINE reference.',fontsize=12)
  fig.subplots_adjust(left=.30,right=.92,wspace=.06,top=.945,bottom=.035);fig.colorbar(im,cax=fig.add_axes([.945,.2,.01,.6]),label='Point coverage fraction (not trajectory guarantee)');fig.savefig(args.out/f'coverage_{int(level*100)}.png',dpi=140);plt.close(fig)
 # Each dot is one method/seed; marker overlays retain both nonaccepted categories.
 fig,axes=plt.subplots(2,3,figsize=(15,8))
 for car in [1,2]:
  blocks=np.arange(car-1,12,2);actual=np.sqrt(np.mean(np.sum(z['error'][:,blocks]**2,axis=-1),axis=1))
  for v,view in enumerate(VIEWS):
   ax=axes[car-1,v];unc=np.sqrt(np.mean(z['covariance'][:,v,blocks,0]+z['covariance'][:,v,blocks,2],axis=1))
   for mi,m in enumerate(METHODS):
    ii=np.array([i for i,r in enumerate(rows) if r['method']==m]);ax.scatter(unc[ii],actual[ii],s=2,alpha=.15,label=m)
   for cat,marker,color in [('NOT_STATIONARY','+','black'),('BUDGET_EXHAUSTED','x','red')]:
    ii=[i for i,r in enumerate(rows) if r['category']==cat];ax.scatter(unc[ii],actual[ii],s=10,marker=marker,color=color,label=cat)
   ax.plot([.01,3],[.01,3],'k--',lw=.5);ax.set(xscale='log',yscale='log',xlabel='sqrt(mean marginal trace) [m]',ylabel=f'Car{car} trajectory RMSE [m]',title=view)
 axes[0,0].legend(fontsize=6);fig.suptitle(f'{args.batch}: all {len(rows)} saved method endpoints; independent n={n}/condition, dots are correlated');fig.tight_layout();fig.savefig(args.out/'error_size.png',dpi=150);plt.close(fig)
 # Descriptive summaries preserve n; no CI pooling across reused seeds.
 summary=[];factor='injection' if args.batch=='fault' else 'noise_model'
 for f in sorted({r[factor] for r in rows}):
  for m in METHODS:
   for car in [1,2]:
    for view in VIEWS:
     for level in CFG['levels']:
      rr=[r for r in rates if r[factor]==f and r['method']==m and r['car']==str(car) and r['view']==view and r['level']==str(level)];vals=[float(r['coverage_available']) for r in rr if r['coverage_available']];summary.append(dict(batch=args.batch,factor=f,method=m,car=car,view=view,level=level,condition_cells=len(rr),independent_seeds=n,planned_points_descriptive=sum(int(r['planned']) for r in rr),available_points=sum(int(r['available']) for r in rr),covered_points=sum(int(r['covered']) for r in rr),mean_condition_coverage=float(np.mean(vals)) if vals else None,min_condition_coverage=min(vals) if vals else None,max_condition_coverage=max(vals) if vals else None))
 csvwrite(args.out/'DESCRIPTIVE.csv',summary)
 if args.batch=='noise':
  fig,axes=plt.subplots(3,4,figsize=(15,10),sharey=True)
  for i,noise in enumerate(['iid_004','iid_008','ar1_07']):
   for j,m in enumerate(METHODS):
    ax=axes[i,j]
    categories={r['category'] for r in rows if r['noise_model']==noise and r['method']==m}
    symbols=(' +' if 'NOT_STATIONARY' in categories else '')+(' x' if 'BUDGET_EXHAUSTED' in categories else '')
    for v,view in enumerate(VIEWS):
     vals=[next(r['mean_condition_coverage'] for r in summary if r['factor']==noise and r['method']==m and r['car']==car and r['view']==view and r['level']==.95) for car in [1,2]];ax.bar(np.arange(2)+(v-1)*.23,vals,.23,label=view)
    ax.axhline(.95,color='k',ls='--',lw=.6);ax.set(xticks=[0,1],xticklabels=['car1','car2'],ylim=(0,1.02),title=noise+' / '+m+symbols,ylabel='Mean condition coverage')
  axes[0,0].legend(fontsize=6);fig.suptitle('Nominal 95% point coverage: equal-weight description across 24 conditions/noise\nEach condition n=50 seeds, 300 points/car; + nonstationary; x budget present; no pooled CI. C: offline known covariance.');fig.tight_layout(rect=[0,0,1,.94]);fig.savefig(args.out/'noise_explanations.png',dpi=150);plt.close(fig)
if __name__=='__main__':main()
