"""Dense footprint support audit; no estimator or evaluation outcomes."""
import csv,json,hashlib,sys
from pathlib import Path
import numpy as np
from scipy.ndimage import distance_transform_edt,gaussian_filter
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[3]
DOC=ROOT/'docs/research/lunar_end_to_end/continuous'
ART=Path('/home/ubuntu22/uwb-lunar-continuous-artifacts')
OLD=ROOT/'docs/research/lunar_end_to_end'
def write(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(x,indent=2,allow_nan=False)+'\n');tmp.replace(p)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvwrite(p,rows):
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def interp(data,t):return np.column_stack([np.interp(t,data['gt_t'],data['gt_xyz'][:,i]) for i in range(3)])
def query(data,xy):
 v=(xy-data['low'])/float(data['res']);ij=np.floor(v).astype(int);u=v-ij;g=data['terrain'];mask=data['observed']
 assert (ij>=0).all() and (ij+1<g.shape).all()
 h=sum(g[ij[:,0]+a,ij[:,1]+b]*(u[:,0] if a else 1-u[:,0])*(u[:,1] if b else 1-u[:,1]) for a,b in [(0,0),(0,1),(1,0),(1,1)])
 support=np.mean([mask[ij[:,0]+a,ij[:,1]+b] for a,b in [(0,0),(0,1),(1,0),(1,1)]],axis=0)
 return h,support

