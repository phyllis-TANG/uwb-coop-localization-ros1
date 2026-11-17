"""Independent residual arithmetic plus full-stage numerical readback; no solves."""
import csv,time
from fcommon import *
from objective import Field
from model import objective as old_objective

def huber(e):return e*np.sqrt(2/(np.sqrt(1+e*e)+1))
def independent(o,method,q,priors=False):
 n=len(o['times']);s=np.array(q[:6*n]).reshape(2,n,3);r=[];walls=[];antenna=[]
 for ci,c in enumerate(CARS):
  v=o['cars'][c];m=v['model'];p=m['graph_parameters'];local=np.array(v['local']);lever=np.array(m['base_to_antenna_body_xy_m'])
  ant=s[ci,:,:2]+np.array([rotation(t)@lever for t in s[ci,:,2]]);antenna.append(ant)
  if priors:
   yaw=np.deg2rad(m['initial_heading_deg']);xy=np.array(m['start_antenna_xyz_m'][:2])-rotation(yaw)@lever
   d=s[ci,0]-np.r_[xy,yaw];d[2]=np.arctan2(np.sin(d[2]),np.cos(d[2]));r.extend(d/np.array([p['prior_position_sigma_m']]*2+[np.deg2rad(p['prior_heading_sigma_deg'])]))
  for i,dt in enumerate(np.diff(o['times'])):
   measured=rotation(-local[i,2])@(local[i+1,:2]-local[i,:2]);predicted=rotation(-s[ci,i,2])@(s[ci,i+1,:2]-s[ci,i,:2])
   r.extend((predicted-measured)/(p['odom_translation_sigma_m']*np.sqrt(dt)))
   angle=(s[ci,i+1,2]-s[ci,i,2])-(local[i+1,2]-local[i,2]);r.append(np.arctan2(np.sin(angle),np.cos(angle))/(np.deg2rad(p['odom_yaw_sigma_deg'])*np.sqrt(dt)))
  for i,row in enumerate(v['observations']):
   for key,raw in sorted(row.items()):
    a=np.array(m['anchors_xyz_m'][key]);pred=np.linalg.norm(np.r_[ant[i],m['antenna_height_m']]-a);err=pred-(raw-m['range_bias_m'][key]);walls.append(err);r.append(huber(err/p['range_sigma_m']))
 tau=np.array(o['times'])-(o['times'][0]+o['times'][-1])/2;b=np.zeros(n)
 if method in ['F2','F3']:b+=q[6*n]
 if method=='F3':b+=q[-1]*tau
 peer=[]
 dz=o['cars']['car1']['model']['antenna_height_m']-o['cars']['car2']['model']['antenna_height_m']
 for i,row in enumerate(o['peers']):
  if row['range_m'] is None:continue
  dist=np.sqrt(np.sum((antenna[0][i]-antenna[1][i])**2)+dz*dz);raw=dist-row['range_m'];peer.append([i,raw,raw+b[i],b[i]])
  if method!='F0':r.append(huber((raw+b[i])/o['peer_sigma_m']))
 return np.array(r),np.array(antenna),np.array(walls),np.array(peer),b

def csvsave(p,rows):
 fields=list(dict.fromkeys(k for x in rows for k in x))
 with Path(p).open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(clean(rows))

