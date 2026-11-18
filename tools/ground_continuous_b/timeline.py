"""Two time bases, 20 Hz left-endpoint duration and alert episode accounting."""
import argparse
import csv
import gzip
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from fractions import Fraction
from a_interface import check_radius,identity

DOC=Path(__file__).resolve().parents[2]/'docs/research/ground_continuous_b'
CFG=json.loads((DOC/'config.json').read_text())
METHODS=('B2','aug','region')
def load(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def csvout(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
def evaluate(seed,scene):
    from audit import validate
    path=DOC/'runs'/f'{seed}_{scene}'
    records=load(path/'records.json.gz')
    truth=load(path/'truth.json.gz')
    finish=dict.fromkeys((*METHODS,'graph'),0.)
    stamps=[];public=[]
    for r in records:
        t=r['t'];obs=r['obs']
        assert len(obs['ranges'])==9 and t<=obs['received']<=r['cutoff']
        start=time.perf_counter()
        validate(r)
        tree_wall=time.perf_counter()-start
        radius=check_radius(r)
        check_s=time.perf_counter()-start
        finish['graph']=max(r['cutoff'],finish['graph'])+r['graph_cost']
        finish['B2']=max(r['cutoff'],finish['B2'])+r['b2_cost']
        finish['aug']=max(obs['received'],finish['aug'])+r['aug_cost']
        finish['region']=max(obs['received'],finish['graph'],finish['region'])+r['region_cost']+check_s
        stamps.append(finish.copy())
        for c in (0,1):
            public.append(dict(case=f'{seed}_{scene}_{t}',seed=seed,car=('p','s')[c],state_time=t,estimate_xy=json.dumps([str(Fraction(x)) for x in r['xy'][c]]),decision_ready_time=finish['region'],AL=CFG['primary_AL_m'],as_of=finish['region'],deadline=t+2,valid_until=t+2,published_at=finish['graph'],input_hash=identity(obs),frame='ground_sim_xy_z_up',mode='4d',A_corner_radius_m=radius[c],B_candidate_PL_m=r['region']['pl'][c],G1_accepted=r['pub_ready'],B_readback_s=tree_wall,A_radius_wall_s_pair=check_s-tree_wall))
    csvout(path/'publications.csv',public)
    stats=defaultdict(lambda:dict(available=0,alarm=0,unavailable_without_alarm=0,exceed_available=0))
    episodes=[];active={}
    def close(k):
        if k in active:episodes.append(active.pop(k))
    with gzip.open(path/'ticks.csv.gz','wt') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow('view,time_s,car,method,AL_m,state_s,ready_s,x_m,y_m,error_m,PL_m,status'.split(','))
        latest=dict.fromkeys(METHODS,-1)
        for n in range(1280):
            now=n/20
            for method in METHODS:
                while latest[method]+1<len(records) and stamps[latest[method]+1][method]<=now:
                    latest[method]+=1
                for view in ('state','delivery'):
                    idx=int(now)-1 if view=='state' else latest[method]
                    r=records[idx] if idx>=0 else None
                    for c in (0,1):
                        xy=None;pl=None;ready=False;alarm=False;reason='STARTUP';error=None
                        if r:
                            t=r['t'];readytime=stamps[idx][method]
                            pos=r['aug']['xy'][c] if method=='aug' else r['xy'][c]
                            posok=r['aug']['ready'] if method=='aug' else r['pub_ready']
                            if view=='delivery' and (now>t+2 or readytime>t+2):
                                reason='EXPIRED' if readytime<=t+2 else 'LATE'
                            else:
                                if posok or method != 'aug':
                                    xy=pos
                                    error=math.dist(pos,truth[t*20 if view=='state' else n][c])
                                if method=='B2':
                                    decl=r['b2'][c];ready=posok and decl['computable'];alarm=decl['alarm']
                                elif method=='aug':
                                    ready=posok;alarm=r['aug']['alarm']
                                else:
                                    pl=r['region']['pl'][c] if posok else None
                                    ready=pl is not None
                                reason='EMPTY' if method=='region' and posok and pl is None else 'NO_DECISION'
                        for al in CFG['AL_m']:
                            status=('ALARM' if (alarm or (pl is not None and pl>al)) else 'AVAILABLE') if ready else reason
                            key=(view,c+1,method,al)
                            s=stats[key]
                            s['available']+=status=='AVAILABLE';s['alarm']+=status=='ALARM'
                            s['unavailable_without_alarm']+=status not in ('ALARM','AVAILABLE')
                            above=error is not None and error>al
                            s['exceed_available']+=above and status=='AVAILABLE'
                            if above:
                                ep=active.setdefault(key,dict(view=view,car=c+1,method=method,AL_m=al,start_s=now,end_exclusive_s=None,first_alarm_s=None,delay_s=None))
                                ep['end_exclusive_s']=(n+1)/20
                                if ep['first_alarm_s'] is None and status=='ALARM':
                                    ep['first_alarm_s']=now;ep['delay_s']=round(now-ep['start_s'],2)
                            else:close(key)
                            w.writerow([view,now,c+1,method,al,r['t'] if r else '',stamps[idx][method] if r else '',*(xy or ('','')),error,pl,status])
    for k in list(active):close(k)
    csvout(path/'episodes.csv',episodes)
    rows=[]
    for (v,c,m,a),s in stats.items():
        same=[e for e in episodes if (e['view'],e['car'],e['method'],e['AL_m'])==(v,c,m,a)]
        rows.append(dict(seed=seed,scene=scene,view=v,car=c,method=m,AL_m=a,**{k+'_s':n/20 for k,n in s.items()},exceed_episodes=len(same),never_alarm=sum(e['delay_s'] is None for e in same),first_episode_delay_s=same[0]['delay_s'] if same else None))
    csvout(path/'summary.csv',rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('seed',type=int);p.add_argument('scene');a=p.parse_args();evaluate(a.seed,a.scene)
