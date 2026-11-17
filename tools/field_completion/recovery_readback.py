"""Read back all P2 endpoints; preserve P0/P1 and quantify numerical changes."""
from fcommon import *
from objective import Field
from readback import independent,csvsave

def audit(batch,recovery,dest):
 batch=Path(batch);recovery=Path(recovery);dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 run=read(recovery/'RUN.json');cfg=read(DOC/'CONFIG.json')
 for p,h in run['freeze']['hashes'].items():assert digest(ROOT/p)==h,p
 for p,h in run['freeze']['source_batch_hashes'].items():assert digest(batch/p)==h,p
 results=list((recovery/'estimates').glob('*.json'));attempts=list((recovery/'attempts').glob('*.json'));assert len(results)==len(attempts)==read(recovery/'COMPLETE.json')['calls']==16
 assert sorted(read(p)['call'] for p in attempts)==list(range(1,17))
 nums=[];changes=[];traj=[];peers=[];differences=[];ends=[];cache={};maxrd=0.;maxjd=0.
 for p in sorted(results):
  case,method,stage=p.stem.split('_');o=read(recovery/'measurements'/f'{case}.json');e=read(p);prev=read(batch/'estimates'/f'{case}_{method}_P1.json');f=Field(o,method)
  a=read(recovery/'attempts'/p.name);assert a['parent_sha256']==digest(batch/'estimates'/f'{case}_{method}_P1.json');assert a['initial']==prev['x']
  if 'failure' in e:nums.append({'case':case,'method':method,'failure':e['failure']});continue
  q=np.array(e['x']);r,j=f.evaluate(q);rr,ant,wall,peer,b=independent(o,method,q);diff=float(max(abs(rr-r)));maxrd=max(maxrd,diff);assert diff<1e-10
  np.testing.assert_allclose(r,e['residual'],atol=1e-12,rtol=0);g=j.T@r
  assert __import__('hashlib').sha256(j.tobytes()).hexdigest()==e['jacobian_sha256'];assert abs(r@r/2-e['cost'])<1e-9
  assert abs(max(abs(g))-e['gradient_inf'])<1e-10;assert bool(max(abs(g))<=1e-5)==e['stationary_1e_5']
  for k in range(2):
   v=np.cos(np.arange(len(q))*.39+k);v/=np.linalg.norm(v);h=1e-5
   fd=(independent(o,method,q+h*v)[0]-independent(o,method,q-h*v)[0])/(2*h);err=float(max(abs(fd-j@v)));maxjd=max(maxjd,err);assert err<1e-5
  sv=np.linalg.svd(j*f.scales,compute_uv=False);rank=int(sum(sv>sv[0]*max(j.shape)*np.finfo(float).eps));full=rank==len(q)
  row={'case':case,'method':method,'stage':'P2','finite':e['finite'],'scipy_success':e['scipy_success'],'status':e['scipy_status'],'stationary_1e_5':e['stationary_1e_5'],'accepted_stationary_fullrank':bool(e['scipy_success'] and e['stationary_1e_5'] and full),'gradient_inf':e['gradient_inf'],'cost':e['cost'],'nfev':e['nfev'],'elapsed_s':e['elapsed_s'],'rank':rank,'dimension':len(q),'scaled_smin':sv[-1],'scaled_condition':float(sv[0]/sv[-1]) if full else None,'wall_rms_m':float(np.sqrt(np.mean(wall**2))),'peer_raw_rms_m':float(np.sqrt(np.mean(peer[:,1]**2))),'peer_corrected_rms_m':float(np.sqrt(np.mean(peer[:,2]**2))),'b0_m':q[f.posdim] if f.extra else None,'b1_mps':q[-1] if f.extra==2 else None}
  nums.append(row);cache[case,method]=(ant,row)
  _,pa,_,_,_=independent(o,method,np.array(prev['x']));delta=np.linalg.norm(ant-pa,axis=2)
  changes.append({'case':case,'method':method,'previous_gradient':prev['gradient_inf'],'new_gradient':e['gradient_inf'],'max_antenna_change_m':float(max(delta.ravel())),'rms_antenna_change_m':float(np.sqrt(np.mean(delta**2))),'cost_change':e['cost']-prev['cost'],'P2_accepted':row['accepted_stationary_fullrank']})
  s=q[:f.posdim].reshape(2,-1,3)
  for ci,c in enumerate(CARS):
   for i,t in enumerate(o['times']):traj.append({'case':case,'method':method,'car':c,'t_s':t,'body_x_m':s[ci,i,0],'body_y_m':s[ci,i,1],'yaw_rad':s[ci,i,2],'antenna_x_m':ant[ci,i,0],'antenna_y_m':ant[ci,i,1],'bias_m':b[i]})
  for i,raw,corr,bias in peer:
   pr=o['peers'][int(i)];peers.append({'case':case,'method':method,'t_s':o['times'][int(i)],'raw_geometry_residual_m':raw,'after_bias_residual_m':corr,'bias_m':bias,'direction_1_m':pr['directions_m'][0],'direction_2_m':pr['directions_m'][1],'samples_1':pr['direction_counts'][0],'samples_2':pr['direction_counts'][1]})
 for case in cfg['fit_cases']:
  for method in cfg['methods'][1:]:
   if (case,method) not in cache or (case,'F0') not in cache:continue
   for ci,c in enumerate(CARS):
    d=np.linalg.norm(cache[case,method][0][ci]-cache[case,'F0'][0][ci],axis=1);differences.append({'case':case,'method':method,'car':c,'rms_difference_from_F0_m':float(np.sqrt(np.mean(d*d))),'max_difference_from_F0_m':float(max(d))})
 proto=ROOT/'docs/field_tests/two_car_updated_comparison_20261022/protocol.json'
 for item in read(proto)['cases']:
  case=item['id'];o=read(recovery/'measurements'/f'{case}.json')
  for method in cfg['methods']:
   if (case,method) not in cache:continue
   for ci,c in enumerate(CARS):
    ant=cache[case,method][0][ci];ref=np.array(item['evaluation_only']['end_antenna_xyz_m'][c][:2]);local=np.array(o['cars'][c]['local'])
    ends.append({'case':case,'method':method,'car':c,'last5_antenna_mean_to_manual_end_m':float(np.linalg.norm(ant[-5:].mean(0)-ref)),'last5_odom_path_m':float(np.linalg.norm(np.diff(local[-5:,:2],axis=0),axis=1).sum()),'scope':'manual endpoint difference, not full-trajectory accuracy'})
 for name,rows in [('NUMERICS',nums),('P1_TO_P2',changes),('TRAJECTORIES',traj),('PEER_RESIDUALS',peers),('METHOD_DIFFERENCES',differences),('MANUAL_ENDPOINT_DIFFERENCES',ends)]:csvsave(dest/(name+'.csv'),rows)
 write(dest/'READBACK.json',{'passed':True,'optimizer_calls':0,'recovery_calls':16,'total_calls':read(batch/'COMPLETE.json')['calls']+16,'formal_runs':0,'finite':sum(x.get('finite',False) for x in nums),'stationary_fullrank_accepted':sum(x.get('accepted_stationary_fullrank',False) for x in nums),'max_independent_residual_difference':maxrd,'max_independent_directional_jacobian_difference':maxjd,'evaluation_reference_sha256':digest(proto)})
if __name__=='__main__':audit(*sys.argv[1:])
