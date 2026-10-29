"""Three preregistered local signal families. No truth, labels or joint states."""
import math
import numpy as np
CARS=('car1','car2')
def wrap(x):return math.atan2(math.sin(x),math.cos(x))
def antenna(p,m):
 lx,ly=m['base_to_antenna_body_xy_m'];c,s=math.cos(p[2]),math.sin(p[2]);return np.array([p[0]+c*lx-s*ly,p[1]+s*lx+c*ly,m['antenna_height_m']])
def body_delta(a,b):
 c,s=math.cos(a[2]),math.sin(a[2]);dx,dy=b[0]-a[0],b[1]-a[1];return np.array([c*dx+s*dy,-s*dx+c*dy])
def finite(p):return p is not None and bool(np.isfinite(p).all())
def gn_proxy(snapshot,config,audit,accepted):
 if not accepted:return dict(status='startup_not_accepted',xy_trace_sigma=[None,None],H_min_eigenvalue=None,solve_relative_residual=None)
 assert not snapshot['peer_enabled']
 x=np.array(snapshot['states']).ravel()
 def f(y):return audit.residuals(y,snapshot['times_s'],snapshot['local'],snapshot['observations'],snapshot['peers_m'],config['models'],snapshot['prior'],False)
 J=audit.finite_jac(f,x,eps=1e-6);H=J.T@J;eig=np.linalg.eigvalsh(H)
 if eig[0]<=np.finfo(float).eps*len(x)*eig[-1]:return dict(status='rank_unknown',xy_trace_sigma=[None,None],H_min_eigenvalue=float(eig[0]),solve_relative_residual=None)
 A=np.zeros((4,len(x)))
 for i,car in enumerate(CARS):
  p=x[-6+3*i:] if i else x[-6:-3];lx,ly=config['models'][car]['base_to_antenna_body_xy_m'];th=p[2];col=len(x)-6+3*i
  A[2*i:2*i+2,col:col+2]=np.eye(2);A[2*i:2*i+2,col+2]=[-math.sin(th)*lx-math.cos(th)*ly,math.cos(th)*lx-math.sin(th)*ly]
 X=np.linalg.solve(H,A.T);P=A@X;error=float(np.linalg.norm(H@X-A.T)/np.linalg.norm(A.T));assert error<1e-7
 assert np.linalg.eigvalsh(P)[0]>0
 return dict(status='nominal_GN_proxy_not_published_covariance',xy_trace_sigma=[float(np.sqrt(np.trace(P[2*i:2*i+2,2*i:2*i+2]))) for i in range(2)],H_min_eigenvalue=float(eig[0]),solve_relative_residual=error)

def construct_local(row,config,local_streams,origin,audit):
 """Accept only an I row + local raw messages; result contains no true errors."""
 assert not row['snapshot']['peer_enabled'];t=row['state_time_s'];cutoff=row['availability_cutoff_epoch_ns'];post=row['pose'];pred=row.get('prediction_pose');out=[]
 covariance=gn_proxy(row['snapshot'],config,audit,row['accepted_graph'])
 for i,car in enumerate(CARS):
  model=config['models'][car];sigma=model['graph_parameters']['range_sigma_m'];obs=row['bins'][car]['observations'];a=antenna(post[3*i:3*i+3],model);ap=antenna(pred[3*i:3*i+3],model)
  raw=[e for e in local_streams[car] if e['receive_epoch_ns']<=cutoff and abs((e['header_epoch_ns']-origin)/1e9-t)<=config['replay']['range_bin_half_width_s']]
  # Only wall keys are read; peer diagnostic fields in raw messages are ignored.
  perkey={k:[e['value'][k] for e in raw if k in e['value'] and np.isfinite(e['value'][k]) and e['value'][k]>0] for k in model['anchors_xyz_m']}
  for k,z in obs.items():assert float(np.median(perkey[k]))==z
  dr=[];dp=[];G=[]
  for k,z in sorted(obs.items()):
   anchor=np.array(model['anchors_xyz_m'][k]);norm=np.linalg.norm(a-anchor);corrected=z-model['range_bias_m'][k]
   dr.append(float(norm-corrected));dp.append(float(np.linalg.norm(ap-anchor)-corrected));G.append((a-anchor)[:2]/norm/sigma)
  H=np.array(G).T@np.array(G);w=np.linalg.eigvalsh(H)
  mads=[float(np.median(abs(np.array(v)-np.median(v)))) for v in perkey.values() if v]
  prior=np.array(row['snapshot']['prior']['matrix']);assert np.linalg.norm((prior.T@prior)[:3,3:])<1e-8
  out.append(dict(car=car,t_s=t,state_epoch_ns=row['state_epoch_ns'],cutoff_epoch_ns=cutoff,reference_accepted=row['accepted_graph'],reference_peer_enabled=False,
   local_dependency_max_s=row['bins'][car]['dependency_receipt_max_s'],window_start_s=row['snapshot']['times_s'][0],prior_present=True,
   wall_count=len(obs),wall_samples=sum(len(v) for v in perkey.values()),wall_raw_MAD_mean_m=float(np.mean(mads)) if mads else None,
   wall_post_signed_mean_m=float(np.mean(dr)) if dr else None,wall_post_rms_m=float(np.sqrt(np.mean(np.square(dr)))) if dr else None,wall_post_max_abs_m=max(map(abs,dr),default=None),wall_post_whitened_rms=float(np.sqrt(np.mean(np.square(dr)))/sigma) if dr else None,
   wall_geometry_eig_min=float(w[0]),wall_geometry_condition=float(w[-1]/w[0]) if w[0]>0 else None,
   wall_only_xy_trace_sigma_proxy_m=float(np.sqrt(np.trace(np.linalg.inv(H)))) if w[0]>0 else None,
   GN_status=covariance['status'],GN_xy_trace_sigma_proxy_m=covariance['xy_trace_sigma'][i],GN_H_min_eigenvalue=covariance['H_min_eigenvalue'],GN_solve_relative_residual=covariance['solve_relative_residual'],
   prediction_correction_xy_m=float(np.linalg.norm(a[:2]-ap[:2])),prediction_correction_yaw_rad=wrap(post[3*i+2]-pred[3*i+2]),wall_prediction_rms_m=float(np.sqrt(np.mean(np.square(dp)))) if dp else None))
 return out
