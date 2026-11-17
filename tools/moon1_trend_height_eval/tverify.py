"""Zero-optimizer reconstruction of inputs, every stage, covariance, labels and statistics."""
import argparse
from tcommon import *
from tinputs import verify
from tmodel import problem,independent,information,classify,tau
from tstats import aggregate
from tplots import plot

def evaluate(source,out):
 source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=False);e=Evidence(source);fr=read(source/'FREEZE.json');execution=read(source/'EXECUTION.json');plan=read(source/'PLAN.json');run=read(source/'RUN.json');cfg=fr['config'];mode=fr['mode']
 assert fr['source_sha256']==sources(),'FROZEN_SOURCE_CHANGED'
 history=unpack(DOC/'HISTORY_SHA256.json.gz')
 for name,meta in history['files'].items():
  sha=hashlib.sha256(os.readlink(ROOT/name).encode()).hexdigest() if meta['kind']=='symlink' else filehash(ROOT/name)
  assert sha==meta['sha256'],'HISTORY_CHANGED '+name
 if (source/'MANIFEST.json').exists():
  man=read(source/'MANIFEST.json')
  for name,meta in man['files'].items():assert filehash(source/name)==meta['sha256']
  for name,sha in man['original_json_sha256'].items():assert hashlib.sha256((json.dumps(e.get(name),indent=2,allow_nan=False)+'\n').encode()).hexdigest()==sha
 assert len({(x['window'],x['seed'],x['height_sigma_m'],x['condition']) for x in plan})==len(plan)
 rows=[];stage_rows=[];peer=[];heightrows=[];same={};m0same={};m0est={};zero={};maxr=0.;maxj=0.;maxg=0.;maxcov=0.;fdmax=0.;calls=0;orphan=0;finished=0
 firstseed=fr['seeds']['seeds'][0] if mode=='explore' else fr['seeds']['development_seed']
 for item in plan:
  uid=item['id'];o=e.get('measurements/'+uid+'.json');ref=e.get('reference/'+uid+'.json');verify(o,ref)
  assert ref['condition']['id']==item['condition'] and ref['seed']==item['seed'] and ref['height_sigma_m']==item['height_sigma_m']
  key=(item['window'],item['seed']);shared=dict(noise=ref['standard_noise'],height=ref['height_standard'],prior=o['prior_center_xy_m'],motion=o['global_xy_increments_m'])
  same.setdefault(key,digest(shared));assert same[key]==digest(shared)
  nonheight={k:v for k,v in o.items() if k!='heights_m'};zk=(*key,item['condition'])
  if item['height_sigma_m']==0:zero[zk]=(digest(nonheight),uid)
  else:assert zero[zk]==(digest(nonheight),item['sigma0_unit'])
  heightrows.append(dict(unit=uid,window=item['window'],seed=item['seed'],condition=item['condition'],height_sigma_m=item['height_sigma_m'],car1_standard=ref['height_standard'][0],car2_standard=ref['height_standard'][1],car1_error_m=ref['height_errors_m'][0],car2_error_m=ref['height_errors_m'][1],sigma0_unit=item['sigma0_unit']))
  truth=np.array(ref['track']['antenna_xyz_m'])[:,:,:2];baseline=None
  for method in cfg['methods']:
   name=uid+'-'+method;fun,init,receipt=problem(o,method);records={};last=None
   if method=='M0':
    mk=(*key,item['height_sigma_m']);m0same.setdefault(mk,(receipt,init.tolist()));assert m0same[mk]==(receipt,init.tolist())
   for stage in ['P0','P1']:
    try:a=e.get('attempts/'+name+'-'+stage+'.json')
    except (KeyError,FileNotFoundError):continue
    calls+=1;assert a['input_sha256']==digest(o) and a['consumed_sha256']==receipt;assert a['settings']==fr['solver'][stage]
    assert a['code_sha']==fr['commit'] and a['source_hash']==digest(fr['source_sha256']) and a['execution_sha256']==filehash(source/'EXECUTION.json')
    np.testing.assert_array_equal(a['start'],init if stage=='P0' else records['P0']['estimate'])
    try:s=e.get('estimates/'+name+'/'+stage+'.json')
    except (KeyError,FileNotFoundError):
     orphan+=1;stage_rows.append(dict(id=name,stage=stage,status='ORPHAN_ATTEMPT',accepted=False,nfev=None,njev=None,cost=None,gradient_inf=None,scaled_gradient_inf=None,scipy_status=None,range_rank=None,data_rank=None,total_rank=None,dimension=None,elapsed_s=None));continue
    finished+=1;records[stage]=s;last=s
    if s['estimate'] is not None:
     q=np.array(s['estimate']);r,j=independent(o,method,q);rr,jj=fun(q);maxr=max(maxr,float(max(abs(r-rr))));maxj=max(maxj,float(np.max(abs(j-jj))));maxg=max(maxg,float(max(abs(j.T@r-np.array(s['gradient'])))))
     np.testing.assert_allclose(r,s['residual'],atol=1e-10,rtol=0);assert abs(r@r/2-s['cost'])<1e-9
     assert classify(q,r,j,s['scipy_status'],s['scipy_success'])==s['status'];assert s['accepted']==(s['status']=='ACCEPTED')
     nr=48 if method=='M0' else 54
     for info_key,mat in [('range_information',j[:nr]),('data_information',j[:-4]),('total_information',j)]:
      info=information(mat);saved=s[info_key];assert info['rank']==saved['rank'];np.testing.assert_allclose(info['singular_values'],saved['singular_values'],atol=1e-10,rtol=1e-10)
      if info['rank']==len(q):
       cov=np.linalg.solve(mat.T@mat,np.eye(len(q)));blocks=np.stack([cov[i:i+2,i:i+2] for i in range(0,24,2)]).reshape(6,2,2,2)
       maxcov=max(maxcov,float(np.max(abs(blocks-np.array(saved['position_covariance_blocks'])))))
       if len(q)>24:np.testing.assert_allclose(cov[24:,24:],saved['bias_covariance'],atol=1e-9,rtol=1e-8)
      else:assert saved['position_covariance_blocks'] is None
     if stage=='P1' and item['seed']==firstseed:
      eps=1e-5;fd=np.column_stack([(independent(o,method,q+d)[0]-independent(o,method,q-d)[0])/(2*eps) for d in np.eye(len(q))*eps]);fdmax=max(fdmax,float(np.max(abs(fd-j))))
    stage_rows.append(dict(id=name,stage=stage,status=s['status'],accepted=s['accepted'],nfev=s.get('nfev'),njev=s.get('njev'),cost=s.get('cost'),gradient_inf=s.get('gradient_inf'),scaled_gradient_inf=s.get('scaled_gradient_inf'),scipy_status=s.get('scipy_status'),range_rank=s.get('range_information',{}).get('rank'),data_rank=s.get('data_information',{}).get('rank'),total_rank=s.get('total_information',{}).get('rank'),dimension=len(s['estimate']) if s['estimate'] is not None else None,elapsed_s=s.get('elapsed_s')))
   try:final=e.get('estimates/'+name+'/FINAL.json')
   except (KeyError,FileNotFoundError):final=dict(status='PROCESS_FAILURE',accepted=False,estimate=None,stage=None)
   finite=final['estimate'] is not None
   if finite:
    chosen=records[final['stage']];np.testing.assert_array_equal(chosen['estimate'],final['estimate'])
    if 'P1' in records and records['P1']['estimate'] is not None:assert final['stage']=='P1' and final['accepted']==records['P1']['accepted']
    else:assert not final['accepted']
   else:chosen={}
   row=dict(unit=uid,part=item['part'],window=item['window'],seed=item['seed'],condition=item['condition'],height_sigma_m=item['height_sigma_m'],method=method,status=final['status'],finite=finite,accepted=final['accepted'],car1_mse_m2=None,car2_mse_m2=None,car1_rmse_m=None,car2_rmse_m=None,relative_mse_m2=None,relative_rmse_m=None,car1_benefit_m2=None,car2_benefit_m2=None,paired_accepted=False,b0_m=None,b1_m_per_s=None,peer_rms_m=None,peer_late_minus_early_m=None,car1_cov_trace_m2=None,car2_cov_trace_m2=None,total_condition=chosen.get('total_information',{}).get('condition'),gradient_inf=chosen.get('gradient_inf'),cost=chosen.get('cost'),nfev=sum(s.get('nfev') or 0 for s in records.values()),optimizer_calls=len(records))
   if finite:
    q=np.array(final['estimate']);xy=q[:24].reshape(6,2,2);err=xy-truth;mse=np.mean(np.sum(err**2,axis=2),axis=0);rel=float(np.mean(np.sum((err[:,1]-err[:,0])**2,axis=1)));b0=q[24] if len(q)>=25 else 0.;b1=q[25] if len(q)==26 else 0.
    h=np.array(o['heights_m']);geom=np.sqrt(np.sum((xy[:,1]-xy[:,0])**2,axis=1)+(h[:,1]-h[:,0])**2);pred=geom+b0+b1*tau(o);pr=pred-np.array(o['ranges_m'])[8::9]
    row.update(car1_mse_m2=float(mse[0]),car2_mse_m2=float(mse[1]),car1_rmse_m=float(np.sqrt(mse[0])),car2_rmse_m=float(np.sqrt(mse[1])),relative_mse_m2=rel,relative_rmse_m=float(np.sqrt(rel)),b0_m=float(b0) if len(q)>=25 else None,b1_m_per_s=float(b1) if len(q)==26 else None,peer_rms_m=float(np.sqrt(np.mean(pr**2))),peer_late_minus_early_m=float(np.mean(pr[3:])-np.mean(pr[:3])))
    blocks=chosen.get('total_information',{}).get('position_covariance_blocks')
    if blocks is not None:
     trace=np.mean(np.trace(np.array(blocks),axis1=2,axis2=3),axis=0);row.update(car1_cov_trace_m2=float(trace[0]),car2_cov_trace_m2=float(trace[1]))
    for t in range(6):peer.append(dict(unit=uid,window=item['window'],seed=item['seed'],condition=item['condition'],height_sigma_m=item['height_sigma_m'],method=method,accepted=row['accepted'],epoch=t,local_time_s=float(o['times_s'][t]-o['times_s'][0]),tau_s=float(tau(o)[t]),injected_m=ref['condition']['curve_m'][t],fitted_bias_m=float(b0+b1*tau(o)[t]),residual_m=float(pr[t]),used=method!='M0'))
    if method=='M0':
     mk=(*key,item['height_sigma_m']);m0est.setdefault(mk,final['estimate']);np.testing.assert_array_equal(final['estimate'],m0est[mk])
   if method=='M0':baseline=row
   if finite and baseline['finite']:
    for c in [1,2]:row[f'car{c}_benefit_m2']=baseline[f'car{c}_mse_m2']-row[f'car{c}_mse_m2']
    row['paired_accepted']=row['accepted'] and baseline['accepted']
   rows.append(row)
 assert maxr<1e-10 and maxj<1e-10 and maxg<1e-8 and maxcov<1e-8 and fdmax<2e-6
 assert calls==run['reserved_calls'] and finished==run['completed_calls'] and orphan==run['orphan_attempts'] and len(rows)==run['planned_methods']
 csvwrite(out/'PER_WINDOW.csv',rows);csvwrite(out/'STAGES.csv',stage_rows);csvwrite(out/'PEER_RESIDUALS.csv',peer);csvwrite(out/'HEIGHT_REALIZATIONS.csv',heightrows)
 seedrows,contrasts,den=aggregate(rows,out,3 if mode=='explore' else 1)
 plot(seedrows,contrasts,peer,firstseed,out/'figures')
 report=dict(passed=True,planned=len(rows),finite=sum(r['finite'] for r in rows),accepted=sum(r['accepted'] for r in rows),failed=sum(not r['accepted'] for r in rows),unavailable=sum(not r['finite'] for r in rows),reserved_calls=calls,completed_calls=finished,orphan_attempts=orphan,residual_max=maxr,jacobian_max=maxj,gradient_max=maxg,covariance_block_max=maxcov,fd_jacobian_max=fdmax,paired_inputs=True,height_only_estimator_geometry=True,M0_peer_invariant_at_each_height=True,sigma_zero_not_resolved=True,source_hash_unchanged=True,readback_optimizer_calls=0,formal_runs=0)
 write(out/'READBACK.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();evaluate(a.input,a.out)
