"""Separate evaluation stage; references never enter pipeline.prepare/run."""
import argparse,math
from pathlib import Path
import numpy as np
import pipeline as p
METHODS=('M2','M3','M3W025');CARS=('car1','car2')
def antenna(row,c,cfg):
    i=4*CARS.index(c);x,y,a=row['pose'][i:i+3];lx,ly=cfg['models'][c]['base_to_antenna_body_xy_m']
    return np.array([x+math.cos(a)*lx-math.sin(a)*ly,y+math.sin(a)*lx+math.cos(a)*ly])
def compare(rows,cfg,reference,windows):
    assert all([r['state_ns'] for r in rows[m]]==[r['state_ns'] for r in rows['M2']] for m in METHODS)
    result=[]
    for w in windows:
        phase=w['phase'];lo=w['start_ns'];hi=w['end_ns'];idx=[i for i,r in enumerate(rows['M2']) if lo<=r['state_ns']<=hi]
        for c in CARS:
            truth=np.array(reference[phase][c],float);assert truth.shape==(2,) and np.isfinite(truth).all()
            shared=[i for i in idx if all(rows[m][i]['valid'][c] and rows[m][i]['pose'] is not None for m in METHODS)]
            r=dict(phase=phase,car=c,scheduled_frames=len(idx),common_valid_frames=len(shared),own_valid_frames={m:sum(rows[m][i]['valid'][c] for i in idx) for m in METHODS},methods={},paired={})
            if shared:
                pts={m:np.array([antenna(rows[m][i],c,cfg) for i in shared]) for m in METHODS}
                for m in METHODS:
                    norm=np.linalg.norm(pts[m]-truth,axis=1)
                    r['methods'][m]={'rmse_m':float(np.sqrt(np.mean(norm**2))),'median_m':float(np.median(norm)),'p95_m':float(np.percentile(norm,95))}
                for m in METHODS[1:]:
                    value=float(np.mean(np.sum((pts[m]-truth)**2-(pts['M2']-truth)**2,axis=1)))
                    radius=math.sqrt(2)*.02;span=2*radius*float(np.linalg.norm((pts[m]-pts['M2']).mean(axis=0)))
                    r['paired'][m+'-M2']={'mean_squared_error_difference_m2':value,'sensitivity_interval_m2':[value-span,value+span],'direction':'improve' if value+span<0 else 'harm' if value-span>0 else 'unresolved'}
            else:r['unavailable_metrics']=None
            result.append(r)
    return result
def evaluate(reference_path):
    p.check_lock();plan=p.read(p.HERE/'PROTOCOL.json');refs=p.read(reference_path);output=[];receipts={}
    for u in plan['units']:
        unit=u['unit'];base=p.HERE/'runs'/unit
        for w in u['evaluation_windows']:
            ref=refs[unit][w['phase']];source=u['reference_sources'][w['phase']]
            if ref['source_path']!=source['path'] or ref['source_sha256']!=source['sha256'] or p.sha(source['path'])!=source['sha256']:raise ValueError('reference source changed')
        if not (base/'INPUT_LOCK.json').exists():
            output.append({'unit':unit,'status':'UNAVAILABLE_PREPARATION','windows':u['evaluation_windows'],'metrics':None});continue
        for file,h in p.read(base/'INPUT_LOCK.json').items():
            if p.sha(file)!=h:raise ValueError('prepared file changed')
        rows={}
        for m in METHODS:
            status=p.read(base/m/'RUN_STATUS.json');trajectory=base/m/'trajectory.json'
            if p.sha(trajectory)!=status['trajectory_sha256']:raise ValueError('output changed')
            rows[m]=p.read(trajectory);receipts[str(trajectory)]=p.sha(trajectory)
        reference={phase:{c:r[c] for c in CARS} for phase,r in refs[unit].items()}
        output.extend(dict(unit=unit,**r) for r in compare(rows,p.read(base/'config.json'),reference,u['evaluation_windows']))
    target=p.HERE/'RESERVED_RESULTS.json'
    if target.exists():raise FileExistsError('do not overwrite revealed results')
    p.write(target,{'scope':'frozen conditional confirmation; no continuous moving truth','reference_file_sha256':p.sha(reference_path),'trajectory_sha256':receipts,'rows':output})
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--references',type=Path,required=True);evaluate(parser.parse_args().references)
