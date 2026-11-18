"""Frozen gate, range/odometry model and 20 Hz scorer. Only calibration varies."""
import copy
import csv
import gzip
import io
import json
import math
from pathlib import Path
from statistics import NormalDist
import subprocess
import sys
import tempfile
from unittest.mock import patch
import numpy as np
from calibrate import ROOT,OUT,CARS,write_csv

FREEZE='efd9f9560de6d0661f5c3322dfa545515b51594d'
EVAL='01e588021e7e3ddd918b1d1fc9561973373758c6'


def blob(sha,name):
    return subprocess.check_output(['git','show',f'{sha}:{name}'],cwd=ROOT)


def frozen(tmp):
    names=['tools/midterm_dual_robot_contract_a/round2/trajectory.py','tools/midterm_dual_robot_contract_a/ground_hcpl/example.py','docs/research/midterm_sim_review/round1/ground/replay_tta.py']
    for name in names:
        p=tmp/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_bytes(blob(FREEZE,name))
    sys.path.insert(0,str((tmp/names[0]).parent))
    import trajectory
    return trajectory


def run(m,raw,cfg,model,arm):
    cfg=copy.deepcopy(cfg)
    stable=np.flatnonzero(model['stable']) if arm=='survey_links' else np.array([],dtype=int)
    keep=np.r_[np.arange(4),stable+4]
    if arm!='baseline':
        for i,c in enumerate(CARS):
            cfg['models'][c]['start_antenna_xyz_m'][:2]=model['mean'][2*i:2*i+2]
            cfg['models'][c]['initial_heading_deg']=model['mean_heading_deg'][i]
    class Calibrated(m.Filter):
        def __init__(self,c):
            super().__init__(c)
            if arm!='baseline':
                self.P[np.ix_(keep,keep)]=np.asarray(model['covariance'])[np.ix_(keep,keep)]
                self.x[stable+4]=np.asarray(model['mean'])[stable+4]
        def step(self,t,frames):
            # These inputs are verified complete. Fail closed if used on another archive.
            if len(frames)!=4 or t!=self.last+(t!=1):
                raise ValueError('expected complete integer-second frames')
            before=self.x.copy()
            P=self.P.copy()
            T=self.transfer
            # Use frozen code unchanged for baseline and survey-only.
            if len(stable)==0:
                return super().step(t,frames)
            odom=[frames[c,'odom']['value']['pose'] for c in CARS]
            if t==1:
                self.origin=odom
            offset=np.concatenate([m.ref.antenna_offset(o,r,self.models[c]) for c,o,r in zip(CARS,odom,self.origin)])
            before[:4]+=offset-self.offset
            self.offset,self.last=offset,t
            if t>1:
                Q=m.ref.Q.copy()
                Q[4+stable,4+stable]=0
                P+=Q
            meta=self.models['car1']['anchors_xyz_m']
            keys=sorted(meta)
            y=[frames[c,'uwb']['value'][k] for c in CARS for k in keys]+[frames['car1','uwb']['value']['node_0']]
            pred,H=m.ref.geometry(before,dict(anchors=[meta[k] for k in keys],heights=[self.models[c]['antenna_height_m'] for c in CARS]))
            innovation=y-pred
            S=H@P@H.T+m.ref.R
            stat=float(innovation@np.linalg.solve(S,innovation))
            ok=stat<=m.THRESHOLD
            if ok:
                K=np.linalg.solve(S,H@P).T
                K[4+stable]=0  # Schmidt nuisance states: fixed means, retain cross-covariances.
                A=np.eye(13)-K@H
                self.x=before+K@innovation
                self.P=A@P@A.T+K@m.ref.R@K.T
                self.transfer=np.column_stack((A@T,K))
            else:
                self.x,self.P=before,P
            recovered=self.accepted is False and ok
            self.accepted=ok
            cars=[]
            for i in range(2):
                sl=slice(2*i,2*i+2)
                sigma=np.sqrt(self.P.diagonal()[sl])
                prior_B=.02*np.abs(self.transfer[sl]).sum(axis=1)
                levels=dict.fromkeys(m.VERSIONS)
                if ok:
                    for v in m.VERSIONS:
                        B=prior_B if v=='history' else .02*np.abs(K[sl]).sum(axis=1)
                        levels[v]=float(np.linalg.norm(B+NormalDist().inv_cdf(1-(.01 if v=='original' else .005)/2)*sigma))
                cars.append(dict(xy=self.x[sl].tolist(),hcpl=levels,sigma=sigma.tolist(),history_B=prior_B.tolist()))
            return dict(action='ACCEPT' if ok else 'REJECT',stat=stat,cars=cars,range_reaccepted=recovered,
                        bias=self.x[4:].tolist(),covariance_diag=self.P.diagonal().tolist())
    with patch.object(m,'Filter',Calibrated):
        ep=m.replay(raw,cfg)
    return ep,m.display(ep)


