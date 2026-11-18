"""Two fault histories on the same axes and receipt-clock policy as #149."""
import csv
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'docs/research/ground_b_round2/evaluation'
OUT=ROOT/'docs/research/ground_b_round3'
SCENES=('peer_step','peer_ramp')
SEED='2026111901'


def read(name):
    with (SRC/name).open() as f:
        return list(csv.DictReader(f))


def write(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def main():
    ticks=read('vehicle_ticks.csv')
    markers=read('window_markers.csv')
    events=read('events_by_tta.csv')
    results=[]
    for scene in SCENES:
        group=[e for e in events if e['scene']==scene and e['tta_s']=='2' and 24<=float(e['first_exceed_s'])<38]
        counts=Counter('already_alarmed' if e['already_alarmed']=='True' else e['outcome'] for e in group)
        expected=({'already_alarmed':3,'timely_alarm':2,'recovered_before_or_at_deadline':1} if scene=='peer_step' else
                  {'timely_alarm':1,'recovered_before_or_at_deadline':5,'exceed_available_at_deadline':3})
        assert counts==expected and {e['seed'] for e in group}=={'2026111901','2026111902'}
        results.append(dict(scene=scene,seeds=2,vehicles=2,events=len(group),already_alarmed=counts['already_alarmed'],
            newly_alarmed_by_2s=counts['timely_alarm'],recovered_by_2s=counts['recovered_before_or_at_deadline'],
            exceeding_and_available_at_2s=counts['exceed_available_at_deadline']))
    write('two_seed_events.csv',results)
    plt.rcParams.update({'font.size':12,'pdf.fonttype':42})
    fig,axes=plt.subplots(2,2,figsize=(16,9),sharex=True,sharey=True)
    fig.subplots_adjust(left=.075,right=.98,bottom=.20,top=.80,wspace=.10,hspace=.64)
    fig.suptitle('Inter-vehicle range faults on the vehicle decision clock',x=.075,y=.975,ha='left',fontsize=24,weight='bold')
    fig.text(.075,.898,'B2 solution separation   ·   Seed 2026111901   ·   Alert limit 10 cm   ·   Bias removed at 38 s',fontsize=14)
    fig.text(.075,.835,'STEP   /   +0.60 m',weight='bold',fontsize=17)
    fig.text(.548,.835,'RAMP   /   0 to +0.60 m',weight='bold',fontsize=17)
    colors={'AVAILABLE':'#8bcdb0','ALARM':'#c6473e','EXPIRED':'#687783'}
    styles=[('o','#17648b','First exceedance'),('^','#ab3028','First displayed alarm'),
            ('D','#725197','Within limit after removal'),('s','#19623d','Available after removal')]
    selected=[]
    for j,scene in enumerate(SCENES):
        for c in (1,2):
            def match(r):
                return (r['seed'],r['scene'],r['car'])==(SEED,scene,str(c))
            rows=[r for r in ticks if match(r) and 24<=float(r['time_s'])<51.55]
            fault=next(r for r in markers if match(r) and r['window']=='fault')
            rec=next(r for r in markers if match(r) and r['window']=='recovery')
            errs=[float(r['error_m'])*100 if r['error_m'] else float('nan') for r in rows]
            times=[float(r['time_s']) for r in rows]
            available=next(float(r['time_s']) for r in rows if float(r['time_s'])>=38 and r['status']=='AVAILABLE')
            ts=[float(fault['first_exceed_s']),float(fault['first_alarm_tick_s']),float(rec['first_within_AL_s']),available]
            assert all(t in times for t in ts)
            selected.append(dict(seed=SEED,scene=scene,car=c,first_fault_exceed_s=ts[0],status_at_exceed=fault['status_at_first'],
                first_fault_alarm_s=ts[1],first_post_removal_within_s=ts[2],first_post_removal_available_s=available))
            ax=axes[c-1,j]
            ax.axvspan(24,38,color='#faf0dd')
            ax.axvline(38,color='#765e43',lw=1.2)
            ax.axhline(10,color='#30363b',ls='--',lw=1)
            ax.plot(times,errs,color='#164f69',lw=1.65)
            start=0
            for i in range(1,len(rows)+1):
                if i==len(rows) or rows[i]['status']!=rows[start]['status']:
                    ax.broken_barh([(times[start],(i-start)/20)],(-4.1,2.5),facecolors=colors[rows[start]['status']])
                    start=i
            for t,(marker,color,_) in zip(ts,styles):
                ax.scatter(t,errs[times.index(t)],color=color,marker=marker,edgecolor='white',linewidth=.5,s=64,zorder=4)
            ax.set(xlim=(24,51.55),ylim=(-5,34),yticks=[0,10,20,30],xticks=[24,28,32,38,42,48,51])
            ax.spines[['top','right']].set_visible(False)
            if j==0:ax.set_ylabel(f'Car {c} error (cm)',weight='bold')
            if c==2:ax.set_xlabel('Vehicle clock (s)')
            ax.set_title(f'Exceed {ts[0]:.2f}  ·  Alarm {ts[1]:.2f}     |     Within {ts[2]:.2f}  ·  Available {ts[3]:.2f}',fontsize=12,loc='left',pad=8)
    handles=[Line2D([],[],marker=m,color=color,ls='',markersize=8,label=lab) for m,color,lab in styles]
    fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.5,.086),ncol=4,frameon=False)
    fig.legend(handles=[Patch(color=v,label=k.title()) for k,v in colors.items()],title='Displayed state (strip below each trace)',loc='lower center',
               bbox_to_anchor=(.5,.009),ncol=3,frameon=False)
    fig.savefig(OUT/'step_vs_ramp.png',dpi=175)
    fig.savefig(OUT/'step_vs_ramp.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    write('figure_times.csv',selected)

if __name__=='__main__':
    main()
