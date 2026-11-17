"""Post-run presentation only: predeclared cases and all methods; no solver or selection tuning."""
import argparse,gzip,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io_utils import read

def plot(results,analysis,out):
    out.mkdir(exist_ok=False,parents=True)
    cases=read(analysis/'CASES.json');selected=[x for x in cases if x['rule']!='fixed_seed'];wanted={x['unit'] for x in selected};units={};fits={}
    for p in sorted(results.glob('EVIDENCE-*.jsonl.gz')):
        for line in gzip.open(p,'rt'):
            z=json.loads(line);v=z['value']
            if z['type']=='RUN':c=v['config']
            elif z['type']=='INPUT':
                uid=v['condition']['id']+'-s'+str(v['seed'])
                if uid in wanted:units[uid]=v
            elif z['type']=='METHOD' and v['unit'] in wanted:fits[v['unit'],v['method']]=v['stages']['P1']
    for rule in ['worst_B2_error','residual_error_rank_gap']:
        fig,axes=plt.subplots(2,2,figsize=(12,8))
        for car in [1,2]:
            for inj,ax in zip(['zero','constant'],axes[car-1]):
                case=next(x for x in selected if x['rule']==rule and x['car']==car and x['injection']==inj);u=units[case['unit']];q=u['condition']
                for method in c['methods']:
                    fit=fits[case['unit'],method]
                    if fit and fit['usable_estimate']:
                        error=np.linalg.norm(np.array(fit['estimate'][:24]).reshape(6,2,2)-u['truth'],axis=-1)[:,car-1];ax.plot(range(6),error,'o-',label=method+(' !' if not fit['accepted'] else ''))
                ax.set(title=f"{inj} Car{car} {q['noise_model']}\n{q['geometry']}/{q['motion']}/{q['candidate']} seed={u['seed']}",xlabel='epoch',ylabel='2D position error (m)');ax.legend(fontsize=7)
        fig.suptitle(rule+' (predeclared rule; ! = not numerically accepted)');fig.tight_layout();fig.savefig(out/(rule+'.png'),dpi=160);plt.close(fig)
    summ=read(analysis/'SUMMARY.json');labels=[(g,m,k) for g in c['matrix']['geometries'] for m in c['matrix']['motions'] for k in c['matrix']['candidates']]
    for car in [1,2]:
        fig,axes=plt.subplots(2,3,figsize=(16,8),sharex=True)
        for inj,axrow in zip(['zero','constant'],axes):
            for noise,ax in zip(c['matrix']['noise_models'],axrow):
                for method in c['methods']:
                    a=[next(s for s in summ if (s['geometry'],s['motion'],s['candidate'])==lab and s['injection']==inj and s['noise_model']==noise and s['method']==method) for lab in labels]
                    ax.plot(range(12),[s[f'rmse{car}_mean'] for s in a],'o-',ms=3,label=method)
                ax.set(title=f'{inj} / {noise} / Car{car}',ylabel='mean per-seed RMSE (m)');ax.set_xticks(range(12),['/'.join(x) for x in labels],rotation=90,fontsize=6);ax.legend(fontsize=7)
        fig.tight_layout();fig.savefig(out/f'all_methods_car{car}.png',dpi=160);plt.close(fig)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();plot(a.results,a.analysis,a.out)
