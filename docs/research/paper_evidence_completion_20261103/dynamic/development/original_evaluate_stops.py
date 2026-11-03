"""Read saved trajectories only; no optimizer, no held-out cases."""
from pathlib import Path
from decimal import Decimal
import json, math, hashlib
import numpy as np
HERE=Path(__file__).resolve().parent
FIELD=HERE.parents[2]/'outputs/field_measurements_20261101/v001'
METHODS=('M2','M3','M3W025')
CARS=('car1','car2')
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def antenna(row,car,cfg):
    i=4*CARS.index(car); x,y,yaw=row['pose'][i:i+3]
    lx,ly=cfg['models'][car]['base_to_antenna_body_xy_m']
    return np.array([x+math.cos(yaw)*lx-math.sin(yaw)*ly,y+math.sin(yaw)*lx+math.cos(yaw)*ly])
def main():
    results=[];sources={}; max_identity=0.
    for case in ('A1','B1'):
        base=HERE/case;cfg=read(base/'config.json')
        trajectories={m:read(base/m/'trajectory.json') for m in METHODS}
        for m in METHODS:
            p=base/m/'trajectory.json';sources[str(p)]=digest(p)
        assert all([r['state_ns'] for r in trajectories[m]]==[r['state_ns'] for r in trajectories['M2']] for m in METHODS)
        bag=Path(read(base/'input_audit.json')['bag_path'])
        eventpath=Path(str(bag)+'.events.txt');sources[str(eventpath)]=digest(eventpath)
        events={label:int(Decimal(t)*10**9) for t,label in (line.split(' ',1) for line in eventpath.read_text().splitlines())}
        for phase in ('START','B','C','RETURN'):
            lo=events[f'{case}_{phase}_STABLE_BEGIN']
            ends=[v for k,v in events.items() if k.startswith(f'{case}_{phase}_STABLE_END')];assert len(ends)==1
            hi=ends[0]
            if case=='A1' and phase=='START':
                ref={'car1_antenna_xy_m':[1.51,3.99],'car2_antenna_xy_m':[2.02,2.01]}
                refpath=Path(str(bag)+'.notes.txt')
                assert 'Car2=(2.02,2.01)' in refpath.read_text()
            else:
                refpath=FIELD/f'{case}_{phase}_reference.json';ref=read(refpath)
            sources[str(refpath)]=digest(refpath)
            idx=[i for i,r in enumerate(trajectories['M2']) if lo<=r['state_ns']<=hi]
            for car in CARS:
                common=[i for i in idx if all(trajectories[m][i]['valid'][car] for m in METHODS)]
                entry=dict(case=case,phase=phase,car=car,role='moving' if car==('car2' if case=='A1' else 'car1') else 'fixed',
                           reference_xy_m=ref[car+'_antenna_xy_m'],window_ns=[lo,hi],scheduled_frames=len(idx),common_valid_frames=len(common),
                           own_valid_frames={m:sum(trajectories[m][i]['valid'][car] for i in idx) for m in METHODS},methods={},paired={})
                if common:
                    truth=np.array(ref[car+'_antenna_xy_m']);pts={m:np.array([antenna(trajectories[m][i],car,cfg) for i in common]) for m in METHODS}
                    for m in METHODS:
                        err=pts[m]-truth; norm=np.linalg.norm(err,axis=1)
                        entry['methods'][m]={'rmse_m':float(np.sqrt(np.mean(norm**2))),'median_m':float(np.median(norm)),'p95_m':float(np.percentile(norm,95)),'mean_error_xy_m':err.mean(axis=0).tolist()}
                    for m in METHODS[1:]:
                        a=pts[m]-truth;b=pts['M2']-truth;delta=pts[m]-pts['M2'];value=float(np.mean(np.sum(a*a-b*b,axis=1)))
                        identity=float(np.mean(np.sum(delta*(pts[m]+pts['M2']-2*truth),axis=1)))
                        max_identity=max(max_identity,abs(identity-value));assert abs(identity-value)<1e-10
                        radius=math.sqrt(2)*.02;span=2*radius*float(np.linalg.norm(delta.mean(axis=0)))
                        # Independent reference perturbation endpoint check of the affine bound.
                        direction=delta.mean(axis=0); n=np.linalg.norm(direction)
                        if n:
                            extrem=[]
                            for s in (-1,1):
                                shifted=truth+s*radius*direction/n
                                extrem.append(float(np.mean(np.sum((pts[m]-shifted)**2-(pts['M2']-shifted)**2,axis=1))))
                            assert np.allclose(sorted(extrem),[value-span,value+span],atol=1e-10,rtol=1e-10)
                        entry['paired'][m+'-M2']={'mean_squared_error_difference_m2':value,'reference_ball_radius_m':radius,'sensitivity_interval_m2':[value-span,value+span],'direction':'improve' if value+span<0 else 'harm' if value-span>0 else 'unresolved'}
                results.append(entry)
    report={'scope':'conditional development; all recorded stable windows; common three-method valid times; no continuous moving truth',
            'reference_sensitivity':'operator estimate conservatively modeled as 2cm per axis / sqrt(2)*2cm ball, not certified bound; same fixed reference perturbation within each stop',
            'start_policy':'first 5s used for range initialization; evaluate all subsequent scheduled stable states, including warmup in coverage denominator; no post-hoc trimming',
            'max_pair_identity_error':max_identity,'source_hashes':sources,'rows':results}
    (HERE/'STOP_COMPARISON.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    for r in results:
        print(r['case'],r['phase'],r['car'],f"{r['common_valid_frames']}/{r['scheduled_frames']}", ' '.join(f"{m}={v['rmse_m']*100:.2f}cm" for m,v in r['methods'].items()),r['paired'])
if __name__=='__main__':main()
