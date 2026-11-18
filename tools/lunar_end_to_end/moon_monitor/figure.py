from monitor import D,read
from evaluate_monitor import save_csv
import csv
from collections import Counter
import matplotlib.pyplot as plt

def render():
    rows=list(csv.DictReader((D/'availability.csv').open()))
    events=read(D/'events.json');truth=read(D/'evaluation_xyz.json')
    fig,axes=plt.subplots(2,3,figsize=(15,8),layout='constrained')
    summaries=[]
    for line,segment in enumerate(['main','second']):
        route=[e for e in events if e['route']==segment and e['condition']=='normal']
        ax=axes[line,0]
        for i,col in enumerate(['#14618c','#bd5d0a']):
            pts=[truth[e['case']][i] for e in route]
            ax.plot(*zip(*[p[:2] for p in pts]),color=col,label=f'Car {i+1}')
            ax.scatter(*pts[0][:2],c=col,marker='o');ax.scatter(*pts[-1][:2],c=col,marker='x')
        ax.legend();ax.set_aspect('equal',adjustable='datalim');ax.set(xlabel='moon_map x (m)',ylabel='moon_map y (m)',title=f'{segment} | antenna reference tracks')
        for i,car in enumerate('ps'):
            ax=axes[line,i+1]
            for method,condition,color,ls in [('P4','normal','#14618c','-'),('P4','ramp_only','#db671b',':'),('N4','normal','#694f9d','--')]:
                group=[r for r in rows if (r['route'],r['method'],r['condition'],r['car'],r['AL'])==(segment,method,condition,car,'1/10')]
                t=[float(r['scene_state_s']) for r in group]
                pl=[float(r['retrospective_PL_m']) for r in group]
                ax.plot(t,pl,color=color,ls=ls,label=f'{method} {condition}')
            ax.plot(t,[float(r['error_m']) for r in group],color='#394339',label='causal fix error')
            ax.axhline(.1,color='grey',lw=1,label='primary AL')
            arrivals=[r for r in group if r['alarm']=='True']
            ax.scatter([float(r['scene_ready_s']) for r in arrivals],[.1]*len(arrivals),
                       marker='x',color='#a82920',label='N4 alarm arrival')
            ax.text(.99,.02,'Normal N4 available ticks: '+str(sum(v['available']=='True' for v in csv.DictReader((D/'delivery_ticks.csv').open()) if (v['route'],v['condition'],v['method'],v['car'],v['AL'])==(segment,'normal','N4',car,'1/10')))+'/'+str(len(group)),ha='right',va='bottom',transform=ax.transAxes,fontsize=8)
            ax.set(xlabel='synthetic state time (s)',ylabel='horizontal distance (m)',title=f'{segment} | Car {i+1} | post-run PL')
            if line==0 and i==0:ax.legend(fontsize=8)
    fig.savefig(D/'route_monitor.png',dpi=155)
    for key in sorted({(r['route'],r['condition'],r['method'],r['car'],r['AL']) for r in rows}):
        g=[r for r in rows if tuple(r[k] for k in ['route','condition','method','car','AL'])==key]
        summaries.append(dict(zip(['route','condition','method','car','AL'],key),n=len(g),available=sum(r['available']=='True' for r in g),alarm=sum(r['alarm']=='True' for r in g),late=sum(r['late']=='True' for r in g),covered=sum(r['covered']=='True' for r in g),PL_min=min(float(r['retrospective_PL_m']) for r in g),PL_max=max(float(r['retrospective_PL_m']) for r in g),max_error=max(float(r['error_m']) for r in g)))
    save_csv('summary.csv',summaries)

if __name__=='__main__':render()
