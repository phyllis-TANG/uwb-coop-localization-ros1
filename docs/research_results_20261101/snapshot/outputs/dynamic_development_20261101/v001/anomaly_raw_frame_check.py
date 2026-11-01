import dynamic_compare as d
import gzip,json,importlib.util
import numpy as np
base=d.HERE/'B1';out=d.HERE/'anomaly_audit001'
with gzip.open(base/'bins.jsonl.gz','rt',encoding='utf-8') as f:bins=[json.loads(l) for l in f]
lo=bins[250]['state_ns'];hi=bins[530]['state_ns'];ranges={}
with gzip.open(base/'sensor_records.jsonl.gz','rt',encoding='utf-8') as f:
    for l in f:
        r=json.loads(l)
        if r['topic']=='/car1/uwb/ranges' and lo-10**9<=r['receive_epoch_ns']<=hi+10**9:ranges[r['header_epoch_ns']]=r
path=d.PROJECT/'outputs/field_measurements_20261031/v001/P00_QC/bag_decoder_snapshot.py'
spec=importlib.util.spec_from_file_location('audit_raw_decoder',path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
bag=d.Path(d.read(base/'input_audit.json')['bag_path']);assert d.sha(bag)==d.read(base/'input_audit.json')['bag_sha256']
con,msgs=mod.load_bag(bag);cids=[k for k,v in con.items() if v['topic']=='/car1/uwb/frame3'];assert cids
dec={k:mod.Decoder(con[k]['type'],con[k]['definition']) for k in cids};checked=0;unmatched=0;maxdiff=0.;radio=[];examples=[]
for cid,rt,payload in msgs:
    if cid not in dec or not lo<=rt<=hi:continue
    frame=json.loads(dec[cid].decode(payload,con[cid]['type'])['data'])
    stamp=frame['stamp_secs']*10**9+frame['stamp_nsecs'];r=ranges.get(stamp)
    if r is None:unmatched+=1;continue
    for node in frame['nodes']:
        key='node_'+str(node['node_id'])
        if key in r['value']:maxdiff=max(maxdiff,abs(node['distance_m']-r['value'][key]));checked+=1
        if key=='node_10':
            radio.append([rt,node['distance_m'],node['fp_rssi_db'],node['rx_rssi_db']])
            if len(examples)<3 or (rt>=bins[500]['state_ns'] and len(examples)<6):examples.append({'receipt_ns':rt,'header_ns':stamp,'node':node,'packet_hex':frame['packet_hex']})
assert maxdiff<1e-6
summ=[]
for a,b in ((250,290),(300,350),(380,430),(483,528)):
    v=np.array([x[1:] for x in radio if bins[a]['state_ns']<=x[0]<=bins[b]['state_ns']]);summ.append({'indices':[a,b],'samples':len(v),'median_distance_fp_rx':np.median(v,axis=0).tolist()})
result={'bag_sha256':d.sha(bag),'matched_link_values':checked,'unmatched_raw_frames':unmatched,'max_raw_to_ranges_difference_m':maxdiff,'node10_window_statistics':summ,'raw_examples':examples,'interpretation':'raw Frame3 decoded distances already contain change; excludes offline binning as creator, does not establish RF fault cause'}
d.write(out/'RAW_FRAME_CHECK.json',result);print(json.dumps({k:v for k,v in result.items() if k!='raw_examples'}),flush=True)
