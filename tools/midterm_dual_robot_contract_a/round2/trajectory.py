"""Ground HCPL replay. The causal estimator receives only sensor packets and survey."""
import argparse
import bisect
import csv
import gzip
import hashlib
import io
import json
import math
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from statistics import NormalDist

import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ground_hcpl'))
import example as ref
sys.path.insert(0,str(ROOT/'docs/research/midterm_sim_review/round1/ground'))
from replay_tta import excursions,classify

THRESHOLD=21.665994333461924
VERSIONS=('original','axis','history')
PRIMARY='history'
CARS=ref.CARS
NS=10**9


def blob(sha,path):
    return subprocess.check_output(['git','show',f'{sha}:{path}'],cwd=ROOT)


def groups(raw,config):
    buckets={t:{} for t in range(1,64)}
    previous=-1
    for line in gzip.decompress(raw).splitlines():
        e=json.loads(line)
        received=e['receive_epoch_ns']
        if received<previous:
            raise ValueError('unordered arrivals')
        previous=received
        t,part=divmod(e['header_epoch_ns']-config['epoch_ns'],NS)
        if part or t not in buckets or e['kind'] not in ('odom','uwb') or e['vehicle_id'] not in CARS:
            continue
        if received<e['header_epoch_ns']:
            raise ValueError('noncausal timestamp')
        if received>e['header_epoch_ns']+NS:
            continue
        key=(e['vehicle_id'],e['kind'])
        if key in buckets[t]:
            raise ValueError('duplicate frame')
        buckets[t][key]=e
    return buckets


class Filter:
    def __init__(self,config):
        self.models=config['models']
        self.x=np.r_[np.concatenate([self.models[c]['start_antenna_xyz_m'][:2] for c in CARS]),np.zeros(9)]
        self.P=np.diag([.2**2]*4+[.3**2]*9)
        self.transfer=np.zeros((13,0))
        self.origin=None
        self.offset=np.zeros(4)
        self.last=1
        self.accepted=None

    def step(self,t,frames):
        if any((c,'odom') not in frames for c in CARS) or (self.origin is None and t!=1):
            self.accepted=False
            return dict(action='MISSING_ODOM_OR_SURVEY_REFERENCE',cars=None,range_reaccepted=False)
        odom=[frames[c,'odom']['value']['pose'] for c in CARS]
        if t==1:
            self.origin=odom
        offset=np.concatenate([ref.antenna_offset(o,r,self.models[c]) for c,o,r in zip(CARS,odom,self.origin)])
        self.x+=np.r_[offset-self.offset,np.zeros(9)]
        self.P=self.P+(t-self.last)*ref.Q
        self.offset,self.last=offset,t
        current=np.zeros((13,9))
        stat=None
        action='MISSING_RANGE'
        if all((c,'uwb') in frames for c in CARS):
            anchors=self.models['car1']['anchors_xyz_m']
            ids=sorted(anchors)
            obs=[frames[c,'uwb']['value'][k] for c in CARS for k in ids]
            obs.append(frames['car1','uwb']['value']['node_0'])
            pred,H=ref.geometry(self.x,dict(anchors=[anchors[k] for k in ids],
                                   heights=[self.models[c]['antenna_height_m'] for c in CARS]))
            innovation=obs-pred
            S=H@self.P@H.T+ref.R
            stat=float(innovation@np.linalg.solve(S,innovation))
            action='ACCEPT' if stat<=THRESHOLD else 'REJECT'
            if action=='ACCEPT':
                current=np.linalg.solve(S,H@self.P).T
                A=np.eye(13)-current@H
                self.x+=current@innovation
                self.P=A@self.P@A.T+current@ref.R@current.T
                self.transfer=np.column_stack((A@self.transfer,current))
        recovered=self.accepted is False and action=='ACCEPT'
        self.accepted=action=='ACCEPT'
        cars=[]
        for i in range(2):
            sl=slice(i*2,i*2+2)
            sigma=np.sqrt(np.diag(self.P)[sl])
            levels={}
            for v in VERSIONS:
                B=.02*np.abs((self.transfer if v=='history' else current)[sl]).sum(axis=1)
                k=NormalDist().inv_cdf(1-(.01 if v=='original' else .005)/2)
                # Rejected/missing measurements provide no new measurement-based PL.
                levels[v]=float(np.linalg.norm(B+k*sigma)) if self.accepted else None
            cars.append(dict(xy=self.x[sl].tolist(),hcpl=levels,sigma=sigma.tolist(),
                             history_B=(.02*np.abs(self.transfer[sl]).sum(axis=1)).tolist()))
        return dict(action=action,stat=stat,cars=cars,range_reaccepted=recovered,
                    bias=self.x[4:].tolist(),covariance_diag=np.diag(self.P).tolist())


