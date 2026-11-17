"""Read-only ROS1 field observation readiness audit. No optimizer/ROS runtime."""
import argparse,csv,gzip,hashlib,json,math,sys,collections,bisect,subprocess,importlib.metadata
from pathlib import Path
import numpy as np
from rosbags.highlevel import AnyReader
ROOT=Path(__file__).resolve().parents[2]
IDS=['013206','015334','033248','050447','045116']
TAG={'car1':'node_1','car2':'node_0'};PEER={'car1':'node_0','car2':'node_1'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def clean(v):return float(v) if np.isfinite(v) else None
def describe(v):
 a=np.asarray(v,dtype=float);a=a[np.isfinite(a)]
 return dict(n=len(a),median=float(np.median(a)) if len(a) else None,p05=float(np.percentile(a,5)) if len(a) else None,p95=float(np.percentile(a,95)) if len(a) else None,min=float(a.min()) if len(a) else None,max=float(a.max()) if len(a) else None)
def writecsv(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def pair(a,b,limit_ns):
 # One-to-one greedy smallest receipt gap; no physical synchronization claim.
 ts=[x['receipt_ns'] for x in b];edges=[]
 for i,x in enumerate(a):
  lo=bisect.bisect_left(ts,x['receipt_ns']-limit_ns);hi=bisect.bisect_right(ts,x['receipt_ns']+limit_ns)
  edges.extend((abs(ts[j]-x['receipt_ns']),i,j) for j in range(lo,hi))
 useda=set();usedb=set();out=[]
 for gap,i,j in sorted(edges):
  if i not in useda and j not in usedb:useda.add(i);usedb.add(j);out.append((i,j,gap))
 return out
def valid_range(row,link):
 vals=[x['range_m'] for x in row['ranges'] if x['anchor_id']==link]
 return vals[0] if len(vals)==1 and vals[0] is not None and vals[0]>0 else None
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 catalog=list(csv.DictReader((ROOT/'datasets/field_raw/catalog.csv').open()));selected=[next(r for r in catalog if r['filename'].endswith('_'+id+'.bag')) for id in IDS]
 topics=[];cars=[];links=[];pairs=[];source=[];cross=[]
 for id,item in zip(IDS,selected):
  path=ROOT/'datasets/field_raw'/item['archive_path'];digest=sha(path);assert digest==item['sha256'];out=a.out/id;out.mkdir();streams=collections.defaultdict(list);counts=collections.Counter();types={}
  with AnyReader([path]) as reader:
   origin=int(reader.start_time);duration=reader.duration*1e-9
   for conn,ns,raw in reader.messages():
    counts[conn.topic]+=1;types[conn.topic]=conn.msgtype
    if not any(conn.topic.startswith('/'+c+'/') for c in TAG):continue
    if conn.msgtype not in ['nav_msgs/msg/Odometry','sensor_msgs/msg/Imu'] and not conn.topic.endswith('/uwb/ranges'):continue
    msg=reader.deserialize(raw,conn.msgtype);h=msg.header;row=dict(topic=conn.topic,receipt_ns=int(ns),header_ns=int(h.stamp.sec)*10**9+int(h.stamp.nanosec),frame_id=h.frame_id)
    if conn.msgtype=='nav_msgs/msg/Odometry':
     pos=msg.pose.pose.position;q=msg.pose.pose.orientation;row.update(kind='odom',position_m=[clean(x) for x in [pos.x,pos.y,pos.z]],quaternion_xyzw=[clean(x) for x in [q.x,q.y,q.z,q.w]],linear_mps=[clean(x) for x in [msg.twist.twist.linear.x,msg.twist.twist.linear.y,msg.twist.twist.linear.z]],angular_rps=[clean(x) for x in [msg.twist.twist.angular.x,msg.twist.twist.angular.y,msg.twist.twist.angular.z]],child_frame_id=msg.child_frame_id)
    elif conn.msgtype=='sensor_msgs/msg/Imu':
     row.update(kind='imu',gyro_rps=[clean(x) for x in [msg.angular_velocity.x,msg.angular_velocity.y,msg.angular_velocity.z]],accel_mps2=[clean(x) for x in [msg.linear_acceleration.x,msg.linear_acceleration.y,msg.linear_acceleration.z]],orientation_covariance=[clean(x) for x in msg.orientation_covariance],gyro_covariance=[clean(x) for x in msg.angular_velocity_covariance])
    else:
     row.update(kind='uwb',tag_id=msg.tag_id,ranges=[dict(anchor_id=x.anchor_id,range_m=clean(x.range),quality=clean(x.quality)) for x in msg.ranges]);assert msg.tag_id==TAG[conn.topic.split('/')[1]]
    streams[conn.topic].append(row)
  with gzip.open(out/'measurements.jsonl.gz','wt') as f:
   for topic in sorted(streams):
    for row in streams[topic]:f.write(json.dumps(row,allow_nan=False)+'\n')
  for topic,count in counts.items():
   rows=streams.get(topic,[]);rr=np.array([x['receipt_ns'] for x in rows],dtype=np.int64);hh=np.array([x['header_ns'] for x in rows],dtype=np.int64)
   topics.append(dict(case=id,topic=topic,type=types[topic],count=count,decoded=len(rows),frames=';'.join(sorted({x['frame_id'] for x in rows})),header_minus_receipt_median_ms=float(np.median(hh-rr)*1e-6) if len(rows) else None,header_backward=int(np.sum(np.diff(hh)<0)) if len(rows) else None,header_duplicate=int(np.sum(np.diff(hh)==0)) if len(rows) else None,receipt_max_gap_ms=float(np.max(np.diff(rr))*1e-6) if len(rows)>1 else None))
  allmotion={}
  for car in TAG:
   od=streams['/'+car+'/odom'];uw=streams['/'+car+'/uwb/ranges'];imu=[x for rr in streams.values() for x in rr if x['topic'].startswith('/'+car+'/') and x['kind']=='imu'];assert od and uw and imu
   xy=np.array([x['position_m'][:2] for x in od]);assert np.isfinite(xy).all();tt=np.array([(x['receipt_ns']-origin)*1e-9 for x in od]);tw=np.array([x['linear_mps'][:2] for x in od]);motion=tt[np.linalg.norm(tw,axis=1)>.02];allmotion[car]=set(np.floor(motion).astype(int));peer=[valid_range(x,PEER[car]) for x in uw]
   cars.append(dict(case=id,car=car,duration_s=duration,odom_count=len(od),imu_count=len(imu),uwb_frames=len(uw),peer_valid=sum(x is not None for x in peer),odom_path_m=float(np.linalg.norm(np.diff(xy,axis=0),axis=1).sum()),odom_displacement_m=float(np.linalg.norm(xy[-1]-xy[0])),motion_bins_over_002mps=len(allmotion[car]),motion_first_s=float(motion[0]) if len(motion) else None,motion_last_s=float(motion[-1]) if len(motion) else None,imu_nonfinite_gyro=sum(any(v is None for v in x['gyro_rps']) for x in imu),imu_covariance_all_zero=sum(all(v==0 for v in x['gyro_covariance']) for x in imu),both_motion_bins=None))
   for link in sorted({v['anchor_id'] for x in uw for v in x['ranges']}):
    vv=[valid_range(x,link) for x in uw];finite=[v for v in vv if v is not None];st=describe(finite);links.append(dict(case=id,car=car,link=link,frames=len(uw),valid=len(finite),invalid_or_missing=len(uw)-len(finite),duplicate_frames=sum(sum(v['anchor_id']==link for v in x['ranges'])>1 for x in uw),quality_finite=sum(v['quality'] is not None for x in uw for v in x['ranges'] if v['anchor_id']==link),**{'range_'+k:v for k,v in st.items()}))
  overlap=len(allmotion['car1']&allmotion['car2'])
  for row in cars[-2:]:row['both_motion_bins']=overlap
  aa=[x for x in streams['/car1/uwb/ranges'] if valid_range(x,PEER['car1']) is not None];bb=[x for x in streams['/car2/uwb/ranges'] if valid_range(x,PEER['car2']) is not None]
  for ms in [5,10,20,30,50]:
   matched=pair(aa,bb,ms*10**6);hd=[(bb[j]['header_ns']-aa[i]['header_ns'])*1e-6 for i,j,g in matched];rd=[valid_range(bb[j],PEER['car2'])-valid_range(aa[i],PEER['car1']) for i,j,g in matched]
   pairs.append(dict(case=id,tolerance_ms=ms,car1_available=len(aa),car2_available=len(bb),matched=len(matched),unmatched_car1=len(aa)-len(matched),unmatched_car2=len(bb)-len(matched),**{'header_delta_'+k:v for k,v in describe(hd).items()},**{'range_delta_'+k:v for k,v in describe(rd).items()}))
  # Check against frozen old reader without invoking any solver. Shared rosbags means not an independent binary decoder.
  sys.path.insert(0,str(ROOT/'tools'));from two_car_updated_comparison import read_bag
  old=read_bag(path,digest)
  for car in TAG:
   assert len(old['odom'][car])==len(streams['/'+car+'/odom']);assert len(old['uwb'][car])==len(streams['/'+car+'/uwb/ranges'])
   for (ot,values),new in zip(old['uwb'][car],streams['/'+car+'/uwb/ranges']):
    assert abs(ot-(new['receipt_ns']-origin)*1e-9)<5e-7
    current={v['anchor_id']:valid_range(new,v['anchor_id']) for v in new['ranges']};current={k:v for k,v in current.items() if v is not None};assert current==values
  cross.append(dict(case=id,raw_uwb_values_and_counts_match_legacy=True,integer_timestamp_difference_tolerance_s=5e-7,independent_binary_decoder=False))
  reference=dict(catalog=item,continuous_truth=None,source='catalog and same-day notes; historical evidence, not independently surveyed this run');dump(out/'reference.json',reference);assert sha(path)==digest
  source.append(dict(case=id,path=str(path.relative_to(ROOT)),sha256=digest,bytes=path.stat().st_size,topics=dict(counts),all_messages=sum(counts.values()),bag_origin_ns=origin))
 writecsv(a.out/'TOPICS.csv',topics);writecsv(a.out/'CARS.csv',cars);writecsv(a.out/'LINKS.csv',links);writecsv(a.out/'PAIRING.csv',pairs);dump(a.out/'SOURCES.json',source);dump(a.out/'CROSSCHECK.json',cross)
 dump(a.out/'RUN.json',dict(code_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),argv=sys.argv,packages={x:importlib.metadata.version(x) for x in ['numpy','scipy','rosbags']},cases=len(source),all_messages=sum(x['all_messages'] for x in source),decoded_messages=sum(x['decoded'] for x in topics),optimizer_calls=0,formal_runs=0,source_unchanged=True,all_selected_cases_retained=True))
 print(json.dumps(cars,indent=2))
if __name__=='__main__':main()
