"""Plot the preregistered peer-step timeline, including the post-recovery interval."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from evaluate import table, OUT

def draw():
    raw=table(OUT/'vehicle_ticks.csv')
    marks=table(OUT/'window_markers.csv')
    fig,axes=plt.subplots(2,1,figsize=(11,7),sharex=True,layout='constrained')
    palette={'AVAILABLE':'#c4ded2','ALARM':'#c84d40','EXPIRED':'#737b85'}
    for car,ax in enumerate(axes,1):
        def match(r):
            return (r['seed'],r['scene'],r['car'])==('2026111901','peer_step',str(car))
        rows=[r for r in raw if match(r)]
        times=[float(r['time_s']) for r in rows]
        err=[float(r['error_m']) if r['error_m'] else float('nan') for r in rows]
        ax.axvspan(24,38,color='#f5e2c4')
        ax.axvspan(38,48,color='#edf1f5')
        ax.plot(times,err,color='#1b5274',lw=1.4)
        ax.axhline(.10,ls='--',lw=1,color='#292929')
        ax.set(xlim=(0,64),ylim=(-.05,max(err[41:]+[.25])+.04),ylabel='Horizontal error (m)')
        start=0
        for i in range(1,len(rows)+1):
            if i==len(rows) or rows[i]['status']!=rows[start]['status']:
                ax.broken_barh([(times[start],(i-start)/20)],(-.045,.027),
                    facecolors=palette.get(rows[start]['status'],'#dedede'))
                start=i
        fault=next(r for r in marks if match(r) and r['window']=='fault')
        recover=next(r for r in marks if match(r) and r['window']=='recovery')
        available=next(r['time_s'] for r in rows if float(r['time_s'])>=38 and r['status']=='AVAILABLE')
        points=[(fault['first_exceed_s'],'o','#0f5472'),(fault['first_alarm_tick_s'],'^','#ba3529'),
                (recover['first_within_AL_s'],'D','#694e83'),(available,'s','#346848')]
        for t,s,c in points:
            i=round(float(t)*20)
            ax.scatter([times[i]],[err[i]],s=40,marker=s,color=c,zorder=5)
        ax.set_title(f'Car{car}   ● Exceed {float(points[0][0]):.2f} s   ▲ Alarm {float(points[1][0]):.2f} s'
            f'   ◆ Within AL {float(points[2][0]):.2f} s   ■ Available {float(available):.2f} s',fontsize=11,loc='left')
        ax.grid(axis='y',alpha=.16)
    axes[1].set_xlabel('Vehicle decision clock (s)  |  dashed line: AL = 0.10 m')
    fig.legend(handles=[Patch(color=v,label=l) for v,l in [
        ('#f5e2c4','Peer step [24, 38)'),('#edf1f5','Recovery [38, 48)'),
        ('#c4ded2','Available'),('#c84d40','Alarm'),('#737b85','Expired'),('#dedede','Startup / no decision')]],
        loc='outside lower center',ncol=3)
    fig.savefig(OUT/'peer_step.png',dpi=175)
    plt.close(fig)

if __name__=='__main__':
    draw()
