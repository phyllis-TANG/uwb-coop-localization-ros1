#!/usr/bin/env python3
"""Independent saved-state evaluation; no optimizer calls. Reference allowed here only."""
import argparse,csv,gzip,json
from pathlib import Path
import numpy as np
from common import read,write,digest,filehash,clean
from model import problem

def residual(o,method,q):
 p=np.asarray(q[:24]).reshape(6,2,2);h=np.asarray(o['heights_m']);y=o['ranges_m'];r=[]
 for t in range(6):
  for c in range(2):
   for k,a in enumerate(o['anchors_xyz_m']):
    dx,dy=p[t,c]-np.array(a[:2]);dz=h[t,c]-a[2]
    r.append((np.sqrt(dx*dx+dy*dy+dz*dz)-y[9*t+4*c+k])/o['range_sigma_m'])
  if method!='M0':
   dx,dy=p[t,1]-p[t,0];dz=h[t,1]-h[t,0]
   r.append((np.sqrt(dx*dx+dy*dy+dz*dz)+(q[-1] if method=='M2' else 0)-y[9*t+8])/o['range_sigma_m'])
 for t in range(5):
  for c in range(2):
   for axis in range(2):r.append((p[t+1,c,axis]-p[t,c,axis]-o['global_xy_increments_m'][t][c][axis])/o['motion_sigmas_m'][c])
 for c in range(2):
  for axis in range(2):r.append((p[0,c,axis]-o['prior_center_xy_m'][c][axis])/o['prior_sigma_m'])
 return np.array(r)

class Evidence:
 def __init__(self,path):self.path=Path(path);self.cache={}
 def load(self,kind,name):
  p=self.path/kind/(name+'.json')
  if p.exists():return read(p)
  if kind not in self.cache:
   with gzip.open(self.path/(kind+'.json.gz'),'rt') as f:self.cache[kind]=json.load(f)
  return self.cache[kind][name]

