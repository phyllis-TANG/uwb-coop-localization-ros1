"""Extend the coordinator's frozen B2 vehicle-clock evaluation to all paired runs."""
import csv
import gzip
import json
import sys
from collections import Counter
import subprocess
from pathlib import Path
from verify_inputs import ROOT, DOC, OLD, SEEDS, SCENES

REFERENCE=ROOT/'docs/research/midterm_sim_review/round1/ground'
sys.path.insert(0,str(REFERENCE))
import replay_tta as reference

OUT=DOC/'evaluation'
WINDOWS={'full':(0,64),'fault':(24,38),'recovery':(38,48)}
RATE=reference.RATE


def table(path):
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as f:
        return list(csv.DictReader(f))


def save(name,rows):
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)


def first(rows,start,end,predicate):
    return next((i for i in range(start,end) if predicate(rows[i])),None)


def evaluate():
    summaries=[];details=[];ticks=[];marks=[];wall=[]
    for seed in SEEDS[1:]:
        for scene in SCENES:
            folder=OLD/f'{seed}_{scene}'
            for name in ('records.json.gz','truth.json.gz','ticks.csv.gz'):
                source=folder/name
                pinned=subprocess.check_output(['git','show',reference.SOURCE+':'+str(source.relative_to(ROOT))],cwd=ROOT)
                reference.require(source.read_bytes()==pinned, f'Archive changed: {source}')
            with gzip.open(folder/'records.json.gz','rt') as f:
                records=json.load(f)
            with gzip.open(folder/'truth.json.gz','rt') as f:
                truth=json.load(f)
            raw=table(folder/'ticks.csv.gz')
            for car in (1,2):
                key=dict(seed=seed,scene=scene,car=car)
                rows=[r for r in raw if r['car']==str(car) and r['view']=='delivery' and
                      r['method']=='B2' and float(r['AL_m'])==reference.AL]
                reference.validate_ticks(rows,car,records,truth)
                events=reference.excursions(rows)
                ticks.extend(dict(**key,**{k:v for k,v in r.items() if k!='car'}) for r in rows)
                if scene=='wall':
                    wall.append(reference.wall_window(rows,events,seed,car))
                for label,(lo,hi) in WINDOWS.items():
                    a,b=lo*RATE,hi*RATE
                    span=rows[a:b]
                    def above(r):
                        return bool(r['error_m']) and float(r['error_m'])>reference.AL
                    start=first(rows,a,b,above)
                    alarm=first(rows,a,b,lambda r:r['status']=='ALARM')
                    available=first(rows,a,b,lambda r:r['status']=='AVAILABLE')
                    within=first(rows,a,b,lambda r:r['error_m'] and not above(r))
                    marks.append(dict(**key,window=label,first_exceed_s=reference.seconds(start),
                        status_at_first=rows[start]['status'] if start is not None else '',
                        first_alarm_tick_s=reference.seconds(alarm),first_alarm_release_s=rows[alarm]['ready_s'] if alarm is not None else '',
                        first_available_s=reference.seconds(available),first_within_AL_s=reference.seconds(within)))
                    for limit in reference.LIMITS:
                        counts=Counter()
                        for e in events:
                            if a<=e['start']<b:
                                counts[reference.classify(e,e['start']+limit*RATE,rows)]+=1
                        starts=[e for e in events if a<=e['start']<b]
                        summaries.append(dict(**key,window=label,tta_s=limit,ticks=len(span),episodes=len(starts),
                            overlap_episodes=sum(e['start']<b and e['end']>a for e in events),
                            available_at_start=sum(e['initial']=='AVAILABLE' for e in starts),
                            alarmed_anytime=sum(e['alarm'] is not None for e in starts),
                            available_s=sum(r['status']=='AVAILABLE' for r in span)/RATE,
                            alarm_s=sum(r['status']=='ALARM' for r in span)/RATE,
                            expired_s=sum(r['status']=='EXPIRED' for r in span)/RATE,
                            no_position_s=sum(not r['error_m'] for r in span)/RATE,
                            exceed_available_s=sum(above(r) and r['status']=='AVAILABLE' for r in span)/RATE,
                            **{k:counts[k] for k in reference.OUTCOMES}))
                for n,e in enumerate(events,1):
                    i,j=e['start'],e['end']
                    alarm=e['alarm']
                    expire=first(rows,i,j,lambda r:r['status']=='EXPIRED')
                    loss=next((k for k in range(i+1,j) if rows[k-1]['status']=='AVAILABLE' and rows[k]['status']!='AVAILABLE'),None)
                    held=first(rows,i,j,lambda r:r['status']!='AVAILABLE')
                    again=first(rows,held+1,j+int(j<len(rows)),lambda r:r['status']=='AVAILABLE') if held is not None else None
                    for limit in reference.LIMITS:
                        deadline=i+RATE*limit
                        details.append(dict(**key,episode=n,first_exceed_s=i/RATE,status_at_start=e['initial'],
                          stop_s=j/RATE,stop_reason=e['reason'],first_alarm_s=reference.seconds(alarm),
                          alarm_release_s=rows[alarm]['ready_s'] if alarm is not None else '',
                          already_alarmed=e['initial']=='ALARM',first_expired_s=reference.seconds(expire),
                          first_loss_available_s=reference.seconds(loss),available_again_s=reference.seconds(again),
                          stop_status=rows[j]['status'] if j<len(rows) else '',record_end_s=64,
                          tta_s=limit,deadline_s=deadline/RATE,outcome=reference.classify(e,deadline,rows),
                          available_exceed_s=e['exposed']/RATE))
    assert len(ticks)==20480
    save('vehicle_ticks.csv',ticks)
    save('summary.csv',summaries)
    save('events_by_tta.csv',details)
    save('window_markers.csv',marks)
    save('wall_window.csv',wall)
    grouped=[]
    for scene in SCENES:
        for window in WINDOWS:
            for limit in reference.LIMITS:
                rr=[r for r in summaries if (r['scene'],r['window'],r['tta_s'])==(scene,window,limit)]
                assert len(rr)==4
                counts={k:sum(r[k] for r in rr) for k in reference.OUTCOMES}
                denominator=sum(r['episodes'] for r in rr)
                assert sum(counts.values())==denominator
                grouped.append(dict(scene=scene,window=window,tta_s=limit,independent_seeds=2,
                    vehicle_ticks=sum(r['ticks'] for r in rr),episodes=denominator,**counts))
    save('scenario_tta.csv',grouped)
    # Exact replay of every column and row of the nominal/wall round-one output.
    for name in ('summary.csv','events_by_tta.csv','wall_window.csv'):
        before=table(REFERENCE/'results'/name)
        after=[r for r in table(OUT/name) if r.get('scene','wall') in ('wall','nominal') and r.get('window','full')=='full']
        assert Counter(tuple(r[k] for k in before[0]) for r in after)==Counter(tuple(r.values()) for r in before), name


if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    evaluate()
