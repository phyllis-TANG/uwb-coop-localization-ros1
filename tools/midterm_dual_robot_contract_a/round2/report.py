"""Render archived clock results, post-hoc fault windows and paired B2 comparison."""
import csv
import gzip
import io
import json
from collections import Counter,defaultdict
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trajectory import ROOT,PRIMARY,VERSIONS,blob,ref,groups,Filter
from replay_tta import validate_ticks

D=ROOT/'docs/research/midterm_dual_robot_contract_a/round2'
def load(path):
    return json.loads(gzip.decompress(path.read_bytes()))
def save(name,rows):
    with (D/name).open('w') as f:
        w=csv.DictWriter(f,rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)

summary=[]
transitions=[]
b2=[]
tta=defaultdict(Counter)
for stage in ('dev','holdout'):
    for folder in sorted((D/stage).iterdir()):
        meta=json.loads((folder/'summary.json').read_text())
        ep=load(folder/'epochs.json.gz')
        ticks=load(folder/'ticks.json.gz')
        seed,scene=folder.name.split('_',1)
        tag=dict(stage=stage,seed=seed,scene=scene)
        summary.extend([{**tag,**r} for r in meta['summary']])
        for e in load(folder/'tta.json.gz'):
            tta[stage,e['car'],e['variant'],e['limit']][e['outcome']]+=1
        for car in (1,2):
            rows=ticks[car-1::2]
            def first_tick(condition):
                return next((r['t'] for r in rows if condition(r)),None)
            rejects=[e['t'] for e in ep if e['action']=='REJECT']
            transitions.append(dict(**tag,car=car,reject_epochs=' '.join(map(str,rejects)),
                reaccept_epochs=' '.join(str(e['t']) for e in ep if e['range_reaccepted']),
                first_alarm=first_tick(lambda r:r['status'][PRIMARY]=='ALARM'),
                first_reject_alarm=first_tick(lambda r:r['state_time'] in rejects and r['status'][PRIMARY]=='ALARM'),
                first_accept_after_clear=next((e['t'] for e in ep if scene!='nominal' and e['t']>=38 and e['action']=='ACCEPT'),None),
                first_available_after_clear=first_tick(lambda r:scene!='nominal' and r['t']>=38 and r['status'][PRIMARY]=='AVAILABLE')))
        if stage=='holdout':
            path='docs/research/ground_continuous_b/runs/'+folder.name+'/'
            def source(name):
                return gzip.decompress(blob(ref.EVALUATION_SHA,path+name))
            records=json.loads(source('records.json.gz'))
            truth=json.loads(source('truth.json.gz'))
            archived=list(csv.DictReader(io.StringIO(source('ticks.csv.gz').decode())))
            for car in (1,2):
                rows=[r for r in archived if r['method']=='B2' and r['view']=='delivery' and int(r['car'])==car and float(r['AL_m'])==.10]
                validate_ticks(rows,car,records,truth)
                counts=Counter(r['status'] for r in rows)
                b2.append(dict(**tag,car=car,ticks=len(rows),available_s=counts['AVAILABLE']/20,alarm_s=counts['ALARM']/20,
                               no_decision_s=(1280-counts['AVAILABLE']-counts['ALARM'])/20,
                               exceed_available_s=sum(r['status']=='AVAILABLE' and float(r['error_m'])>.1 for r in rows)/20))
save('per_run.csv',summary)
save('recovery.csv',transitions)
save('b2_clock.csv',b2)
fields=('ticks','seconds','available_s','alarm_s','no_decision_s','exceed_available_s')
aggregate=[]
for car in (1,2):
    for v in VERSIONS:
        rows=[r for r in summary if r['stage']=='holdout' and (r['car'],r['variant'])==(car,v)]
        aggregate.append(dict(car=car,variant=v,**{k:round(sum(r[k] for r in rows),6) for k in fields}))
save('per_car_holdout.csv',aggregate)
from replay_tta import OUTCOMES
save('tta_summary.csv',[dict(stage=s,car=c,variant=v,deadline_s=limit,events=sum(count.values()),
                           **{k:count[k] for k in OUTCOMES}) for (s,c,v,limit),count in sorted(tta.items())])

# Recompute development decisions from every raw prefix up to the two excerpts.
for scene,stamps in [('nominal',(9,10)),('wall',(23,24,25,37,38,39))]:
    folder=D/'dev'/('101_'+scene)
    meta=json.loads((folder/'summary.json').read_text())
    raw=blob(meta['input_sha'],meta['runtime']+'/events.jsonl.gz')
    cfg=json.loads(blob(meta['input_sha'],meta['runtime']+'/geometry.json'))
    model=Filter(cfg)
    epochs=load(folder/'epochs.json.gz')
    ticks=load(folder/'ticks.json.gz')
    trace=[]
    for t,frames in groups(raw,cfg).items():
        got=model.step(t,frames)
        archived=epochs[t-1]
        assert got['action']==archived['action']
        if t in stamps:
            import numpy as np
            for a,b in zip(got['cars'],archived['cars']):
                np.testing.assert_allclose(a['xy'],b['xy'],atol=1e-12,rtol=0)
                for v in VERSIONS:
                    if a['hcpl'][v] is None: assert b['hcpl'][v] is None
                    else: assert abs(a['hcpl'][v]-b['hcpl'][v])<1e-12
            trace.append(dict(frames=list(frames.values()),epoch=archived,
                              first_display=[r for r in ticks if r['t']==archived['first_display']]))
    (D/(scene+'_excerpt.json')).write_text(json.dumps(trace,indent=2)+'\n')

folder=D/'dev/101_wall'
ep=load(folder/'epochs.json.gz')
ticks=load(folder/'ticks.json.gz')[::2]
fig,axes=plt.subplots(3,1,figsize=(10,6),sharex=True,layout='constrained')
for ax in axes:
    ax.axvspan(24,38,color='#f8db97',alpha=.55)
axes[0].plot([e['t'] for e in ep],[e['stat'] for e in ep],'.-',lw=1)
axes[0].axhline(21.665994333461924,color='#b43e35',ls='--')
axes[0].set_ylabel('Innovation statistic')
axes[1].step([e['t'] for e in ep],[int(e['action']=='ACCEPT') for e in ep],where='post')
axes[1].set_yticks([0,1],['Rejected','Accepted'])
axes[1].annotate('Range updates resume',(38,1),xytext=(42,.55),arrowprops={'arrowstyle':'->'})
axes[2].step([r['t'] for r in ticks],[{'NO_DECISION':0,'ALARM':1,'AVAILABLE':2}[r['status'][PRIMARY]] for r in ticks],where='post')
axes[2].set_yticks([0,1,2],['No decision','Alarm','Available'])
axes[2].set(xlabel='Replay time (s)',ylabel='Car 1 display')
axes[0].set_title('Development seed 101 · wall injection [24, 38) s · history-adjusted HCPL')
fig.savefig(D/'wall_timeline.png',dpi=160)
