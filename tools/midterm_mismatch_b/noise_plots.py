"""Separate noise-exploration figures, leaving first-batch plots/statistics untouched."""
import argparse,gzip,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io_utils import read

def plots(results,analysis,out):
    out.mkdir(parents=True,exist_ok=False);meta=read(results/'RUN.json');c=meta['config'];summ=read(analysis/'SUMMARY.json');rows=read(results/'ROWS.json.gz');models=c['matrix']['noise_models'];labels=[(g,m,k) for g in c['matrix']['geometries'] for m in c['matrix']['motions'] for k in c['matrix']['candidates']]
    for metric,name in [('mean','noise_position_mean.png'),('q95','noise_position_tail.png')]:
        fig,axes=plt.subplots(2,2,figsize=(11,10))
        for car in [1,2]:
            for f,ax in zip(c['matrix']['injections'],axes[car-1]):
                a=np.array([[next(x[f'rmse{car}_{metric}'] for x in summ if x['method']=='B2' and (x['geometry'],x['motion'],x['candidate'])==label and x['injection']==f and x['noise_model']==n) for n in models] for label in labels]);im=ax.imshow(a,aspect='auto',vmin=0,cmap='magma');ax.set_xticks(range(3),models);ax.set_yticks(range(len(labels)),['/'.join(x) for x in labels],fontsize=8);ax.set_title(f'B2 Car{car} {f}: {metric} RMSE (m)');fig.colorbar(im,ax=ax,shrink=.8)
        fig.tight_layout();fig.savefig(out/name,dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    for car in [1,2]:
        for n,ax in zip(models,axes[car-1]):
            for g,color in zip(c['matrix']['geometries'],['#009e73','#e69f00','#0072b2']):
                a=[r for r in rows if r['method']=='B2' and r['noise_model']==n and r['geometry']==g and r['residual_rms'] is not None];ax.scatter([x['residual_rms'] for x in a],[x[f'rmse{car}'] for x in a],s=6,alpha=.3,color=color,label=g);bad=[x for x in a if not x['accepted']];ax.scatter([x['residual_rms'] for x in bad],[x[f'rmse{car}'] for x in bad],marker='x',s=18,c='black')
            ax.set(title=f'{n} Car{car}',xlabel='assumed-whitened residual RMS',ylabel='position RMSE (m)');ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'noise_residual_error_joint.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,4,figsize=(13,3))
    for ax,name in zip(axes,['assumed']+models):
        if name=='assumed':cov=np.eye(6)*.04**2
        else:
            model=c['range_noise_models'][name];cov=model['actual_marginal_sigma_m']**2*model.get('rho',0.)**np.abs(np.arange(6)[:,None]-np.arange(6)[None,:])
        im=ax.imshow(cov,vmin=0,vmax=.08**2,cmap='viridis');ax.set(title=name,xlabel='epoch',ylabel='epoch');fig.colorbar(im,ax=ax,shrink=.7)
    fig.tight_layout();fig.savefig(out/'noise_covariance_contract.png',dpi=160);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();plots(a.results,a.analysis,a.out)