def replay(raw,config):
    if config['prior_state_s']!=1 or config['raw_range_sigma_m']!=.04:
        raise ValueError('incompatible survey or noise')
    f=Filter(config)
    epochs=[]
    ready=0
    for t,frames in groups(raw,config).items():
        times=[(e['receive_epoch_ns']-config['epoch_ns'])/NS for e in frames.values()]
        arrival=max(times) if len(frames)==4 else None
        start=max(ready,arrival if arrival is not None else t+1)
        tic=time.perf_counter_ns()
        r=f.step(t,frames)
        elapsed=(time.perf_counter_ns()-tic)/NS
        ready=start+elapsed
        epochs.append(dict(t=t,ids=[e['source_observation_id'] for e in frames.values()],
                           receipts=times,all_arrived=arrival,start=start,service=elapsed,finish=ready,
                           ready=ready,expiry=t+2,first_display=None,**r))
    return epochs


def display(epochs):
    ticks=[]
    arrivals=[e['ready'] for e in epochs]
    for i in range(1280):
        now=i/20
        idx=bisect.bisect_right(arrivals,now)-1
        e=epochs[idx] if idx>=0 else None
        valid=e is not None and now<=e['expiry']
        if valid and e['first_display'] is None:
            e['first_display']=now
        for car in (0,1):
            state=e['cars'][car] if valid and e['cars'] else None
            statuses={}
            for v in VERSIONS:
                if state is None:
                    status='NO_DECISION'
                elif e['action']=='REJECT':
                    status='ALARM'
                elif state['hcpl'][v] is None:
                    status='NO_DECISION'
                else:
                    status='ALARM' if state['hcpl'][v]>.10 else 'AVAILABLE'
                statuses[v]=status
            ticks.append(dict(t=now,car=car+1,state_time=e['t'] if valid else None,
                              xy=state['xy'] if state else None,status=statuses))
    return ticks


def score(ticks,truth):
    if len(truth)!=1280 or len(ticks)!=2560:
        raise ValueError('denominator')
    summary=[]
    events=[]
    for car in (1,2):
        for v in VERSIONS:
            rows=[]
            for i,r in enumerate(ticks[car-1::2]):
                error='' if r['xy'] is None else str(math.dist(r['xy'],truth[i][car-1]))
                rows.append(dict(status=r['status'][v],error_m=error))
            counts=Counter(r['status'] for r in rows)
            episodes=excursions(rows)
            summary.append(dict(car=car,variant=v,ticks=len(rows),seconds=len(rows)/20,
                                available_s=counts['AVAILABLE']/20,alarm_s=counts['ALARM']/20,
                                no_decision_s=counts['NO_DECISION']/20,
                                exceed_available_s=sum(e['exposed'] for e in episodes)/20))
            for n,e in enumerate(episodes):
                for limit in (1,2,5):
                    events.append(dict(car=car,variant=v,episode=n,start=e['start']/20,
                        alarm=None if e['alarm'] is None else e['alarm']/20,
                        limit=limit,outcome=classify(e,e['start']+20*limit,rows)))
    return summary,events


def main():
    p=argparse.ArgumentParser()
    for name in ('sha','runtime','seed','scene','out'):
        p.add_argument(name)
    a=p.parse_args()
    config=blob(a.sha,a.runtime+'/geometry.json')
    raw=blob(a.sha,a.runtime+'/events.jsonl.gz')
    if 'ground_b_round2' in a.runtime:
        sums=blob(a.sha,a.runtime+'/SHA256SUMS').decode().splitlines()
        expected={name:sha for sha,name in (line.split() for line in sums)}
        for name,data in [('geometry.json',config),('events.jsonl.gz',raw)]:
            if hashlib.sha256(data).hexdigest()!=expected[name]:
                raise ValueError('B runtime hash mismatch')
    epochs=replay(raw,json.loads(config))
    ticks=display(epochs)
    # Strictly post-hoc, after all decisions have been generated.
    path=f'docs/research/ground_continuous_b/runs/{a.seed}_{a.scene}/truth.json.gz'
    truth=json.loads(gzip.decompress(blob(ref.EVALUATION_SHA,path)))
    summary,events=score(ticks,truth)
    out=Path(a.out)
    out.mkdir(parents=True,exist_ok=True)
    for name,data in [('epochs',epochs),('ticks',ticks),('tta',events)]:
        (out/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(data,allow_nan=False,separators=(',',':')).encode(),mtime=0))
    meta=dict(seed=a.seed,scene=a.scene,input_sha=a.sha,runtime=a.runtime,
              hashes={k:hashlib.sha256(v).hexdigest() for k,v in [('geometry.json',config),('events.jsonl.gz',raw)]},
              epochs=len(epochs),vehicle_ticks=len(ticks),actions=dict(Counter(e['action'] for e in epochs)),
              summary=summary)
    (out/'summary.json').write_text(json.dumps(meta,indent=2)+'\n')


if __name__=='__main__':
    main()
