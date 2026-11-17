"""Reference-aware generation only. Ordinary solver must not import this module."""
import sys
from pathlib import Path
import numpy as np
from common import ROOT,DOC,read,write,filehash,clean,digest
sys.path.insert(0,str(ROOT/'sim/isaac_lab/moon1'))
from antenna_geometry import positions

def tracks(scene,cfg):
 # Match accepted PR114 output identity; never rebuild or overwrite it.
 receipt=read(ROOT/'docs/research/moon1_height_audit/results/RUN.json')
 record=next(r for r in receipt['outputs'] if r['path'].endswith('/scene/moon1_scene.npz'))
 if filehash(scene)!=record['sha256']:raise ValueError('PR114 scene SHA mismatch')
 with np.load(scene,allow_pickle=False) as n:data={k:n[k] for k in n.files}
 results=[]
 for w,start in enumerate(cfg['window_starts_s']):
  times=start+np.arange(6)*cfg['dt_s']
  if times[0]<data['sim_time'][0] or times[-1]>data['sim_time'][-1]:raise ValueError('OUT_OF_TIME_RANGE: no extrapolation')
  raw=[np.column_stack([np.interp(times,data['sim_time'],data[key][:,j]) for j in range(3)]) for key in ['leader','follower']]
  body,antenna=zip(*(positions(data,x) for x in raw))
  xyz=np.stack(antenna,axis=1);bodies=np.stack(body,axis=1)
  results.append(dict(window=w,times_s=times,antenna_xyz_m=xyz,body_xyz_m=bodies,original_gt_xyz_m=np.stack(raw,axis=1),display_antenna_xyz_m=xyz.copy()))
 return clean(results),dict(path=str(Path(scene).resolve()),sha256=record['sha256'],bytes=Path(scene).stat().st_size,pr114_commit=cfg['pr114_commit'],source_receipt_sha256=filehash(ROOT/'docs/research/moon1_height_audit/results/RUN.json'))

def make_input(track,cfg,condition,seed,noiseless=False):
 xyz=np.array(track['antenna_xyz_m']);anchors=np.array(cfg['anchors_xyz_m'])
 # Deliberately independent of model.prediction: compute by broadcasting 3D coordinates.
 wall=np.sqrt(np.sum((xyz[:,:,None,:]-anchors[None,None,:,:])**2,axis=-1))
 peer=np.sqrt(np.sum((xyz[:,1]-xyz[:,0])**2,axis=1))
 ranges=np.column_stack([wall.reshape(6,8),peer]).ravel()
 standard={k:np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,track['window'],stream]))).normal(size=shape) for k,stream,shape in [('range',0,54),('motion',1,(5,2,2)),('prior',2,(2,2))]}
 if noiseless:standard={k:np.zeros_like(v) for k,v in standard.items()}
 motion_sigma=np.array([cfg['motion_sigma_m'],cfg['motion_sigma_m']*condition['car2_motion_multiplier']])
 noise=standard['range']*cfg['range_sigma_m'];injected=np.zeros(54);injected[8::9]=condition['peer_bias_m']
 increments=np.diff(xyz[:,:,:2],axis=0)+standard['motion']*motion_sigma[None,:,None]
 center=xyz[0,:,:2]+cfg['prior_sigma_m']*standard['prior']
 obs=dict(schema=1,frame='moon_map',units=['m','s'],times_s=track['times_s'],anchors_xyz_m=cfg['anchors_xyz_m'],height_mode=cfg['height_mode'],heights_m=xyz[:,:,2],ranges_m=ranges+noise+injected,global_xy_increments_m=increments,motion_sigmas_m=motion_sigma,range_sigma_m=cfg['range_sigma_m'],prior_center_xy_m=center,prior_sigma_m=cfg['prior_sigma_m'],initialization_offset_m=cfg['initialization_offset_m'],peer_direction='one_car1_to_car2')
 reference=dict(window=track['window'],seed=seed,condition=condition,track=track,clean_ranges_m=ranges,injection_m=injected,standard_noise=standard,noiseless=noiseless)
 return clean(obs),clean(reference)
