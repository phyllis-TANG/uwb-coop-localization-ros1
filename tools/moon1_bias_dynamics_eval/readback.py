"""Full portable readback: no optimizer calls. Includes original and continued endpoints."""
import argparse
from bridge import *
from inputs import verify

class Evidence:
 def __init__(self,path):self.path=Path(path);self.cache={}
 def get(self,rel):
  p=self.path/rel
  if p.exists():return read(p)
  group,tail=rel.split('/',1)
  if group not in self.cache:self.cache[group]=unpack(self.path/(group+'.json.gz'))
  return self.cache[group][tail]

def continuation_readback():
 p=DOC/'continuation';old=unpack(OLD/'results/estimates.json.gz');obs=unpack(OLD/'results/measurements.json.gz');cases=read(p/'FREEZE.json')['cases'];count=0
 for name in cases['failures']+cases['controls']:
  uid,method=name.split('-');attempt=read(p/name/'CONTINUE.attempt.json');res=read(p/name/'CONTINUE.result.json')
  np.testing.assert_array_equal(attempt['start'],old[name]['estimate']);assert digest(obs[uid])==attempt['measurement_sha256']
  if res['estimate'] is not None:
   r,j=independent(obs[uid],method,res['estimate']);assert abs(r@r/2-res['cost'])<1e-9
   np.testing.assert_allclose(j.T@r,res['gradient'],atol=1e-8,rtol=0)
   assert classify(res['estimate'],r,j,res['scipy_status'],res['scipy_success'])==res['status']
  count+=1
 assert count==22
 return dict(cases=22,optimizer_calls=0,passed=True)

