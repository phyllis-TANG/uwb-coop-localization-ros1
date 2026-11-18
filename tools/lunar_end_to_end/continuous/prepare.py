"""Freeze supported route, artificial anchors and paired simulation observations."""
import gzip,json,math
import numpy as np
from coverage import DOC,ART,OLD,write,sha,csvwrite,query,interp

def digest(x):
 import hashlib
 return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def state(data,t):
 q=np.stack([interp(data,t+shift) for shift in [5,0]],axis=1);q[:,:,2]=query(data,q[:,:,:2].reshape(-1,2))[0].reshape(len(t),2)+1.16
 yaw=np.stack([np.interp(t+shift,data['gt_t'],np.unwrap(data['gt_yaw'])) for shift in [5,0]],axis=1)
 return q,yaw

def main():
 audit=json.loads((DOC/'COVERAGE_AUDIT.json').read_text());a,b=audit['candidates'][0]['longest_pass'];assert b-a>=1
 data=np.load(ART/'scene_augmented.npz');assert sha(ART/'scene_augmented.npz')==audit['source_scene_sha256'];N=math.ceil((b-a)/.2)+1;times=np.linspace(0,b-a,N);q,yaw=state(data,a+times);dense=np.round(np.arange(a,b+.001,.02),8);qd,yd=state(data,dense)
 mid=q[:,:,:2].mean((0,1));span=np.maximum(np.ptp(q[:,:,:2],axis=(0,1))/2+8,[10,8]);anchors=np.array([[mid[0]+i*span[0],mid[1]+j*span[1],1.16] for i,j in [(-1,-1),(-1,1),(1,-1),(1,1)]])
 route=dict(source_times_car2_s=[a,b],source_times_car1_s=[a+5,b+5],duration_s=b-a,times_s=times.tolist(),sampling_dt_s=float(times[1]),xyz_m=q.tolist(),yaw_rad=yaw.tolist(),dense_times_s=(dense-a).tolist(),dense_xyz_m=qd.tolist(),dense_yaw_rad=yd.tolist(),anchors_xyz_m=anchors.tolist(),coordinate_frame='moon_map x-forward y-left z-up, meters',body_pose='world-upright procedural proxy: source yaw only; center at terrain+0.20m',antenna_arm_body_m=[0,0,.96],body_dimensions_m=[.8,.6,.4],scene_sha256=sha(ART/'scene_augmented.npz'))
 write(DOC/'ROUTE.json',route)
 rows=[]
 for i,t in enumerate(dense):
  for c in range(2):rows.append(dict(relative_time_s=float(t-a),source_time_s=float(t+(5 if c==0 else 0)),car=c+1,body_x_m=qd[i,c,0],body_y_m=qd[i,c,1],body_z_m=qd[i,c,2]-.96,qw=np.cos(yd[i,c]/2),qx=0,qy=0,qz=np.sin(yd[i,c]/2),antenna_x_m=qd[i,c,0],antenna_y_m=qd[i,c,1],antenna_z_m=qd[i,c,2],peer_distance_m=np.linalg.norm(qd[i,1]-qd[i,0])))
 csvwrite(DOC/'POSES.csv',rows)
 # Crop a single connected grid, keeping the observed mask for every terrain vertex.
 xy=qd[:,:,:2].reshape(-1,2);lo=np.maximum(np.floor((xy.min(0)-2-data['low'])/.4).astype(int),0);hi=np.minimum(np.ceil((xy.max(0)+2-data['low'])/.4).astype(int),np.asarray(data['terrain'].shape)-1);sl=tuple(slice(x,y+1) for x,y in zip(lo,hi));np.savez_compressed(DOC/'terrain.npz',terrain=data['terrain'][sl],observed=data['observed'][sl],low=data['low']+lo*.4,res=.4)
 protocol=dict(base_sha='591354134e4390812a1e8fad71873d5b13d75fc9',route_sha256=sha(DOC/'ROUTE.json'),terrain_sha256=sha(DOC/'terrain.npz'),conditions=['normal','ramp_only','motion_only','both'],seeds=list(range(2026111801,2026111811)),methods=['M0','M2','M3'],main_runs=120,ramp_total_m=.30,ramp_slope_m_s=.30/(b-a),motion_anomaly_car=2,motion_anomaly_increment_index=(N-1)//2,motion_anomaly_vector_rule='0.15m along source yaw on exactly one increment',sigma_range_m=.04,sigma_motion_m=.02,sigma_prior_m=.5,ar1_rho=.8,optional='40 paired records: original M3 vs rho=.8 whitened M3, white/correlated zero-bias inputs, 10 seeds; 10 main M3 records reused, only 30 additional executions',optimizer='two fixed trf calls max_nfev=150,100; no retry; strict gradient<=1e-5, full scaled rank',max_method_wall_seconds=30,max_matrix_wall_seconds=3600,reference_use='generation and evaluation only; no reference, labels or seeds in estimator API')
 write(DOC/'PROTOCOL.json',protocol)
 records=[]
 for condition in protocol['conditions']+['correlated_optional']:
  for seed in protocol['seeds']:
   rng=lambda k:np.random.default_rng(np.random.SeedSequence([seed,k]));z=rng(2).normal(size=(N-1,2,2));e=z.copy()
   if condition=='correlated_optional':
    for i in range(1,N-1):e[i]=.8*e[i-1]+.6*z[i]
   e*=.02
   if condition in ('motion_only','both'):
    i=protocol['motion_anomaly_increment_index'];e[i,1]+=.15*np.array([np.cos(yaw[i,1]),np.sin(yaw[i,1])])
   bias=np.linspace(0,.3,N) if condition in ('ramp_only','both') else np.zeros(N);ranges=np.column_stack([np.linalg.norm(q[:,:,None]-anchors[None,None],axis=3).reshape(N,8),np.linalg.norm(q[:,1]-q[:,0],axis=1)+bias]);noise=.04*rng(1).normal(size=(N,9));prior=q[0,:,:2]+.5*rng(3).normal(size=(2,2));ident=digest(dict(route=protocol['route_sha256'],condition=condition,seed=seed))[:24]
   o=dict(id=ident,times_s=times.tolist(),anchors=anchors.tolist(),heights=q[:,:,2].tolist(),ranges=(ranges+noise).tolist(),increments=(np.diff(q[:,:,:2],axis=0)+e).tolist(),prior=prior.tolist(),sigma_range=.04,sigma_motion=.02,sigma_prior=.5)
   ref=dict(id=ident,condition=condition,seed=seed,xyz=q.tolist(),bias=bias.tolist(),true_slope_m_s=float((bias[-1]-bias[0])/(b-a)),motion_error=e.tolist(),range_noise=noise.tolist())
   records.append(dict(observation=o,reference=ref,input_sha256=digest(o)))
 (DOC/'INPUTS.json.gz').write_bytes(gzip.compress(json.dumps(records,sort_keys=True).encode(),mtime=0));print(json.dumps(dict(route=[a,b],duration=b-a,samples=N,dt=times[1],ramp_slope=protocol['ramp_slope_m_s'],inputs=len(records))))
if __name__=='__main__':main()
