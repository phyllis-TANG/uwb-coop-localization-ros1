"""All finite outcomes and protocol-selected cases. No post-hoc alert threshold."""
import argparse,gzip,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io_utils import read
COLORS={'B0':'#7b8794','B1':'#d55e00','B2':'#0072b2','B3_full_oracle':'#009e73'}
def plots(results,analysis,out):
    out.mkdir(parents=True,exist_ok=False);meta=read(results/'RUN.json');c=meta['config'];rows=read(results/'ROWS.json.gz');summary=read(analysis/'SUMMARY.json');ints=read(analysis/'INTERVALS.json');cases=read(analysis/'CASES.json');faults=c['matrix']['injections'];methods=c['methods'];nf=len(faults)
    fig,axes=plt.subplots(1,nf,figsize=(3*nf,3),squeeze=False)
    for ax,f in zip(axes[0],faults):
        seq=c['injection_sequences_m'][f];ax.plot(range(6),seq['candidate'],'o-',label='candidate');ax.plot(range(6),seq['other'],'s--',label='other');ax.set(title=f,xlabel='epoch',ylabel='injected bias (m)',ylim=(-.02,.34));ax.legend(fontsize=7)
    fig.tight_layout();fig.savefig(out/'injection_sequences.png',dpi=160);plt.close(fig)
    labels=[(g,m,k) for g in c['matrix']['geometries'] for m in c['matrix']['motions'] for k in c['matrix']['candidates']]
    fig,axes=plt.subplots(1,2,figsize=(12,7))
    for car,ax in enumerate(axes,1):
        a=np.full((len(labels),nf),np.nan);star=np.zeros_like(a,bool)
        for i,(g,m,k) in enumerate(labels):
            for j,f in enumerate(faults):
                hit=[r for r in ints if r['geometry']==g and r['motion']==m and r['candidate']==k and r['injection']==f and r['method']=='B2' and r['metric']==f'B2_B1_{car}']
                if hit:a[i,j]=hit[0]['mean'];star[i,j]=hit[0]['lower'] is not None and hit[0]['lower']*hit[0]['upper']>0
        lim=max(.001,float(np.nanmax(abs(a))));im=ax.imshow(a,cmap='coolwarm',vmin=-lim,vmax=lim,aspect='auto');ax.set_xticks(range(nf),faults,rotation=45,ha='right');ax.set_yticks(range(len(labels)),['/'.join(q) for q in labels]);ax.set_title(f'Car{car}: paired MSE B2 - B1 (m2)')
        for i,j in zip(*np.where(star)):ax.text(j,i,'*',ha='center',va='center',fontsize=12)
        fig.colorbar(im,ax=ax,shrink=.7)
    fig.suptitle('* pointwise 95% interval excludes zero; not family-wise');fig.tight_layout();fig.savefig(out/'paired_method_comparison.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(2,nf,figsize=(3.3*nf,6),squeeze=False)
    for car in [1,2]:
        for j,f in enumerate(faults):
            ax=axes[car-1,j]
            for g,color in zip(c['matrix']['geometries'],['#009e73','#e69f00','#0072b2']):
                rs=[r for r in rows if r['method']=='B2' and r['injection']==f and r['geometry']==g and r['residual_rms'] is not None]
                ax.scatter([r['residual_rms'] for r in rs],[r[f'rmse{car}'] for r in rs],s=5,alpha=.25,label=g,color=color)
                bad=[r for r in rs if not r['accepted']];ax.scatter([r['residual_rms'] for r in bad],[r[f'rmse{car}'] for r in bad],s=20,marker='x',color='black')
            ax.set(title=f+' / Car'+str(car),xlabel='whitened residual RMS',ylabel='position RMSE (m)');ax.legend(fontsize=6)
    fig.tight_layout();fig.savefig(out/'residual_error_joint.png',dpi=160);plt.close(fig)
    wanted=set(x['unit'] for x in cases);units={};fits={}
    for p in sorted(results.glob('EVIDENCE-*.jsonl.gz')):
        for line in gzip.open(p,'rt'):
            rec=json.loads(line);v=rec['value']
            if rec['type']=='INPUT':
                key=v['condition']['id']+'-s'+str(v['seed'])
                if key in wanted:units[key]=v
            elif rec['type']=='METHOD' and v['unit'] in wanted:fits[v['unit'],v['method']]=v['stages']['P1']
    def temporal(kind,name):
        fig,axes=plt.subplots(2,nf,figsize=(3.3*nf,6),squeeze=False)
        for car in [1,2]:
            for j,f in enumerate(faults):
                if kind=='fixed':
                    options=[u for u in units if units[u]['condition']['geometry']=='weak' and units[u]['condition']['motion']=='static' and units[u]['condition']['candidate']=='peer' and units[u]['condition']['injection']==f and units[u]['seed']==c['representative_cases']['fixed_seed']]
                    uid=sorted(options)[0] if options else None
                else:
                    options=[x['unit'] for x in cases if x['rule']==kind and x['injection']==f and x['car']==car];uid=options[0] if options else None
                ax=axes[car-1,j]
                if uid is None:continue
                u=units[uid]
                for m in methods:
                    fit=fits[uid,m]
                    if fit is not None and fit['usable_estimate']:
                        e=np.linalg.norm(np.array(fit['estimate'][:24]).reshape(6,2,2)-u['truth'],axis=-1)[:,car-1];ax.plot(range(6),e,'o-',ms=3,label=m+(' !' if not fit['accepted'] else ''),color=COLORS[m])
                q=u['condition'];ax.set_title(f"{f} / Car{car}\n{q['geometry']}/{q['motion']}/{q['candidate']} s{u['seed']}",fontsize=8);ax.set(xlabel='epoch',ylabel='2D position error (m)');ax.legend(fontsize=6)
        fig.tight_layout();fig.savefig(out/name,dpi=160);plt.close(fig)
    temporal('fixed','fixed_seed_epoch_errors.png');temporal('worst_B2_error','worst_cases_epoch_errors.png');temporal('residual_error_rank_gap','rank_gap_cases_epoch_errors.png')
    fig,axes=plt.subplots(1,nf,figsize=(3*nf,4),squeeze=False)
    for ax,f in zip(axes[0],faults):
        data=[];names=[]
        for k in c['matrix']['candidates']:
            for g in c['matrix']['geometries']:
                vals=[r['bias_estimate'] for r in rows if r['method']=='B2' and r['injection']==f and r['geometry']==g and r['candidate']==k and r['bias_estimate'] is not None];data.append(vals);names.append(g+'/'+k)
        ax.boxplot(data,tick_labels=names,showfliers=True);ax.axhline(np.mean(c['injection_sequences_m'][f]['candidate']),linestyle='--',color='grey');ax.tick_params(axis='x',rotation=90,labelsize=7);ax.set(title=f,ylabel='estimated b (m)')
    fig.suptitle('Dashed: candidate injection mean, descriptive reference only');fig.tight_layout();fig.savefig(out/'estimated_bias_distribution.png',dpi=160);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();plots(a.results,a.analysis,a.out)