def summary(scene,arm,car,rows):
    def exp(r):
        return r['status']=='AVAILABLE' and r['err']>.10
    wall=scene=='wall'
    phase=[r for r in rows if wall and 24<=r['t']<38]
    rec=next((r['t'] for r in rows if r['t']>=38 and r['status']=='AVAILABLE'),None)
    return dict(scene=scene,arm=arm,car=car,ticks=len(rows),available_s=sum(r['status']=='AVAILABLE' for r in rows)/20,
                later_available_s=sum(r['status']=='AVAILABLE' and r['state']>=2 for r in rows)/20,
                alarm_s=sum(r['status']=='ALARM' for r in rows)/20,exposed_s=sum(map(exp,rows))/20,
                fault_exposed_s=sum(map(exp,phase))/20 if wall else None,
                first_available_after_clear_s=rec if wall else None)


def main():
    model=json.loads((OUT/'calibration.json').read_text())
    results=[]
    with tempfile.TemporaryDirectory() as temp:
        m=frozen(Path(temp))
        for scene in ('nominal','wall'):
            package=ROOT/'docs/research/ground_b_round2/runtime'/('101_'+scene)
            cfg=json.loads((package/'geometry.json').read_text())
            raw=(package/'events.jsonl.gz').read_bytes()
            outputs={a:run(m,raw,cfg,model,a) for a in ('baseline','survey','survey_links')}
            path=f'docs/research/ground_continuous_b/runs/101_{scene}/'
            truth=json.loads(gzip.decompress(blob(EVAL,path+'truth.json.gz')))
            for arm,(ep,ticks) in outputs.items():
                for car in (1,2):
                    rows=[dict(t=r['t'],state=r['state_time'],status=r['status']['history'],
                               err=math.dist(r['xy'],truth[i][car-1]) if r['xy'] is not None else None)
                          for i,r in enumerate(ticks[car-1::2])]
                    results.append(summary(scene,arm,car,rows))
                (OUT/f'{scene}_{arm}.json.gz').write_bytes(gzip.compress(json.dumps(ep,separators=(',',':')).encode(),mtime=0))
            from replay_tta import validate_ticks
            records=json.loads(gzip.decompress(blob(EVAL,path+'records.json.gz')))
            b2=list(csv.DictReader(io.StringIO(gzip.decompress(blob(EVAL,path+'ticks.csv.gz')).decode())))
            for car in (1,2):
                samples=[r for r in b2 if r['view']=='delivery' and r['method']=='B2' and int(r['car'])==car and float(r['AL_m'])==.10]
                validate_ticks(samples,car,records,truth)
                rows=[dict(t=float(r['time_s']),state=float(r['state_s'] or 0),status=r['status'],
                           err=float(r['error_m']) if r['error_m'] else None) for r in samples]
                results.append(summary(scene,'B2',car,rows))
    write_csv('clock.csv',results)
    new=[r for r in results if r['arm']=='survey_links']
    gate=all(r['exposed_s']==0 and (r['later_available_s']>0 if r['scene']=='nominal' else r['first_available_after_clear_s'] is not None) for r in new)
    print('holdout admission',gate)

if __name__=='__main__':
    main()
