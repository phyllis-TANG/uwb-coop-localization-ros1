"""Full-matrix figures, no favorable case selection and no optimizer."""
import argparse,csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def table(p):return list(csv.DictReader(p.open()))
def f(x):return float(x) if x not in ['',None] else np.nan
def plots(inp,out):
    out.mkdir(parents=True,exist_ok=False);cover=table(inp/'COVERAGE.csv');mom=table(inp/'MOMENTS.csv');summary=table(inp/'SUMMARY.csv');labels=[(g,s,k) for g in ['good','weak','near'] for s in [.5,.05] for k in ['fixed_correct','fixed_survey','random_correct']];methods=['B0','B1','B2','B3']
    for car in [1,2]:
     for view in ['curvature','mechanism_noise']:
        fig,axes=plt.subplots(2,2,figsize=(12,12))
        for row,model in enumerate(['truth_linearized','nonlinear']):
         for col,b in enumerate([0.,.3]):
            ax=axes[row,col];a=np.full((18,4),np.nan)
            for i,(g,s,k) in enumerate(labels):
             for j,m in enumerate(methods):
                x=next(x for x in cover if x['geometry']==g and float(x['prior_sigma'])==s and x['mechanism']==k and x['method']==m and x['model']==model and float(x['bias_m'])==b and int(x['car'])==car and x['view']==view and x['level']=='0.95' and x['subset']=='all' and x['aggregation']=='point_average');a[i,j]=float(x['coverage']) if x['coverage'] else np.nan
            cmap=plt.get_cmap('viridis').copy();cmap.set_bad('lightgray');im=ax.imshow(a,vmin=0,vmax=1,cmap=cmap,aspect='auto');ax.set_xticks(range(4),methods);ax.set_yticks(range(18),['/'.join(map(str,x)) for x in labels],fontsize=7);ax.set_title(f'{model} bias={b} Car{car}')
            for i in range(18):
             for j in range(4):ax.text(j,i,'NA' if np.isnan(a[i,j]) else f'{a[i,j]:.2f}',ha='center',va='center',fontsize=7,color='white' if a[i,j]<.6 else 'black')
            fig.colorbar(im,ax=ax,shrink=.7)
        fig.suptitle(view+' nominal 95% point-average (available denominator; unavailable counts in table)');fig.tight_layout();fig.savefig(out/f'coverage_{view}_car{car}.png',dpi=160);plt.close(fig)
    for car in [1,2]:
        fig,axes=plt.subplots(2,1,figsize=(14,8))
        for model,ax in zip(['truth_linearized','nonlinear'],axes):
            bias=[];var=[]
            for g,s,k in labels:
                a=[x for x in mom if x['geometry']==g and float(x['prior_sigma'])==s and x['mechanism']==k and x['method']=='B2' and x['model']==model and float(x['bias_m'])==.3 and int(x['car'])==car and x['view']=='curvature'];bias.append(np.mean([f(x['mean_squared']) for x in a]));var.append(np.mean([((int(x['n'])-1)/int(x['n'])*f(x['centered_trace'])) if int(x['n'])>1 else np.nan for x in a]))
            ax.bar(range(18),bias,label='squared mean error');ax.bar(range(18),var,bottom=bias,label='centered fluctuation contribution');ax.set_xticks(range(18),['/'.join(map(str,x)) for x in labels],rotation=55,ha='right',fontsize=7);ax.set(title=f'B2 +0.3 / {model} / Car{car}',ylabel='MSE decomposition (m2)');ax.legend()
        fig.tight_layout();fig.savefig(out/f'mean_fluctuation_car{car}.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    for car,ax in enumerate(axes,1):
        for m in methods:
            a=[x for x in summary if x['method']==m and x['model']=='truth_linearized'];b=[next(y for y in summary if y['method']==m and y['model']=='nonlinear' and y['id']==x['id']) for x in a];ax.scatter([f(x[f'mse{car}']) for x in a],[f(x[f'mse{car}']) for x in b],label=m,alpha=.7)
        ax.plot([0,1],[0,1],'k--',lw=.8);ax.set(xscale='log',yscale='log',xlim=(1e-4,1),ylim=(1e-4,1),xlabel='truth-linearized MSE',ylabel='nonlinear MSE',title=f'All 36 conditions / Car{car}');ax.legend()
    fig.tight_layout();fig.savefig(out/'linear_nonlinear_all_conditions.png',dpi=160);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();plots(a.input,a.out)
