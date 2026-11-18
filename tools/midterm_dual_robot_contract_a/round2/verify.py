"""Independent post-hoc readback. No imports from the estimator or either scorer."""
import gzip
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
TRUTH_SHA = '01e588021e7e3ddd918b1d1fc9561973373758c6'
VERSIONS = ('original', 'axis', 'history')


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def rebuild(car, version, rows, truth):
    status = [r['status'][version] for r in rows]
    error = [None if r['xy'] is None else math.dist(r['xy'], xy)
             for r, xy in zip(rows, truth, strict=True)]
    counts = Counter(status)
    exposed = sum(s == 'AVAILABLE' and e is not None and e > .10 for s, e in zip(status, error))
    summary = dict(car=car, variant=version, ticks=len(rows), seconds=len(rows)/20,
                   available_s=counts['AVAILABLE']/20, alarm_s=counts['ALARM']/20,
                   no_decision_s=counts['NO_DECISION']/20, exceed_available_s=exposed/20)
    events = []
    intervals = []
    start = None
    alarm = None
    # A missing position neither starts nor closes an observable excursion.
    for tick in range(len(rows) + 1):
        eof = tick == len(rows)
        if not eof and error[tick] is None:
            continue
        if not eof and error[tick] > .10:
            if start is None:
                start = tick
            if alarm is None and status[tick] == 'ALARM':
                alarm = tick
            continue
        if start is None:
            continue
        episode = len(intervals)
        intervals.append((start, tick, alarm))
        for limit in (1, 2, 5):
            deadline = start + 20*limit
            if alarm is not None and alarm <= deadline:
                outcome = 'timely_alarm'
            elif not eof and tick <= deadline:
                outcome = 'recovered_before_or_at_deadline'
            elif deadline >= len(rows):
                outcome = 'right_censored_before_deadline'
            elif error[deadline] is None:
                outcome = 'no_position_at_deadline'
            elif status[deadline] == 'AVAILABLE':
                outcome = 'exceed_available_at_deadline'
            else:
                outcome = 'exceed_withheld_at_deadline'
            events.append(dict(car=car, variant=version, episode=episode, start=start/20,
                               alarm=None if alarm is None else alarm/20, limit=limit, outcome=outcome))
        start = alarm = None
    return summary, events, intervals