def main():
 DOC.mkdir(exist_ok=True);ART.mkdir(exist_ok=True)
 path=Path('/home/ubuntu22/uwb-lunar-end-to-end-artifacts/scene.npz');data=np.load(path);assert sha(path)==json.loads((OLD/'SCENE_STATS.json').read_text())['scene_npz_sha256']
 protocol=dict(dt_s=.02,footprint_half_length_m=.4,footprint_half_width_m=.3,footprint_grid_m=.1,minimum_four_corner_observed_fraction=.75,maximum_nearest_observed_node_m=.4,maximum_adjacent_sample_height_change_m=.15,maximum_frame_cell_height_spread_m=.25,car1_source_offset_s=5,car2_source_offset_s=0,meaning='sampled point-cloud support, not collision or traversability certification')
 write(DOC/'COVERAGE_PROTOCOL.json',protocol)
 obsxy=np.argwhere(data['observed'])*float(data['res'])+data['low'];tree=cKDTree(obsxy)
 source=json.loads((OLD/'INPUT_SOURCES.json').read_text())
 if '--augment' in sys.argv:source+=json.loads((DOC/'SUPPLEMENT_RECEIPT.json').read_text())['files']
 gt=source[0];rows=list(csv.reader(Path(gt['path']).open()))[1:];ns=np.array([int(r[0]) for r in rows],dtype=np.int64);arr=np.array([[float(v) for v in r[1:8]] for r in rows]);C=np.diag([1.,-1.,-1.]);rots=Rotation.from_quat(arr[:,[4,5,6,3]]).as_matrix();frame_grids=[];clouds=[]
 for f in source[1:]:
  p=Path(f['path']);assert sha(p)==f['sha256'];points=np.loadtxt(p,delimiter=',')[:,:3];i=np.argmin(abs(ns-int(p.stem)));world=((points+[1,0,-1.5])@rots[i].T+arr[i,:3])@C;clouds.append(world)
  ix=np.rint((world[:,:2]-data['low'])/float(data['res'])).astype(int);valid=np.isfinite(world).all(1)&(abs(world[:,2])<2)&(ix>=0).all(1)&(ix<data['terrain'].shape).all(1);ix=ix[valid];z=world[valid,2];flat=ix[:,0]*data['terrain'].shape[1]+ix[:,1];order=np.argsort(flat);keys,starts=np.unique(flat[order],return_index=True);grid=np.full(data['terrain'].shape,np.nan)
  for key,a,b in zip(keys,starts,np.r_[starts[1:],len(order)]):grid.ravel()[key]=np.median(z[order[a:b]])
  frame_grids.append(grid)
 if '--augment' in sys.argv:
  data=dict(data);pc=np.concatenate(clouds);ix=np.rint((pc[:,:2]-data['low'])/float(data['res'])).astype(int);valid=(abs(pc[:,2])<2)&(ix>=0).all(1)&(ix<data['terrain'].shape).all(1);flat=ix[valid,0]*data['terrain'].shape[1]+ix[valid,1];z=pc[valid,2];order=np.argsort(flat);keys,starts=np.unique(flat[order],return_index=True);g=np.full(data['terrain'].shape,np.nan)
  for key,a,b in zip(keys,starts,np.r_[starts[1:],len(order)]):g.ravel()[key]=np.median(z[order[a:b]])
  mask=np.isfinite(g);_,near=distance_transform_edt(~mask,return_indices=True);data['terrain']=gaussian_filter(g[tuple(near)],.65);data['observed']=mask;data['cloud']=pc.astype('f4');path=ART/'scene_augmented.npz';np.savez_compressed(path,**data);tree=cKDTree(np.argwhere(mask)*float(data['res'])+data['low'])
 fg=np.stack(frame_grids);count=np.isfinite(fg).sum(0);lo=np.min(np.where(np.isfinite(fg),fg,np.inf),axis=0);hi=np.max(np.where(np.isfinite(fg),fg,-np.inf),axis=0);spread=np.where(count>=2,hi-lo,0)
 offsets=np.array([(x,y) for x in np.arange(-.4,.401,.1) for y in np.arange(-.3,.301,.1)])
 summaries=[];allrows=[];routes={}
 for start,end in [(5,14),(109,114)]:
  times=np.round(np.arange(start,end+.01,.02),8);centres=np.stack([interp(data,times+shift) for shift in [5,0]],axis=1);yaw=np.stack([np.interp(times+shift,data['gt_t'],np.unwrap(data['gt_yaw'])) for shift in [5,0]],axis=1)
  good=np.ones(len(times),bool);footprints=[];stats=[]
  for car in range(2):
   c=np.cos(yaw[:,car]);s=np.sin(yaw[:,car]);xy=centres[:,car,None,:2]+np.stack([c[:,None]*offsets[:,0]-s[:,None]*offsets[:,1],s[:,None]*offsets[:,0]+c[:,None]*offsets[:,1]],axis=2)
   flatxy=xy.reshape(-1,2);height,support=query(data,flatxy);distance=tree.query(flatxy)[0];idx=np.rint((flatxy-data['low'])/float(data['res'])).astype(int);seam=spread[idx[:,0],idx[:,1]];frames=count[idx[:,0],idx[:,1]]
   h=height.reshape(len(times),-1);support=support.reshape(h.shape);distance=distance.reshape(h.shape);seam=seam.reshape(h.shape);frames=frames.reshape(h.shape)
   dh=np.r_[np.zeros((1,h.shape[1])),np.abs(np.diff(h,axis=0))].max(1)
   ok=(support.min(1)>=.75)&(distance.max(1)<=.4+1e-12)&(seam.max(1)<=.25)&(dh<=.15);good &=ok;footprints.append(xy)
   for i,t in enumerate(times):
    allrows.append(dict(candidate=f'{start}-{end}',time_s=t,car=car+1,support_min=float(support[i].min()),support_mean=float(support[i].mean()),fill_distance_max_m=float(distance[i].max()),height_min_m=float(h[i].min()),height_max_m=float(h[i].max()),height_step_max_m=float(dh[i]),frame_overlap_count_min=int(frames[i].min()),frame_height_spread_max_m=float(seam[i].max()),passed=bool(ok[i])))
   stats.append(dict(car=car+1,passed=int(ok.sum()),total=len(ok),support_min=float(support.min()),fill_distance_max_m=float(distance.max()),frame_spread_max_m=float(seam.max())))
  intervals=[];begin=None
  for i,val in enumerate(np.r_[good,False]):
   if val and begin is None:begin=i
   elif not val and begin is not None:intervals.append([float(times[begin]),float(times[i-1])]);begin=None
  best=max(intervals,key=lambda a:a[1]-a[0]) if intervals else None
  summaries.append(dict(candidate=[start,end],all_pass=bool(good.all()),longest_pass=best,passing_intervals=intervals,failed_times=times[~good].tolist(),cars=stats));routes[(start,end)]=(times,centres,yaw,good)
  fig,axs=plt.subplots(2,1,figsize=(12,7),constrained_layout=True);ax=axs[0];extent=[data['low'][0],data['low'][0]+(data['terrain'].shape[0]-1)*.4,data['low'][1],data['low'][1]+(data['terrain'].shape[1]-1)*.4];ax.imshow(data['observed'].T,origin='lower',extent=extent,cmap='Greys',alpha=.65)
  for car in range(2):
   xy=footprints[car];ax.plot(centres[:,car,0],centres[:,car,1],label=f'Car{car+1}');bad=xy[~good];ax.scatter(bad[:,:,0].ravel(),bad[:,:,1].ravel(),s=1,color='red',alpha=.15)
  xyall=np.concatenate(footprints);ax.set(xlim=(xyall[:,:,0].min()-1,xyall[:,:,0].max()+1),ylim=(xyall[:,:,1].min()-1,xyall[:,:,1].max()+1),xlabel='moon_map x [m]',ylabel='y [m]',title=f'{start}-{end}s: dark observed; white filled; red failing footprint');ax.legend()
  for car in range(2):
   rr=[r for r in allrows if r['candidate']==f'{start}-{end}' and r['car']==car+1];axs[1].plot(times,[r['support_min'] for r in rr],label=f'Car{car+1} min support')
  axs[1].axhline(.75,color='red',ls='--');axs[1].set(xlabel='Car2 source time [s]',ylabel='four-corner support');axs[1].legend();fig.savefig(DOC/f'coverage_{start}_{end}.png',dpi=140);plt.close(fig)
 csvwrite(DOC/'DENSE_COVERAGE.csv',allrows);write(DOC/'COVERAGE_AUDIT.json',dict(protocol=protocol,candidates=summaries,source_scene_sha256=sha(path),coordinate_transform=C.tolist(),transform_determinant=float(np.linalg.det(C)),source_hashes_verified=len(source)-1))
 np.savez_compressed(ART/'frame_support.npz',count=count,spread=spread)
 write(DOC/'CONTINUOUS_SOURCES.json',source)
 print(json.dumps(summaries))
if __name__=='__main__':main()
