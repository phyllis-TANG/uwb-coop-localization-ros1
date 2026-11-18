"""Regenerate Chapter 7 exhibits and evaluate the distance contract at fixed epochs."""
import csv
import gzip
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

root = Path(__file__).resolve().parents[3]
lunar = root / 'docs/research/lunar_end_to_end'
source = lunar / 'replication'
out = lunar / 'interface'
out.mkdir(exist_ok=True)

def read_csv(name):
    with (source / name).open() as stream:
        return list(csv.DictReader(stream))

def save(name, rows):
    with (out / name).open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)

def export(fig, name):
    fig.savefig(out / (name + '.pdf'))
    fig.savefig(out / (name + '.png'), dpi=240)
    plt.close(fig)

conditions = ['normal', 'ramp_only', 'motion_only', 'both']
colors = ['#17648a', '#ab4a21']
pairs = [r for r in read_csv('PAIRS.csv') if r['method']=='M3']
assert len({tuple(r[k] for k in ('segment','car','condition','seed','baseline')) for r in pairs}) == len(pairs) == 320
save('paired.csv', pairs)
fig, axes = plt.subplots(4,4,figsize=(12,9),sharey=True,constrained_layout=True)
summary = []
for row,(segment,car) in enumerate((s,c) for s in ['main','second'] for c in ['1','2']):
    for col,cond in enumerate(conditions):
        ax=axes[row,col]
        ax.axhline(0,color='0.5',lw=.8)
        for x,baseline in enumerate(['M2','M0']):
            group=sorted((r for r in pairs if (r['segment'],r['car'],r['condition'],r['baseline'])==(segment,car,cond,baseline)),key=lambda r:r['seed'])
            assert len(group)==10
            vals=1000*np.array([float(r['base_rmse'])-float(r['method_rmse']) for r in group])
            np.testing.assert_allclose(vals,[1000*float(r['gain_m']) for r in group])
            for index,(r,v) in enumerate(zip(group,vals)):
                accepted=r['baseline_state']==r['method_state']=='ACCEPTED'
                ax.scatter(x+(index-4.5)*.055,v,s=16,marker='o' if accepted else 'x',c=colors[x])
            ax.hlines(vals.mean(),x-.30,x+.30,color='black',lw=2)
            ax.text(x,.96,f'{sum(vals>0)}/10',ha='center',va='top',transform=ax.get_xaxis_transform(),fontsize=9)
            summary.append(dict(segment=segment,car=car,condition=cond,baseline=baseline,mean_gain_mm=vals.mean(),improved=int(sum(vals>0)),finite=len(vals)))
        ax.set(xlim=(-.5,1.5),xticks=[0,1],xticklabels=['vs M2','vs M0'])
        if row==0:ax.set_title(['Normal','Range ramp','Motion anomaly','Ramp + anomaly'][col])
        if col==0:ax.set_ylabel(f'{segment.title()} · Car {car}\nRMSE gain (mm)')
for ax in axes.flat:ax.margins(y=.22)
export(fig,'contrasts')
save('summary.csv',summary)
slopes=read_csv('ZERO_BIAS.csv')
save('zero_bias.csv',slopes)
fig,axes=plt.subplots(1,2,figsize=(8.5,4),sharey=True,constrained_layout=True)
for ax,segment in zip(axes,['main','second']):
    ax.axhline(0,color='0.45',lw=.8)
    series=[]
    for cond in ['normal','motion_only']:
        group=sorted((r for r in slopes if r['segment']==segment and r['condition']==cond),key=lambda r:r['seed'])
        assert len(group)==10 and all(float(r['true_slope'])==0 for r in group)
        series.append([1000*float(r['estimated_m_s']) for r in group])
    ax.plot([0,1],series,color='0.73',lw=1)
    ax.scatter(np.repeat([0,1],10),np.ravel(series),s=20,c=colors[0])
    for x,v in enumerate(series):ax.hlines(np.mean(v),x-.1,x+.1,color='black',lw=2)
    ax.set(title=segment.title()+' segment',xticks=[0,1],xticklabels=['Normal','Motion anomaly'],xlim=(-.3,1.3))
axes[0].set_ylabel('Estimated peer slope (mm/s)')
export(fig,'zero_slopes')

geometry=[];witness=[]
for segment,folder in [('main','continuous'),('second','replication')]:
    records=json.loads(gzip.decompress((lunar/folder/'INPUTS.json.gz').read_bytes()))
    record=next(r for r in records if r['reference']['seed']==2026111801 and r['reference']['condition']=='normal')
    o=record['observation'];ref=record['reference'];t=o['times_s'];sigma=o['sigma_range']
    for i in (0,(len(t)-1)//2,len(t)-1):
        p,s=np.array(ref['xyz'][i]);anchors=np.array(o['anchors'])
        delta=np.vstack([p-anchors,s-anchors,s-p])
        horizontal=np.linalg.norm(delta[:,:2],axis=1)
        slant=np.linalg.norm(delta,axis=1)
        np.testing.assert_allclose(slant+ref['range_noise'][i],o['ranges'][i],atol=1e-12,rtol=0)
        for j in range(9):
            geometry.append(dict(segment=segment,index=i,relative_s=t[i],link=(f'car{1+j//4}_a{j%4}' if j<8 else 'peer'),dz_m=delta[j,2],planar_m=horizontal[j],slant_m=slant[j],difference_m=slant[j]-horizontal[j]))
        if segment=='second' and i==0:
            for n,q in [(8,24),(9,26)]:
                # A strictly interior noise vector, with enough margin to resolve rounding.
                difference=slant[0]-horizontal[0]
                values=slant.copy()
                values[0]+=sigma*np.sqrt(q)-difference/2
                corrected=np.sum(((values[:n]-slant[:n])/sigma)**2)
                planar=np.sum(((values[:8]-horizontal[:8])/sigma)**2)
                # For P4 the peer contribution has a nonnegative minimum regardless of B.
                assert corrected<q<planar
                witness.append(dict(method='N4' if n==8 else 'P4',threshold=q,epoch_car2_s=109.66,epoch_car1_s=114.66,p=p.tolist(),s=s.tolist(),anchors=anchors.tolist(),sigma=sigma,observation=values[:n].tolist(),true_bias=0,slant_metric_at_b0=corrected,planar_anchor_lower_bound=planar))
save('geometry.csv',geometry)
(out/'counterexample.json').write_text(json.dumps(witness,indent=2)+'\n')
print([(w['method'],w['slant_metric_at_b0'],w['planar_anchor_lower_bound']) for w in witness])