def audit(epochs, ticks, events, meta, truth, survey=None):
    need(len(epochs)==meta['epochs']==63 and len(ticks)==meta['vehicle_ticks']==2560 and len(truth)==1280,'run denominator')
    previous_finish = 0
    last_prediction = 1
    diag = np.array([.2**2]*4 + [.3**2]*9)
    bias = [0.]*9
    previous_accepted = None
    reference = False
    first = {}
    for t,e in enumerate(epochs,1):
        ids = e['ids']
        allowed = {f'{c}:{k}:{20*t}' for c in ('car1','car2') for k in ('uwb','odom')}
        need(e['t']==t and len(set(ids))==len(ids)==len(e['receipts']) and set(ids)<=allowed,'frame identity')
        need(all(t<=r<=t+1 for r in e['receipts']), 'receipt cutoff')
        arrival = max(e['receipts']) if len(ids)==4 else None
        need(e['all_arrived']==arrival and e['start']==max(previous_finish,arrival if arrival is not None else t+1),'input clock')
        need(e['service']>0 and e['finish']==e['ready']==e['start']+e['service'] and e['expiry']==t+2,'output clock')
        previous_finish=e['ready']
        odom=sum(':odom:' in k for k in ids)==2
        reference |= t==1 and odom
        if not odom or not reference:
            expected='MISSING_ODOM_OR_SURVEY_REFERENCE'
        elif len(ids)<4:
            expected='MISSING_RANGE'
        else:
            need(math.isfinite(e['stat']) and e['stat']>=0,'innovation')
            expected='ACCEPT' if e['stat']<=21.665994333461924 else 'REJECT'
        need(e['action']==expected and e['range_reaccepted']==(previous_accepted is False and expected=='ACCEPT'),'action/recovery')
        previous_accepted=expected=='ACCEPT'
        if expected=='MISSING_ODOM_OR_SURVEY_REFERENCE':
            need(e['cars'] is None,'missing odometry publication')
            continue
        if expected!='ACCEPT':
            need(e['bias']==bias and all(all(v is None for v in c['hcpl'].values()) for c in e['cars']), 'fallback update')
            np.testing.assert_allclose(e['covariance_diag'],diag+(t-last_prediction)*np.array([.03**2]*4+[.01**2]*9),rtol=0,atol=1e-12)
            if t==1 and survey is not None:
                np.testing.assert_allclose([c['xy'] for c in e['cars']],survey,rtol=0,atol=1e-12)
        else:
            need(all(math.isfinite(c['hcpl'][v]) and c['hcpl'][v]>=0 for c in e['cars'] for v in VERSIONS),'accepted PL')
        bias,diag,last_prediction=e['bias'],np.array(e['covariance_diag']),t
    need(Counter(e['action'] for e in epochs)==meta['actions'],'action denominator')
    for j,r in enumerate(ticks):
        now,car=(j//2)/20,j%2
        need(r['t']==now and r['car']==car+1,'tick identity')
        e=next((e for e in reversed(epochs) if e['ready']<=now),None)
        if e and e['expiry']<now:
            e=None
        state=e['cars'][car] if e and e['cars'] else None
        need(r['state_time']==(e['t'] if e else None) and r['xy']==(state['xy'] if state else None),'displayed pair')
        if e:
            first.setdefault(e['t'],now)
        for v in VERSIONS:
            label='NO_DECISION'
            if state and e['action']=='REJECT':
                label='ALARM'
            elif state and state['hcpl'][v] is not None:
                label='AVAILABLE' if state['hcpl'][v]<=.10 else 'ALARM'
            need(r['status'][v]==label,'display declaration')
    need(all(first.get(e['t'])==e['first_display'] for e in epochs),'first display')
    summaries, rebuilt=[],[]
    for car in (1,2):
        for v in VERSIONS:
            summary, rows, _=rebuild(car,v,ticks[car-1::2],[p[car-1] for p in truth])
            summaries.append(summary)
            rebuilt.extend(rows)
    need(meta['summary']==summaries,'per-car summary or denominator')
    need(events==rebuilt,'TTA rows differ in identity, multiplicity, timing or classification')


def blob(sha,path):
    return subprocess.check_output(['git','show',f'{sha}:{path}'],cwd=ROOT)


def verify(folder):
    def read(name):
        return json.loads(gzip.decompress((folder/(name+'.json.gz')).read_bytes()))
    meta=json.loads((folder/'summary.json').read_text())
    need(folder.name==f"{meta['seed']}_{meta['scene']}",'run identity')
    truth=json.loads(gzip.decompress(blob(TRUTH_SHA,f'docs/research/ground_continuous_b/runs/{folder.name}/truth.json.gz')))
    geometry=json.loads(blob(meta['input_sha'],meta['runtime']+'/geometry.json'))
    survey=[geometry['models'][c]['start_antenna_xyz_m'][:2] for c in ('car1','car2')]
    audit(read('epochs'),read('ticks'),read('tta'),meta,truth,survey)
    return meta['scene']


if __name__=='__main__':
    stage=Path(sys.argv[1])
    seeds={'dev':('101',),'holdout':('2026111901','2026111902')}
    paths=sorted(stage.iterdir())
    if stage.name in seeds:
        expected={s+'_'+scene for s in seeds[stage.name] for scene in ('nominal','peer_step','peer_ramp','wall')}
        need({p.name for p in paths}==expected,'stage run denominator')
    for path in paths:
        print(path.name,verify(path),'PASS')
