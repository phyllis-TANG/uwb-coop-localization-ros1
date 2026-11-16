"""Plots of all finite final estimates, including numerical nonacceptance."""
import argparse,csv,json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);z=p.parse_args();z.out.mkdir(parents=True,exist_ok=False)
    groups=json.loads((z.results/'GROUPS.json').read_text());rows=list(csv.DictReader((z.results/'PER_RUN.csv').open()))
    core=[g for g in groups if g['condition']['panel']=='core' and g['method']=='B2']
    plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False})
    fig,axs=plt.subplots(1,2,figsize=(12,10),sharey=True)
    labels=[f"{g['condition']['geometry']}/{g['condition']['motion']}/{g['condition']['kind']}/{g['condition']['bias_m']:g}" for g in core]
    for car,ax in enumerate(axs,1):
        for offset,metric,color,label in [(-.12,f'B2_minus_B1_car{car}','#2667a8','B2 - B1'),(.12,f'D_car{car}','#be5628','B2 - B0')]:
            for i,g in enumerate(core):
                v=g['metrics'][metric];ci=v['ci95'];mu=v['mean']
                if mu is None:continue
                ax.plot(mu,i+offset,'o',color=color,markersize=4,label=label if i==0 else None)
                if ci:ax.plot(ci,[i+offset,i+offset],color=color,lw=1.5)
        ax.axvline(0,color='gray',lw=1);ax.set_xlabel('Paired MSE difference (m²); negative = improvement');ax.set_title(f'Car {car}');ax.legend(loc='best')
    axs[0].set_yticks(range(len(labels)),labels);axs[0].invert_yaxis()
    fig.suptitle('Formal simulation: all finite P1 estimates | 50 seeds per condition\nPointwise 95% paired seed bootstrap; numerical nonacceptance retained')
    fig.tight_layout(rect=(0,0,1,.95));fig.savefig(z.out/'position_gains.png',dpi=180);plt.close(fig)
    b2=[g for g in groups if g['method']=='B2'];fig,ax=plt.subplots(figsize=(13,8))
    values=[];labels=[]
    for g in b2:
        c=g['condition'];values.append([float(r['bias_error']) for r in rows if r['id']==c['id'] and r['method']=='B2' and r['bias_error']!=''])
        labels.append(f"{c['id']} {c['geometry']}/{c['motion']}/{c['kind']}/{c['bias_m']:g} {c['panel']}")
    ax.boxplot(values,orientation='horizontal',tick_labels=labels,showfliers=True,flierprops={'markersize':2},widths=.6)
    ax.axvline(0,color='gray');ax.axvline(.1,color='#b44',ls='--');ax.axvline(-.1,color='#b44',ls='--');ax.invert_yaxis()
    ax.set_xlabel('B2 signed bias error (m); dashed lines = offline ±0.1 m diagnostic threshold')
    ax.set_title('All 50 finite final estimates per condition (acceptance labels retained in tables)\nBoxes: quartiles/median; whiskers: 1.5 IQR; points: outliers')
    fig.tight_layout();fig.savefig(z.out/'bias_errors.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(3,3,figsize=(12,10));panels=['no_prior','core','strong','shifted_strong'];x=np.arange(4)
    for gi,geo in enumerate(['good','weak','near']):
        gs=[next(g for g in b2 if g['condition']['geometry']==geo and g['condition']['motion']=='static' and g['condition']['kind']=='peer' and g['condition']['bias_m']==.3 and g['condition']['panel']==p) for p in panels]
        for car in [1,2]:
            ax=axs[gi,car-1]
            means=[g['metrics'][f'position_rmse_car{car}']['mean'] for g in gs]
            ci=[g['metrics'][f'position_rmse_car{car}']['ci95'] for g in gs]
            ax.plot(x,means,'o-',color='#2667a8')
            for k,v in enumerate(ci):
                if v:ax.plot([k,k],v,color='#2667a8')
            ax.set_title(f'{geo}: Car {car} mean RMSE');ax.set_ylabel('m');ax.set_xticks(x,panels,rotation=25)
        ax=axs[gi,2];means=[g['metrics']['bias_error']['mean'] for g in gs];ax.plot(x,means,'o-',color='#be5628')
        for k,g in enumerate(gs):
            if g['metrics']['bias_error']['ci95']:ax.plot([k,k],g['metrics']['bias_error']['ci95'],color='#be5628')
        ax.axhline(0,color='gray',lw=1);ax.set_title(f'{geo}: mean signed bias error');ax.set_ylabel('m');ax.set_xticks(x,panels,rotation=25)
    fig.suptitle('B2 prior sensitivity: static / peer +0.3 m | same 50 seeds and initialization\nAll finite P1 estimates; pointwise 95% seed bootstrap intervals')
    fig.tight_layout(rect=(0,0,1,.94));fig.savefig(z.out/'prior_sensitivity.png',dpi=180);plt.close(fig)
if __name__=='__main__':main()