def evaluate(source,out):
 source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=False);e=Evidence(source);freeze=read(source/'FREEZE.json');cfg=freeze['config'];plan=read(source/'PLAN.json');run=read(source/'RUN.json')
 if (source/'MANIFEST.json').exists():
  manifest=read(source/'MANIFEST.json')
  for name,meta in manifest['files'].items():assert filehash(source/name)==meta['sha256']
  for name,sha in manifest['original_json_sha256'].items():
   obj=e.get(name);assert hashlib.sha256((json.dumps(obj,indent=2,allow_nan=False)+'\n').encode()).hexdigest()==sha
 if freeze['mode']=='smoke':cfg=dict(cfg,seeds=[cfg['development_seed']])
 rows=[];peerrows=[];stages=[];noise={};m0base={};m2base={};shifts=[];maxr=0.;maxg=0.;maxfd=0.;calls=0
 for item in plan:
  uid=item['id'];o=e.get('measurements/'+uid+'.json');ref=e.get('reference/'+uid+'.json');verify(o,ref)
  assert ref['condition']['id']==item['condition'];assert ref['seed']==item['seed']
  pair=(item['window'],item['seed']);noise.setdefault(pair,digest(ref['standard_noise']));assert noise[pair]==digest(ref['standard_noise'])
  truth=np.array(ref['track']['antenna_xyz_m'])[:,:,:2];methodrows=[];baseline=None
  for method in cfg['methods']:
   name=uid+'-'+method
   try:final=e.get('estimates/'+name+'/FINAL.json')
   except (KeyError,FileNotFoundError):final=dict(method=method,estimate=None,accepted=False,status='PROCESS_FAILURE',optimizer_calls=None,stage=None)
   f,init,receipt=problem(o,method);last=None;stage_records=[]
   for stage in ['P0','P1']:
    try:attempt=e.get('estimates/'+name+'/'+stage+'.attempt.json')
    except (KeyError,FileNotFoundError):continue
    calls+=1
    assert attempt['measurement_sha256']==digest(o) and attempt['consumed_sha256']==receipt
    assert attempt['settings']==freeze['solver'][stage]
    assert attempt['commit']==freeze['commit'] and attempt['source_sha256']==freeze['source_sha256']
    np.testing.assert_array_equal(attempt['start'],init if stage=='P0' else last['estimate'])
    try:s=e.get('estimates/'+name+'/'+stage+'.result.json')
    except (KeyError,FileNotFoundError):
     stages.append(dict(id=name,stage=stage,status='ORPHAN_ATTEMPT',cost=None,gradient_inf=None,scaled_gradient_inf=None,nfev=None,njev=None,scipy_status=None,accepted=False,data_rank=None,total_rank=None,elapsed_s=None));continue
    if s['estimate'] is not None:
     q=np.array(s['estimate']);rr,jj=independent(o,method,q);r,j=f(q);maxr=max(maxr,float(max(abs(rr-r))));maxg=max(maxg,float(max(abs(jj.T@rr-np.array(s['gradient'])))))
     np.testing.assert_allclose(rr,s['residual'],atol=1e-10,rtol=0);assert abs(rr@rr/2-s['cost'])<1e-9
     label=classify(q,rr,jj,s['scipy_status'],s['scipy_success']);assert label==s['status']
     for key,mat in [('data_information',jj[:-4]),('total_information',jj)]:
      info=information(mat,1e-8);assert info['rank']==s[key]['rank'];np.testing.assert_allclose(info['singular_values'],s[key]['singular_values'],rtol=1e-10,atol=1e-10)
     if item['seed']==cfg['seeds'][0] and stage=='P1':
      eps=1e-5;fd=np.column_stack([(independent(o,method,q+d)[0]-independent(o,method,q-d)[0])/(2*eps) for d in np.eye(len(q))*eps]);maxfd=max(maxfd,float(np.max(abs(fd-jj))))
    last=s;stage_records.append(s)
    stages.append(dict(id=name,stage=stage,status=s['status'],cost=s.get('cost'),gradient_inf=s.get('gradient_inf'),scaled_gradient_inf=s.get('scaled_gradient_inf'),nfev=s.get('nfev'),njev=s.get('njev'),scipy_status=s.get('scipy_status'),accepted=s['accepted'],data_rank=s.get('data_information',{}).get('rank'),total_rank=s.get('total_information',{}).get('rank'),elapsed_s=s.get('elapsed_s')))
   if final['estimate'] is not None:
    selected=next(s for s in stage_records if s['stage']==final['stage'])
    np.testing.assert_array_equal(final['estimate'],selected['estimate'])
    if final['status']=='NO_FINITE_P1':assert not final['accepted']
    last=selected
   row=dict(unit=uid,window=item['window'],seed=item['seed'],condition=item['condition'],method=method,status=final['status'],accepted=final['accepted'],finite=final['estimate'] is not None,car1_mse_m2=None,car2_mse_m2=None,car1_rmse_m=None,car2_rmse_m=None,relative_mse_m2=None,relative_rmse_m=None,bias_estimate_m=None,curve_mean_m=float(np.mean(ref['condition']['peer_curve_m'])),bias_minus_curve_mean_m=None,peer_residual_rms_m=None,peer_residual_late_minus_early_m=None,peer_residual_slope_m_per_s=None,car1_benefit_m2=None,car2_benefit_m2=None,paired_accepted=False,gradient_inf=last.get('gradient_inf') if last else None,cost=last.get('cost') if last else None,optimizer_calls=final['optimizer_calls'],nfev_total=sum(s.get('nfev') or 0 for s in stage_records))
   if row['finite']:
    q=np.array(final['estimate']);err=q[:24].reshape(6,2,2)-truth;mse=np.mean(np.sum(err**2,axis=2),axis=0);rel=float(np.mean(np.sum((err[:,1]-err[:,0])**2,axis=1)));b=float(q[-1]) if method=='M2' else 0.
    row.update(car1_mse_m2=float(mse[0]),car2_mse_m2=float(mse[1]),car1_rmse_m=float(np.sqrt(mse[0])),car2_rmse_m=float(np.sqrt(mse[1])),relative_mse_m2=rel,relative_rmse_m=float(np.sqrt(rel)),bias_estimate_m=b if method=='M2' else None,bias_minus_curve_mean_m=b-row['curve_mean_m'] if method=='M2' else None)
    xy=q[:24].reshape(6,2,2);height=np.array(o['heights_m']);geom=np.sqrt(np.sum((xy[:,1]-xy[:,0])**2,axis=1)+(height[:,1]-height[:,0])**2);pr=geom+b-np.array(o['ranges_m'])[8::9];time=np.arange(6)*.2
    row.update(peer_residual_rms_m=float(np.sqrt(np.mean(pr**2))),peer_residual_late_minus_early_m=float(np.mean(pr[3:])-np.mean(pr[:3])),peer_residual_slope_m_per_s=float(np.polyfit(time,pr,1)[0]))
    for t in range(6):peerrows.append(dict(unit=uid,window=item['window'],seed=item['seed'],condition=item['condition'],method=method,accepted=final['accepted'],epoch=t,local_time_s=float(time[t]),global_time_s=o['times_s'][t],injection_m=ref['condition']['peer_curve_m'][t],estimated_constant_m=b if method=='M2' else None,geometric_range_m=float(geom[t]),measured_range_m=o['ranges_m'][9*t+8],model_minus_measurement_m=float(pr[t]),whitened_residual=float(pr[t]/.04),used_by_solver=method!='M0'))
    if method=='M0':
     if item['condition']=='normal':m0base[pair]=final['estimate']
     else:np.testing.assert_array_equal(final['estimate'],m0base[pair])
    if method=='M2':
     if item['condition']=='normal':m2base[pair]=(q,pr)
     if item['condition']=='constant03':
      q0,pr0=m2base[pair];shifts.append(dict(window=item['window'],seed=item['seed'],xy_difference_max_m=float(max(abs(q[:24]-q0[:24]))),bias_shift_minus_point3_m=float(q[-1]-q0[-1]-.3),residual_difference_max_m=float(max(abs(pr-pr0)))))
   if method=='M0':baseline=row
   if baseline['finite'] and row['finite']:
    for c in [1,2]:row[f'car{c}_benefit_m2']=baseline[f'car{c}_mse_m2']-row[f'car{c}_mse_m2']
    row['paired_accepted']=baseline['accepted'] and row['accepted']
   rows.append(row)
 assert maxr<1e-10 and maxg<1e-8 and maxfd<2e-6
 assert len(rows)==run['planned_methods'];assert calls==run['reserved_calls']
 csvwrite(out/'PER_RUN.csv',rows);csvwrite(out/'STAGES.csv',stages);csvwrite(out/'PEER_RESIDUALS.csv',peerrows);csvwrite(out/'CONSTANT_SHIFT.csv',shifts)
 summaries=[]
 for w in ['all',0,1,2]:
  for condition in [c['id'] for c in cfg['conditions']]:
   for method in cfg['methods']:
    selected=[r for r in rows if r['condition']==condition and r['method']==method and (w=='all' or r['window']==w)]
    if not selected:continue
    for subset in ['all_finite','paired_accepted']:
     use=[r for r in selected if r['finite'] and (subset=='all_finite' or r['paired_accepted'])]
     summary=dict(window=w,condition=condition,method=method,subset=subset,planned=len(selected),finite=sum(r['finite'] for r in selected),accepted=sum(r['accepted'] for r in selected),used=len(use))
     for k in ['car1_mse_m2','car2_mse_m2','car1_rmse_m','car2_rmse_m','relative_rmse_m','car1_benefit_m2','car2_benefit_m2','bias_estimate_m','bias_minus_curve_mean_m','peer_residual_rms_m','peer_residual_late_minus_early_m']:
      vals=[r[k] for r in use if r[k] is not None];summary[k+'_mean']=float(np.mean(vals)) if vals else None
     summaries.append(summary)
 csvwrite(out/'SUMMARY.csv',summaries)
 report=dict(passed=True,planned=len(rows),finite=sum(r['finite'] for r in rows),accepted=sum(r['accepted'] for r in rows),calls_reserved=calls,calls_completed=run['completed_calls'],orphan_attempts=run['orphan_attempts'],residual_crosscheck_max=maxr,gradient_crosscheck_max=maxg,fd_jacobian_max=maxfd,paired_noise=True,M0_all_conditions_invariant=True,max_M2_constant_xy_difference_m=max(s['xy_difference_max_m'] for s in shifts),max_M2_constant_bias_shift_error_m=max(abs(s['bias_shift_minus_point3_m']) for s in shifts),readback_optimizer_calls=0,formal_runs=0)
 if freeze['mode']=='explore':
  from diagnose import run as audit_previous
  audit_previous(out/'historical');report['continuation_readback']=continuation_readback()
 write(out/'READBACK.json',report);plots(rows,peerrows,cfg,out);print(json.dumps(report,indent=2))