def audit(out,dest):
 out=Path(out);dest=Path(dest);dest.mkdir(parents=True,exist_ok=True);cfg=read(DOC/'CONFIG.json');run=read(out/'RUN.json')
 for p,h in run['freeze']['hashes'].items():assert digest(ROOT/p)==h,p
 assert digest(DOC/'ACCEPTANCE.json')==run['freeze']['acceptance_sha256']
 attempts=list((out/'attempts').glob('*.json'));results=list((out/'estimates').glob('*.json'));assert len(attempts)==len(results)==read(out/'COMPLETE.json')['calls']<=38
 assert sorted(read(p)['call'] for p in attempts)==list(range(1,len(attempts)+1))
 numerics=[];continuation=[];trajectories=[];residuals=[];comparisons=[];endpoint=[];cache={};max_rdiff=0.;max_jdiff=0.
 for p in sorted(results):
  name=p.stem;e=read(p);attempt=read(out/'attempts'/p.name);o=read(out/'measurements'/(attempt['source']+'.json'));isold=name.startswith('old_')
  if isold:method='F1' if name.endswith('_joint') else 'F0';f=old_objective(o,method=='F1');label='old_continuation'
  else:case,method,stage=name.split('_');f=Field(o,method);label=stage
  if 'failure' in e:numerics.append({'run':name,'failure':e['failure']});continue
  q=np.array(e['x']);r,j=f.evaluate(q);rr,ant,wall,peer,b=independent(o,method,q,isold)
  diff=float(max(abs(rr-r)));max_rdiff=max(max_rdiff,diff);assert diff<1e-10
  np.testing.assert_allclose(r,e['residual'],atol=1e-12,rtol=0)
  assert __import__('hashlib').sha256(j.tobytes()).hexdigest()==e['jacobian_sha256']
  g=j.T@r;assert abs(max(abs(g))-e['gradient_inf'])<1e-10
  assert bool(max(abs(g))<=1e-5)==e['stationary_1e_5'];assert abs(r@r/2-e['cost'])<1e-9
  # Independent-residual directional derivatives at every endpoint; deterministic directions.
  for k in range(2):
   v=np.sin(np.arange(len(q))*.71+k+.3);v/=np.linalg.norm(v);h=1e-5
   fd=(independent(o,method,q+h*v,isold)[0]-independent(o,method,q-h*v,isold)[0])/(2*h)
   err=float(max(abs(fd-j@v)));max_jdiff=max(max_jdiff,err);assert err<1e-5,err
  scale=np.array(attempt['scales']);sv=np.linalg.svd(j*scale,compute_uv=False);tol=sv[0]*max(j.shape)*np.finfo(float).eps;rank=int(np.sum(sv>tol));full=rank==len(q)
  row={'run':name,'stage':label,'method':method,'finite':e['finite'],'scipy_success':e['scipy_success'],'stationary_1e_5':e['stationary_1e_5'],'gradient_inf':e['gradient_inf'],'scaled_gradient_inf':float(max(abs(g*scale))),'cost':e['cost'],'nfev':e['nfev'],'elapsed_s':e['elapsed_s'],'rank':rank,'dimension':len(q),'scaled_smin':float(sv[-1]),'scaled_condition':float(sv[0]/sv[-1]) if full else None,'wall_rms_m':float(np.sqrt(np.mean(wall**2))),'peer_raw_rms_m':float(np.sqrt(np.mean(peer[:,1]**2))) if len(peer) else None,'peer_corrected_rms_m':float(np.sqrt(np.mean(peer[:,2]**2))) if len(peer) else None,'b0_m':float(q[6*len(o['times'])]) if method in ['F2','F3'] else None,'b1_mps':float(q[-1]) if method=='F3' else None,'accepted_stationary_fullrank':bool(e['scipy_success'] and e['stationary_1e_5'] and full)}
  numerics.append(row)
  if isold:
   old=read(out/'diagnosis'/(name[4:]+'.json'))['old'];dq=q-np.array(old['x']);_,oa,_,_,_=independent(o,method,np.array(old['x']),True)
   continuation.append({'run':name,'old_gradient':old['gradient_inf'],'new_gradient':e['gradient_inf'],'max_body_xy_change_m':float(np.max(np.linalg.norm(dq.reshape(2,-1,3)[:,:,:2],axis=2))),'max_antenna_change_m':float(np.max(np.linalg.norm(ant-oa,axis=2))),'cost_change':e['cost']-old['cost'],'accepted':e['stationary_1e_5']})
  elif label=='P1':
   cache[(case,method)]=(ant,row)
   s=q[:6*len(o['times'])].reshape(2,-1,3)
   for ci,c in enumerate(CARS):
    for i,t in enumerate(o['times']):trajectories.append({'case':case,'method':method,'car':c,'t_s':t,'body_x_m':s[ci,i,0],'body_y_m':s[ci,i,1],'yaw_rad':s[ci,i,2],'antenna_x_m':ant[ci,i,0],'antenna_y_m':ant[ci,i,1],'bias_m':b[i]})
   for i,raw,corr,bias in peer:
    p=o['peers'][int(i)];residuals.append({'case':case,'method':method,'t_s':o['times'][int(i)],'raw_geometry_residual_m':raw,'after_bias_residual_m':corr,'bias_m':bias,'direction_1_m':p['directions_m'][0],'direction_2_m':p['directions_m'][1],'samples_1':p['direction_counts'][0],'samples_2':p['direction_counts'][1]})
 for case in cfg['fit_cases']:
  for method in cfg['methods'][1:]:
   if (case,method) not in cache or (case,'F0') not in cache:continue
   for ci,c in enumerate(CARS):
    d=np.linalg.norm(cache[case,method][0][ci]-cache[case,'F0'][0][ci],axis=1)
    comparisons.append({'case':case,'method':method,'car':c,'rms_difference_from_F0_m':float(np.sqrt(np.mean(d*d))),'max_difference_from_F0_m':float(max(d)),'both_stationary_fullrank':bool(cache[case,method][1]['accepted_stationary_fullrank'] and cache[case,'F0'][1]['accepted_stationary_fullrank'])})
 # Only accessible manual final references; never used by solver.
 oldp=read(ROOT/'docs/field_tests/two_car_updated_comparison_20261022/protocol.json')
 for item in oldp['cases']:
  case=item['id'];o=read(out/'measurements'/f'{case}.json')
  for method in cfg['methods']:
   if (case,method) not in cache:continue
   for ci,c in enumerate(CARS):
    a=cache[case,method][0][ci];ref=np.array(item['evaluation_only']['end_antenna_xyz_m'][c][:2]);loc=np.array(o['cars'][c]['local'])
    endpoint.append({'case':case,'method':method,'car':c,'last5_antenna_mean_to_manual_end_m':float(np.linalg.norm(a[-5:].mean(0)-ref)),'last5_odom_path_m':float(np.linalg.norm(np.diff(loc[-5:,:2],axis=0),axis=1).sum()),'scope':'manual endpoint difference; not full trajectory accuracy'})
 for name,rows in [('NUMERICS',numerics),('CONTINUATION',continuation),('TRAJECTORIES',trajectories),('PEER_RESIDUALS',residuals),('METHOD_DIFFERENCES',comparisons),('MANUAL_ENDPOINT_DIFFERENCES',endpoint)]:csvsave(dest/(name+'.csv'),rows)
 final=[x for x in numerics if x.get('stage')=='P1'];write(dest/'READBACK.json',{'passed':True,'optimizer_calls':0,'batch_calls':len(attempts),'formal_runs':0,'old_continuations':len(continuation),'full_final_runs':len(final),'full_stationary':sum(x['stationary_1e_5'] for x in final),'full_stationary_fullrank':sum(x['accepted_stationary_fullrank'] for x in final),'max_independent_residual_difference':max_rdiff,'max_independent_directional_jacobian_difference':max_jdiff,'all_source_hashes_unchanged':True})
if __name__=='__main__':audit(*sys.argv[1:])