def csvwrite(p,rows):
 with p.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def evaluate(source,out):
 source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=False);e=Evidence(source)
 plan=read(source/'PLAN.json');cfg=read(source/'FREEZE.json')['config'];sc=read(source/'FREEZE.json')['solver_config'];rows=[];maxres=0.;maxgrad=0.;maxcov=0.;fdmax=0.;data_ranks=[];calls=0
 standard={};nominal={};display=[]
 for item in plan:
  uid=item['id'];o=e.load('measurements',uid);ref=e.load('reference',uid);truth=np.array(ref['track']['antenna_xyz_m'])[:,:,:2]
  key=(item['window'],item['seed']);standard.setdefault(key,digest(ref['standard_noise']));assert standard[key]==digest(ref['standard_noise'])
  assert o['heights_m']==np.array(ref['track']['antenna_xyz_m'])[:,:,2].tolist()
  assert ref['track']['antenna_xyz_m']==ref['track']['display_antenna_xyz_m']
  for t in range(6):
   for c in range(2):
    a=ref['track']['antenna_xyz_m'][t][c];b=ref['track']['body_xyz_m'][t][c]
    assert np.allclose(a,np.array(b)+[0,0,1.16],atol=1e-12,rtol=0)
  # Reconstruct generation independently from saved truth and standardized streams.
  cleanrange=[]
  for t in range(6):
   points=np.array(ref['track']['antenna_xyz_m'])[t]
   for c in range(2):
    for a in cfg['anchors_xyz_m']:cleanrange.append(float(np.linalg.norm(points[c]-a)))
   cleanrange.append(float(np.linalg.norm(points[0]-points[1])))
  np.testing.assert_allclose(o['ranges_m'],np.array(cleanrange)+cfg['range_sigma_m']*np.array(ref['standard_noise']['range'])+ref['injection_m'],atol=1e-12,rtol=0)
  np.testing.assert_allclose(o['global_xy_increments_m'],np.diff(truth,axis=0)+np.array(ref['standard_noise']['motion'])*np.array(o['motion_sigmas_m'])[None,:,None],atol=1e-12,rtol=0)
  np.testing.assert_allclose(o['prior_center_xy_m'],truth[0]+cfg['prior_sigma_m']*np.array(ref['standard_noise']['prior']),atol=1e-12,rtol=0)
  baseline=None;methodrows=[]
  for method in cfg['methods']:
   fit=e.load('estimates',uid+'-'+method);calls+=fit.get('optimizer_calls') or 0
   row=dict(unit=uid,window=item['window'],condition=item['condition'],seed=item['seed'],method=method,status=fit['status'],accepted=fit['accepted'],usable=fit.get('estimate') is not None,car1_mse_m2=None,car2_mse_m2=None,car1_rmse_m=None,car2_rmse_m=None,relative_rmse_m=None,bias_estimate_m=None,bias_error_m=None,cost=fit.get('cost'),gradient_inf=fit.get('gradient_inf'),optimizer_calls=fit.get('optimizer_calls'),data_rank=None,total_rank=None,data_condition=None,total_condition=None,car1_D_m2=None,car2_D_m2=None,car1_benefit_m2=None,car2_benefit_m2=None,paired_accepted=False)
   if row['usable']:
    q=np.array(fit['estimate']);r=residual(o,method,q);f,start,h=problem(o,method);rr,j=f(q)
    assert h==fit['input_sha256'];np.testing.assert_array_equal(start,fit['initialization'])
    maxres=max(maxres,float(np.max(abs(r-np.array(fit['residual'])))));assert np.max(abs(r-rr))<1e-10
    assert abs(float(r@r/2)-fit['cost'])<1e-9
    maxgrad=max(maxgrad,float(np.max(abs(j.T@r-np.array(fit['gradient'])))))
    if item['seed']==cfg['seeds'][0] and item['condition']=='normal':
     steps=np.eye(len(q))*1e-5;fd=np.column_stack([(residual(o,method,q+d)-residual(o,method,q-d))/2e-5 for d in steps]);fdmax=max(fdmax,float(np.max(abs(fd-j))))
    for which,mat in [('data_information',j[:-4]),('total_information',j)]:
     scale=np.r_[np.ones(24),.1] if method=='M2' else np.ones(24);s=np.linalg.svd(mat*scale,compute_uv=False);rank=int(np.sum(s>s[0]*sc['rank_relative_tolerance']));assert rank==fit[which]['rank']
     if rank==len(q):
      independent=np.linalg.solve(mat.T@mat,np.eye(len(q)));maxcov=max(maxcov,float(np.max(abs(independent-np.array(fit[which]['covariance'])))))
     else:assert fit[which]['covariance'] is None
    err=q[:24].reshape(6,2,2)-truth;mse=np.mean(np.sum(err*err,axis=2),axis=0)
    relative=err[:,1]-err[:,0]
    row.update(car1_mse_m2=float(mse[0]),car2_mse_m2=float(mse[1]),car1_rmse_m=float(np.sqrt(mse[0])),car2_rmse_m=float(np.sqrt(mse[1])),relative_rmse_m=float(np.sqrt(np.mean(np.sum(relative*relative,axis=1)))),bias_estimate_m=float(q[-1]) if method=='M2' else None,bias_error_m=float(q[-1]-ref['condition']['peer_bias_m']) if method=='M2' else None,data_rank=fit['data_information']['rank'],total_rank=fit['total_information']['rank'],data_condition=fit['data_information']['condition_scaled'],total_condition=fit['total_information']['condition_scaled'])
    data_ranks.append(row['data_rank'])
   if method=='M0':baseline=row
   if baseline['usable'] and row['usable']:
    for c in [1,2]:row[f'car{c}_D_m2']=row[f'car{c}_mse_m2']-baseline[f'car{c}_mse_m2'];row[f'car{c}_benefit_m2']=-row[f'car{c}_D_m2']
    row['paired_accepted']=baseline['accepted'] and row['accepted']
   rows.append(row);methodrows.append(row)
  if item['condition'] in ['normal','motion5']:nominal[(item['window'],item['seed'],item['condition'])]=e.load('estimates',uid+'-M0')
  else:
   basecond='normal' if item['condition']=='bias03' else 'motion5';other=nominal[(item['window'],item['seed'],basecond)]
   here=e.load('estimates',uid+'-M0');assert here['input_sha256']==other['input_sha256'] and here['estimate']==other['estimate']
 assert maxres<1e-10 and maxgrad<1e-8 and maxcov<1e-8 and fdmax<2e-6
 assert len(rows)==180 and calls<=180
 csvwrite(out/'PER_RUN.csv',rows)
 groups=[]
 for window in range(3):
  for condition in [c['id'] for c in cfg['conditions']]:
   for method in cfg['methods']:
    selected=[r for r in rows if (r['window'],r['condition'],r['method'])==(window,condition,method)]
    summary=dict(window=window,condition=condition,method=method,planned=len(selected),usable=sum(r['usable'] for r in selected),accepted=sum(r['accepted'] for r in selected),paired_accepted=sum(r['paired_accepted'] for r in selected))
    for k in ['car1_mse_m2','car2_mse_m2','car1_rmse_m','car2_rmse_m','relative_rmse_m','car1_benefit_m2','car2_benefit_m2','bias_estimate_m','bias_error_m','cost','gradient_inf']:
     vals=[r[k] for r in selected if r[k] is not None];summary[k+'_mean']=float(np.mean(vals)) if vals else None
    groups.append(summary)
 csvwrite(out/'SUMMARY.csv',groups)
 failures=[dict(unit=r['unit'],window=r['window'],condition=r['condition'],seed=r['seed'],method=r['method'],status=r['status'],accepted=r['accepted']) for r in rows]
 csvwrite(out/'STATUS_ALL.csv',failures)
 contrasts=[]
 for window in range(3):
  for method in cfg['methods']:
   for a,b in [('motion5','normal'),('bias03','normal'),('both','motion5'),('both','bias03')]:
    for seed in cfg['seeds']:
     x=next(r for r in rows if (r['window'],r['method'],r['condition'],r['seed'])==(window,method,a,seed));y=next(r for r in rows if (r['window'],r['method'],r['condition'],r['seed'])==(window,method,b,seed))
     contrasts.append(dict(window=window,method=method,seed=seed,contrast=a+' minus '+b,paired_accepted=x['accepted'] and y['accepted'],car1_mse_change_m2=x['car1_mse_m2']-y['car1_mse_m2'] if x['usable'] and y['usable'] else None,car2_mse_change_m2=x['car2_mse_m2']-y['car2_mse_m2'] if x['usable'] and y['usable'] else None))
 csvwrite(out/'CONTRASTS.csv',contrasts)
 report=dict(status='PASS',planned=180,completed=len(rows),accepted=sum(r['accepted'] for r in rows),finite=sum(r['usable'] for r in rows),optimizer_calls=calls,residual_max_error=maxres,gradient_max_error=maxgrad,covariance_max_error=maxcov,weighted_jacobian_fd_max_error=fdmax,paired_standard_noise=True,M0_bias_input_output_invariant=True,display_coordinates_equal=True,formal_runs=0)
 write(out/'READBACK.json',report);print(json.dumps(report,indent=2));plots(e,plan,cfg,rows,out)