def plots(rows,peer,cfg,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 d=out/'figures';d.mkdir();conditions=[c['id'] for c in cfg['conditions']];colors={'M0':'#777777','M1':'#2978b5','M2':'#dd6d35'}
 fig,axes=plt.subplots(3,4,figsize=(15,9),layout='constrained')
 for w in range(3):
  for k,c in enumerate(conditions):
   ax=axes[w,k]
   for m in cfg['methods']:
    s=[r for r in peer if r['window']==w and r['condition']==c and r['method']==m and r['seed']==cfg['seeds'][0]]
    if s:ax.plot([r['local_time_s'] for r in s],[r['model_minus_measurement_m'] for r in s],'-o',ms=3,color=colors[m],label=m)
   ax.axhline(0,color='k',lw=.5);ax.set_title(f'w{w} {c}');ax.set_xlabel('local time (s)');ax.set_ylabel('peer residual (m)');ax.grid(alpha=.2)
 axes[0,0].legend();fig.suptitle('Fixed first seed; M0 peer residual is unused diagnostic');fig.savefig(d/'peer_first_seed.png',dpi=140);plt.close(fig)
 fig,axes=plt.subplots(2,3,figsize=(14,7),layout='constrained')
 for w in range(3):
  for car in [1,2]:
   ax=axes[car-1,w]
   for k,c in enumerate(conditions):
    for mi,m in enumerate(cfg['methods']):
     s=[r for r in rows if r['window']==w and r['condition']==c and r['method']==m and r['finite']]
     for r in s:ax.scatter(k+(mi-1)*.22,r[f'car{car}_rmse_m'],s=15,color=colors[m],marker='o' if r['accepted'] else 'x',alpha=.7)
   ax.set_xticks(range(4),conditions,rotation=25);ax.set_ylabel(f'Car{car} RMSE (m)');ax.set_title(f'Window {w}');ax.grid(alpha=.2)
 fig.suptitle('All seeds: gray M0, blue M1, orange M2; x = not accepted');fig.savefig(d/'errors_all_seeds.png',dpi=140);plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
 for w,ax in enumerate(axes):
  for k,c in enumerate(conditions):
   s=[r for r in rows if r['window']==w and r['condition']==c and r['method']=='M2' and r['finite']]
   ax.scatter([k]*len(s),[r['bias_estimate_m'] for r in s],s=20)
   ax.plot([k-.2,k+.2],[np.mean(cfg['conditions'][k]['peer_curve_m'])]*2,'k-')
  ax.set_xticks(range(4),conditions,rotation=25);ax.set_title(f'Window {w}');ax.set_ylabel('constant b estimate (m)');ax.grid(alpha=.2)
 fig.suptitle('All seeds; black = descriptive curve mean, not a true constant target');fig.savefig(d/'bias_all_seeds.png',dpi=140);plt.close(fig)
 fig,axes=plt.subplots(1,3,figsize=(13,4),layout='constrained')
 for w,ax in enumerate(axes):
  for k,c in enumerate(conditions):
   s=[r for r in rows if r['window']==w and r['condition']==c and r['method']=='M2' and r['finite']]
   ax.scatter([k]*len(s),[r['peer_residual_late_minus_early_m'] for r in s],s=20)
  ax.axhline(0,color='k',lw=.7);ax.set_xticks(range(4),conditions,rotation=25);ax.set_ylabel('M2 late - early residual (m)');ax.set_title(f'Window {w}');ax.grid(alpha=.2)
 fig.suptitle('All seeds: remaining temporal structure; no detector or risk calibration');fig.savefig(d/'residual_structure_all_seeds.png',dpi=140);plt.close(fig)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();evaluate(a.input,a.out)
