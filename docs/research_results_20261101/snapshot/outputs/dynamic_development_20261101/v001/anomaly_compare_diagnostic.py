import evaluate_stops as e
import numpy as np
out=e.HERE/'anomaly_audit001';cfg=e.read(e.HERE/'B1/config.json')
ref=e.read(e.FIELD/'B1_B_reference.json');windows=e.read(e.HERE/'STOP_COMPARISON.json')['rows']
lo,hi=next(r['window_ns'] for r in windows if r['case']=='B1' and r['phase']=='B')
data={c:e.read(out/(c+'.json')) for c in ('baseline','diagnostic_remove_car1_node10')};result=[]
for car in e.CARS:
    selected=[i for i,r in enumerate(data['baseline']) if lo<=r['state_ns']<=hi and all(data[c][i]['valid'][car] for c in data)]
    row={'car':car,'common_valid_frames':len(selected),'reference_xy_m':ref[car+'_antenna_xy_m']}
    for c in data:
        pts=np.array([e.antenna(data[c][i],car,cfg) for i in selected]);err=pts-np.array(ref[car+'_antenna_xy_m'])
        row[c]={'rmse_m':float(np.sqrt(np.mean(np.sum(err**2,axis=1)))),'mean_antenna_xy_m':pts.mean(axis=0).tolist()}
    result.append(row)
(out/'DIAGNOSTIC_STOP_COMPARISON.json').write_text(e.json.dumps({'scope':'post-hoc diagnostic only; not a tuned method or validation','rows':result},indent=2)+'\n',encoding='utf-8');print(e.json.dumps(result))