def plots(e,plan,cfg,rows,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 figdir=out/'figures';figdir.mkdir()
 fig,ax=plt.subplots(figsize=(10,5),layout='constrained');a=np.array(cfg['anchors_xyz_m']);ax.scatter(a[:,0],a[:,1],marker='^',s=70,label='Designed anchors z=1.16 m')
 for w in range(3):
  item=next(i for i in plan if i['window']==w);x=np.array(e.load('reference',item['id'])['track']['antenna_xyz_m'])
  for c in range(2):ax.plot(x[:,c,0],x[:,c,1],'-o',ms=3,label=f'w{w} car{c+1}')
 ax.set(xlabel='moon_map x (m)',ylabel='moon_map y (m)',title='Fixed windows and synthetic facilities (height-oracle)');ax.axis('equal');ax.legend(fontsize=8,ncol=2);fig.savefig(figdir/'scene.png',dpi=150);plt.close(fig)
 colors={'M0':'#777777','M1':'#2978b5','M2':'#dd6d35'}
 for w in range(3):
  fig,axes=plt.subplots(2,4,figsize=(15,6),layout='constrained')
  for k,condition in enumerate(cfg['conditions']):
   item=next(i for i in plan if i['window']==w and i['condition']==condition['id'] and i['seed']==cfg['seeds'][0]);x=np.array(e.load('reference',item['id'])['track']['antenna_xyz_m'])
   for c in range(2):
    ax=axes[c,k];ax.plot(x[:,c,0],x[:,c,1],'k-o',ms=3,label='reference')
    for method in cfg['methods']:
     f=e.load('estimates',item['id']+'-'+method)
     if f.get('estimate') is not None:
      z=np.array(f['estimate'][:24]).reshape(6,2,2);ax.plot(z[:,c,0],z[:,c,1],'-x',ms=3,color=colors[method],label=method)
    ax.set_title(f"{condition['id']} / car{c+1}");ax.set_xlabel('x (m)');ax.set_ylabel('y (m)');ax.ticklabel_format(useOffset=False);ax.axis('equal');ax.grid(alpha=.2)
  axes[0,0].legend(fontsize=7);fig.suptitle(f'Window {w}, fixed first seed {cfg["seeds"][0]}: height-oracle');fig.savefig(figdir/f'trajectories_w{w}.png',dpi=150);plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
 for w,ax in enumerate(axes):
  for k,c in enumerate(cfg['conditions']):
   vals=[r['bias_estimate_m'] for r in rows if r['window']==w and r['condition']==c['id'] and r['method']=='M2' and r['usable']]
   ax.scatter(np.full(len(vals),k),vals,label='M2' if k==0 else None);ax.plot([k-.2,k+.2],[c['peer_bias_m']]*2,'k-')
  ax.set_xticks(range(4),[c['id'] for c in cfg['conditions']],rotation=25);ax.set_title(f'Window {w}');ax.set_ylabel('Bias estimate (m)');ax.grid(alpha=.2)
 fig.suptitle('Five paired seeds; black line = reference injection, no CI claim');fig.savefig(figdir/'bias.png',dpi=150);plt.close(fig)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();evaluate(a.input,a.out)
