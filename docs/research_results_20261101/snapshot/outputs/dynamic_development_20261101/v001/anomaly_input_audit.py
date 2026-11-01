import dynamic_compare as d
import gzip,json
import numpy as np
base=d.HERE/'B1';out=d.HERE/'anomaly_audit001'
with gzip.open(base/'bins.jsonl.gz','rt',encoding='utf-8') as f:bins=[json.loads(l) for l in f]
rows=d.read(base/'M3W025/trajectory.json')
rates={};header=[]
with gzip.open(base/'sensor_records.jsonl.gz','rt',encoding='utf-8') as f:
    for l in f:
        r=json.loads(l)
        if r['topic']=='/car1/imu':
            rates[r['record_index']]=r
            if bins[200]['state_ns']<=r['receive_epoch_ns']<=bins[530]['state_ns']:header.append([r['receive_epoch_ns'],r['header_epoch_ns'],*r['value']])
max_angle_error=0.;checked=0
for b in bins[201:531]:
    v=b['intervals']['car1'];total=0;duration=0
    for s in v['segments']:
        raw=rates[s['dependency']['record_index']];assert raw['value'][2]==s['rate_rad_s']
        assert raw['receive_epoch_ns']==s['dependency']['mapped_header_epoch_ns']
        assert raw['availability_epoch_ns']==s['dependency']['receive_epoch_ns']
        assert s['dt_ns']==s['end_epoch_ns']-s['start_epoch_ns']
        total+=raw['value'][2]*(s['end_epoch_ns']-s['start_epoch_ns'])/1e9;duration+=s['dt_ns'];checked+=1
    gap=sum(g['end_epoch_ns']-g['start_epoch_ns'] for g in v['gaps']);assert duration+gap==v['dt_ns']
    max_angle_error=max(max_angle_error,abs(total-v['partial_angle_rad']))
header=np.array(header);window=[]
for start,end in ((0,50),(200,215),(230,250),(270,290),(300,320),(330,350),(380,400),(430,450),(483,528)):
    bb=bins[start:end+1];r={'indices':[start,end],'peer_median':float(np.median([b['peer'] for b in bb if b['peer'] is not None])),'cars':{}}
    for car in d.CARS:
        r['cars'][car]={k:float(np.median([b['wall'][car][k] for b in bb if k in b['wall'][car]])) for k in bb[0]['wall'][car]}
    window.append(r)
y=np.unwrap([r['pose'][2] for r in rows]);jumps=np.argsort(np.abs(np.diff(y))) [-12:]
data={'scope':'raw cached IMU vs cached segment integration; receipt association is not sensor sync validation',
      'segments_checked':checked,'max_angle_error_rad':max_angle_error,
      'car1_header_minus_receipt_s_min_median_max':np.percentile((header[:,1]-header[:,0])/1e9,[0,50,100]).tolist(),
      'car1_gyro_xyz_median_rad_s':np.median(header[:,2:],axis=0).tolist(),'range_medians':window,
      'largest_yaw_jumps':[{'index':int(i+1),'delta_rad':float(y[i+1]-y[i]),'state_ns':rows[i+1]['state_ns'],'status':rows[i+1]['status']} for i in jumps]}
d.write(out/'INPUT_AUDIT.json',data);print(json.dumps(data),flush=True)
