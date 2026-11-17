"""Audit local source frames and select windows without localization results."""
import csv,hashlib,json
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from scipy.ndimage import distance_transform_edt,gaussian_filter
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/'docs/research/lunar_end_to_end'; ART=Path('/home/ubuntu22/uwb-lunar-end-to-end-artifacts'); ART.mkdir(exist_ok=True)
def dump(p,x): p.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=Path('/home/ubuntu22/LuSNAR-reproduction/sample/Moon_1/gt.txt')
 rows=list(csv.reader(p.open()))[1:]; ns=np.array([int(r[0]) for r in rows],dtype=np.int64); gt=np.array([[float(v) for v in r[1:8]] for r in rows]); ts=(ns-ns[0])*1e-9
 C=np.diag([1.,-1.,-1.]); xyz=gt[:,:3]@C; rr=Rotation.from_quat(gt[:,[4,5,6,3]]); rots=C@rr.as_matrix()@C; yaw=Rotation.from_matrix(rots).as_euler('xyz')[:,2]
 files=sorted(Path('/home/ubuntu22/LuSNAR-reproduction/sample/Moon_1/LiDAR').glob('*.txt'))+sorted(Path('/home/ubuntu22/uwb-moon1-representativeness-artifacts/supplement001/sample/Moon_1/LiDAR').glob('*.txt'))
 cloud=[]; manifest=[dict(path=str(p),sha256=sha(p),role='reference',rows=len(ts))]
 for f in files:
  a=np.loadtxt(f,delimiter=',');a=a[np.isfinite(a).all(axis=1),:3];i=int(np.argmin(abs(ns-int(f.stem)))); w=((a+[1,0,-1.5])@rr.as_matrix()[i].T+gt[i,:3])@C; cloud.append(w)
  manifest.append(dict(path=str(f),sha256=sha(f),bytes=f.stat().st_size,points=len(a),timestamp_ns=f.stem,reference_offset_s=float((int(f.stem)-ns[i])*1e-9),time_s=float((int(f.stem)-ns[0])*1e-9),bbox_min=w.min(0).tolist(),bbox_max=w.max(0).tolist()))
 pc=np.concatenate(cloud); low=np.floor(xyz[:,:2].min(0)-8); high=np.ceil(xyz[:,:2].max(0)+8); res=.4; shape=np.ceil((high-low)/res).astype(int)+1
 ix=np.rint((pc[:,:2]-low)/res).astype(int); valid=(ix>=0).all(1)&(ix<shape).all(1)&(abs(pc[:,2])<2)
 ix=ix[valid];z=pc[valid,2]; flat=ix[:,0]*shape[1]+ix[:,1];order=np.argsort(flat);keys,starts=np.unique(flat[order],return_index=True); zz=z[order];g=np.full(tuple(shape),np.nan)
 for k,a,b in zip(keys,starts,np.r_[starts[1:],len(zz)]):g.ravel()[k]=np.median(zz[a:b])
 mask=np.isfinite(g);dist,near=distance_transform_edt(~mask,return_indices=True);filled=gaussian_filter(g[tuple(near)],.65)
 def sample(t):return np.column_stack([np.interp(t,ts,xyz[:,k]) for k in range(3)])
 def terrain(q):
  v=(q[:,:2]-low)/res;j=np.floor(v).astype(int); u=v-j
  assert (j>=0).all() and (j+1<shape).all()
  h=sum(filled[j[:,0]+a,j[:,1]+b]*((u[:,0] if a else 1-u[:,0])*(u[:,1] if b else 1-u[:,1])) for a,b in [(0,0),(0,1),(1,0),(1,1)])
  support=np.array([mask[j[:,0]+a,j[:,1]+b] for a,b in [(0,0),(0,1),(1,0),(1,1)]]).mean(0)
  return h,support,dist[j[:,0],j[:,1]]*res
 candidates=[]; tracks={}
 for start in range(1,114):
  t=start+np.arange(6)*.2;q=np.stack([sample(t+5),sample(t)],axis=1);h,s,d=terrain(q.reshape(-1,3));q[:,:,2]=h.reshape(6,2)+1.16
  vv=np.diff(q[:,:,:2],axis=0);speed=np.linalg.norm(vv,axis=2)/.2;angle=np.arctan2(vv[:,:,1],vv[:,:,0]); turn=np.abs(np.diff(np.unwrap(angle,axis=0),axis=0));turn[speed[1:]<.02]=0
  rec=dict(start_s=start,support_min=float(s.min()),support_mean=float(s.mean()),fill_distance_max_m=float(d.max()),speed_mean_m_s=float(speed.mean()),speed_min_m_s=float(speed.min()),turn_rad=float(turn.sum()),height_span_m=float(np.ptp(q[:,:,2])),peer_mean_m=float(np.linalg.norm(q[:,1]-q[:,0],axis=1).mean()))
  candidates.append(rec);tracks[start]=q
 eligible=[r for r in candidates if r['support_min']>=.75 and r['fill_distance_max_m']<=.4]
 if len(eligible)<3:raise RuntimeError('Insufficient supported windows')
 # Predeclared selection: most turning moving; slowest; greatest separation from selected start times.
 moving=[r for r in eligible if r['speed_mean_m_s']>.1]
 chosen=[max(moving,key=lambda r:(r['turn_rad'],-r['start_s']))];rest=[r for r in eligible if abs(r['start_s']-chosen[0]['start_s'])>=2]
 chosen.append(min(rest,key=lambda r:(r['speed_mean_m_s'],r['start_s'])))
 rest=[r for r in eligible if min(abs(r['start_s']-a['start_s']) for a in chosen)>=2]
 chosen.append(max(rest,key=lambda r:(min(abs(r['start_s']-a['start_s']) for a in chosen),r['height_span_m'])))
 windows=[]
 for i,r in enumerate(chosen):
  q=tracks[r['start_s']];mid=q[:,:,:2].mean((0,1)); span=np.maximum(np.ptp(q[:,:,:2],axis=(0,1))/2+8,[10,8]);anchors=np.array([[mid[0]+a*span[0],mid[1]+b*span[1],1.16] for a,b in [(-1,-1),(-1,1),(1,-1),(1,1)]])
  windows.append(dict(id=f'W{i}',**r,times_s=(np.arange(6)*.2).tolist(),xyz_m=q.tolist(),anchors_xyz_m=anchors.tolist(),yaw_rad=np.stack([np.interp(r['start_s']+np.arange(6)*.2+5,ts,np.unwrap(yaw)),np.interp(r['start_s']+np.arange(6)*.2,ts,np.unwrap(yaw))],axis=1).tolist()))
 np.savez_compressed(ART/'scene.npz',cloud=pc.astype('f4'),terrain=filled,observed=mask,low=low,res=res,gt_xyz=xyz,gt_t=ts,gt_yaw=yaw)
 dump(OUT/'INPUT_SOURCES.json',manifest);dump(OUT/'WINDOWS.json',windows);dump(OUT/'WINDOW_CANDIDATES.json',candidates)
 dump(OUT/'SCENE_STATS.json',dict(reference_duration_s=float(ts[-1]),reference_rows=len(ts),reference_bbox=[xyz.min(0).tolist(),xyz.max(0).tolist()],point_count=len(pc),frames=len(files),grid_shape=shape.tolist(),observed_cells=int(mask.sum()),all_cells=int(mask.size),eligible_windows=len(eligible),scene_npz_sha256=sha(ART/'scene.npz')))
 print(json.dumps(windows,indent=2))
if __name__=='__main__':main()
