import gzip,json,math
import numpy as np
import evaluate_stops as e
b=e.HERE/'B1';cfg=e.read(b/'config.json');methods=e.METHODS
rows={m:e.read(b/m/'trajectory.json') for m in methods}
comp=e.read(e.HERE/'STOP_COMPARISON.json');stop=next(r for r in comp['rows'] if r['case']=='B1' and r['phase']=='B' and r['car']=='car1')
lo,hi=stop['window_ns'];truth=np.array(stop['reference_xy_m'])
idx=[i for i,r in enumerate(rows['M2']) if lo<=r['state_ns']<=hi]
summ={}
for m in methods:
    selected=[rows[m][i] for i in idx];pts=np.array([e.antenna(r,'car1',cfg) for r in selected]);poses=np.array([r['pose'] for r in selected])
    summ[m]={'n_all_stop':len(idx),'rmse_all_finite_m':float(np.sqrt(np.mean(np.sum((pts-truth)**2,axis=1)))),
             'antenna_xy_min':pts.min(axis=0).tolist(),'antenna_xy_max':pts.max(axis=0).tolist(),'yaw_min_max_rad':[float(poses[:,2].min()),float(poses[:,2].max())],
             'bias_min_max_rad_s':[float(poses[:,3].min()),float(poses[:,3].max())]}
dis=[float(np.linalg.norm(e.antenna(a,'car1',cfg)-e.antenna(c,'car1',cfg))) for a,c in zip(rows['M3W025'],rows['M2'])]
first=next(i for i,v in enumerate(dis) if v>1.)
target=set([rows['M2'][i]['state_ns'] for i in range(max(0,first-2),min(len(dis),first+3))]+[rows['M2'][idx[0]]['state_ns'],rows['M2'][idx[-1]]['state_ns']])
details=[]
with gzip.open(b/'M3W025/updates.jsonl.gz','rt',encoding='utf-8') as f:
    for l in f:
        item=json.loads(l)
        if item['state_ns'] not in target:continue
        r=item['result'];details.append({'state_ns':item['state_ns'],'status':r['status'],'optimizer':r['optimizer'],'pose':r['pose'],'prediction_pose':r['prediction_pose'],'rank':r['numerical_rank'],'dimension':8*r['graph_states'],'angular_valid':r['angular_valid']})
out={'scope':'saved-output diagnosis only; no refit or alternate parameters','stop_summary':summ,'first_weighted_vs_independent_displacement_over_1m_index':first,'details':details,'interpretation':'accepted/full-rank is numerical validity, not accuracy or physical consistency; mechanism not yet isolated'}
(e.HERE/'B1_WEIGHTED_ANOMALY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,ensure_ascii=False))
