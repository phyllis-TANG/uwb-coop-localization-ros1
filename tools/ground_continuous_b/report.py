"""Rebuild report tables, figure and example from the archived declarations."""
import csv
import gzip
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from timeline import CFG,DOC,csvout,load,METHODS

def read(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:
        return list(csv.DictReader(f))

def stage(t):
    if t<1:return 'startup'
    if t<24:return 'pre'
    if t<38:return '24-38'
    if t<48:return '38-48'
    return '48-64'

def draw(data):
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
    colors={'ALARM':'#d75e48','AVAILABLE':'#e4f1ed','other':'#92989f'}
    for c,ax in enumerate(axes,1):
        for method,style,label in [('region','-','G1 error at region delivery'),('aug',':','Augmented fix error')]:
            v=[r for r in data if int(r['car'])==c and r['method']==method]
            t=[float(r['time_s']) for r in v]
            ax.plot(t,[float(r['error_m']) if r['error_m'] else math.nan for r in v],style,color='#234f68' if method=='region' else '#74509c',lw=1.3,label=label)
            if method=='region':
                ax.plot(t,[float(r['PL_m']) if r['PL_m'] else math.nan for r in v],color='#da8317',lw=1.5,label='Region candidate PL (stamped)')
        ax.axhline(.10,color='black',ls='--',lw=1,label='Research AL 0.10 m')
        ax.axvspan(24,38,color='#f5daad',alpha=.38)
        ax.set(title=f'Car{c}  |  common +0.30 m wall-anchor bias on Car1',ylabel='Horizontal distance (m)',ylim=(0,None))
        ax.margins(x=0);ax.grid(axis='y',alpha=.18)
        strip=ax.inset_axes([0,-.30,1,.23],sharex=ax)
        for i,method in enumerate(METHODS):
            vals=[(float(r['time_s']),r['status']) for r in data if int(r['car'])==c and r['method']==method]
            begin=0
            for j in range(1,len(vals)+1):
                if j==len(vals) or vals[j][1]!=vals[begin][1]:
                    strip.broken_barh([(vals[begin][0],(j-begin)/20)],(i-.43,.86),facecolors=colors.get(vals[begin][1],colors['other']))
                    begin=j
        strip.set(yticks=range(3),yticklabels=['B2','Aug','Region'],ylim=(-.5,2.5),xlim=(0,64))
        strip.tick_params(labelsize=8);ax.tick_params(labelbottom=False)
        if c==2:strip.set_xlabel('Vehicle decision clock (s)')
    axes[0].legend(ncol=2,fontsize=8,loc='upper right')
    fig.legend(handles=[Patch(color=v,label=l) for v,l in zip(colors.values(),['Alarm','Declared available','No usable decision'])],loc='outside lower center',ncol=3)
    fig.savefig(DOC/'MAIN.png',dpi=180)
    plt.close(fig)

def main():
    windows=[];summaries=[];phase=defaultdict(lambda:[0,0,0,0]);timings=[];example=None
    for seed in [CFG['development_seed'],*CFG['holdout_seeds']]:
        baseline=None
        for scene in CFG['scenarios']:
            p=DOC/'runs'/f'{seed}_{scene}'
            summaries+=read(p/'summary.csv')
            rec=load(p/'records.json.gz')
            if baseline is None:baseline=rec
            pub=read(p/'publications.csv')[::2]
            for r,b,u in zip(rec,baseline,pub,strict=True):
                t=r['t']
                for j,(y,z) in enumerate(zip(r['obs']['ranges'],b['obs']['ranges'],strict=True)):
                    expected=0.
                    if 24<=t<38:
                        if scene=='wall' and j<4:expected=.30
                        if scene=='peer_step' and j==8:expected=.60
                        if scene=='peer_ramp' and j==8:expected=.60*(t-24)/13.95
                    assert abs(y-z-expected)<1e-12
                for m in METHODS:
                    timings.append(dict(seed=seed,scene=scene,state_s=t,method=m,service_s={'region':r['region_cost']+float(u['B_readback_s'])+float(u['A_radius_wall_s_pair']),'B2':r['b2_cost'],'aug':r['aug_cost']}[m]))
            tick=read(p/'ticks.csv.gz')
            assert len(tick)==1280*2*3*3*2
            for r in tick:
                if float(r['AL_m'])!=.10:continue
                key=(seed,scene,r['view'],int(r['car']),r['method'],stage(float(r['time_s'])))
                counts=phase[key];counts[0]+=1
                counts[1]+=r['status']=='AVAILABLE';counts[2]+=r['status']=='ALARM'
                missed=r['status']=='AVAILABLE' and float(r['error_m'])>.10
                counts[3]+=missed
                if seed==CFG['plot_seed'] and scene=='wall' and r['view']=='delivery' and missed and 24<=float(r['time_s'])<38 and example is None:
                    example=dict(seed=seed,scene=scene,**r)
            # One extra descriptive latency per physical injection window, without
            # dividing it at temporary monitor outages; keep original episode metric.
            for car in (1,2):
                for method in METHODS:
                    for view in ('state','delivery'):
                        obs=[r for r in tick if r['car']==str(car) and r['method']==method and r['view']==view and float(r['AL_m'])==.10 and 24<=float(r['time_s'])<38]
                        above=next((float(r['time_s']) for r in obs if r['error_m'] and float(r['error_m'])>.10),None)
                        alarm=next((float(r['time_s']) for r in obs if above is not None and float(r['time_s'])>=above and r['status']=='ALARM'),None)
                        windows.append(dict(seed=seed,scene=scene,car=car,method=method,view=view,first_exceed_s=above,alarm_at_or_after_s=alarm,delay_s=round(alarm-above,2) if alarm is not None else None,status='NO_OBSERVED_EXCEED' if above is None else 'NO_ALARM_BY_38' if alarm is None else 'ALARM'))
            if seed==CFG['plot_seed'] and scene==CFG['plot_scenario']:
                draw([r for r in tick if float(r['AL_m'])==.10 and r['view']=='delivery'])
    csvout(DOC/'WINDOW_DELAY.csv',windows)
    csvout(DOC/'ALL.csv',summaries)
    csvout(DOC/'PHASE.csv',[dict(seed=k[0],scene=k[1],view=k[2],car=k[3],method=k[4],period=k[5],duration_s=v[0]/20,available_s=v[1]/20,alarm_s=v[2]/20,exceed_available_s=v[3]/20) for k,v in phase.items()])
    csvout(DOC/'SERVICE.csv',timings)
    group=defaultdict(list)
    for r in summaries:
        if int(r['seed']) in CFG['holdout_seeds'] and float(r['AL_m'])==.1:
            group[(r['scene'],r['view'],r['car'],r['method'])].append(r)
    table=[]
    for (s,v,c,m),rows in group.items():
        assert len(rows)==2
        table.append(dict(scene=s,view=v,car=c,method=m,seeds=2,**{k:statistics.mean(float(r[k]) for r in rows) for k in ('available_s','alarm_s','unavailable_without_alarm_s','exceed_available_s')},exceed_episodes=sum(int(r['exceed_episodes']) for r in rows),never_alarm=sum(int(r['never_alarm']) for r in rows)))
    csvout(DOC/'MAIN.csv',table)
    (DOC/'EXAMPLE.json').write_text(json.dumps(example,indent=2)+'\n')
if __name__=='__main__':main()
