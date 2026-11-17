"""All 1800 saved endpoints; SVD decomposition and all PR121 position blocks."""
from regions import *
from test_math import tests
import argparse,collections

def endpoints():
 inputs={r['id']:r['input'] for r in records(A/'INPUTS.jsonl.gz')};selection={(r['id'],r['method']):r for r in json.loads((A/'readback/SELECTION.json').read_text())};metrics={(r['id'],r['method'],r['init']):r for r in readcsv(A/'readback/ENDPOINT_METRICS.csv')}
 with np.load(A/'readback/POINTS.npz') as z:points={k:z[k] for k in z.files}
 groupmap={}
 for r in readcsv(A/'readback/GROUPS.csv'):
  for ini in r['members'].split(';'):groupmap[(r['id'],r['method'],ini,r['kind'])]=r['group']
 for r in records(A/'ENDPOINTS.jsonl.gz'):
  u=inputs[r['id']];q=u['condition'];s=selection[r['id'],r['method']];old=metrics[r['id'],r['method'],r['init']];idx=int(old['index']);fin=r['stages']['P1'];x=np.array(fin['estimate']);a=affine(u,r['method'])
  meta=dict(batch='PR119',id=r['id'],condition=q['id'],geometry=q['geometry'],perturbation_m=q['perturbation_m'],sigma=q['prior_sigma'],offset_m=0,seed=u['seed'],method=r['method'],init=r['init'],accepted=fin['accepted'],category=fin['category'],original=r['init']=='I0',selected=idx==s['selected_index'],selected_group=idx in s['selected_group_indices'],accepted_groups=s['accepted_groups'],finite_groups=s['finite_groups'],finite_group=groupmap.get((r['id'],r['method'],r['init'],'finite')),accepted_group=groupmap.get((r['id'],r['method'],r['init'],'accepted')),legacy_index=idx)
  for car in range(2):
   meta[f'old_coverage95_car{car+1}']=float(np.mean(points['q'][idx,0,car::2]<=chi2.ppf(.95,2)));meta[f'old_area95_car{car+1}']=float(np.mean(points['area95'][idx,0,car::2]))
  yield meta,u,x,a,fin,None
 for r in records(B/'EVIDENCE.jsonl.gz'):
  if r['type']!='UNIT':continue
  v=r['value'];u=v['input'];item=v['item'];q=item['condition'];fin=v['stages']['P1']['result']['payload']['value'];x=np.array(fin['estimate']);a=affine(u,'B2');assert max(abs(a['x']+a['delta']-v['linear']['estimate']))<1e-9
  meta=dict(batch='PR121',id=item['id'],condition=q['id'],geometry=q['geometry'],perturbation_m=None,sigma=q['prior_sigma'],offset_m=q['delta_m'],seed=item['seed'],method='B2',init='I0',accepted=fin['accepted'],category=fin['category'],original=True,selected=None,selected_group=None,accepted_groups=None,finite_groups=None,finite_group=None,accepted_group=None,legacy_index=None)
  yield meta,u,x,a,fin,v

def regional(meta,u,x,a):
 G,T,structure_error=structural_gains(u,a);delta=np.array(u['obs']['prior_center'])-a['x'][:4];eps=-a['r'][:74];pred=G@eps+T@delta
 assert max(abs(pred-a['delta']))<1e-9
 rows=[];mat=[];supportcheck=0.
 for t in range(6):
  for car in range(2):
   sl=slice(4*t+2*car,4*t+2*car+2);F=G[sl];BB=T[sl];Q=np.array([[1.],[0.]]) if u['condition']['geometry']=='weak' and t==0 else None;z=factor_support(F,Q)
   # Independent covariance response from unscaled least squares (not truncated).
   independent=np.linalg.lstsq(a['j'],np.eye(78),rcond=None)[0][:,:74][sl];assert np.max(abs(F@F.T-independent@independent.T))<1e-10
   eL=a['delta'][sl];noise=eL-BB@delta;supportcheck=max(supportcheck,float(np.linalg.norm(noise-z['Q']@(z['Q'].T@noise))))
   mat.append(dict(id=meta['id'],epoch=t,car=car+1,rank=z['rank'],reason=z['reason'],noise_gain=F,support=z['Q'],covariance=F@F.T,bias_gain=BB,mean=BB@delta))
   for model,error in [('AFFINE',eL),('NL_COMPARE',(x-a['x'])[sl])]:
    for scope,alpha in [('point95',.05),('joint95',.05/12)]:
     for kind,rho in [('noise_support',0.),('outer_circle',0.),('outer_circle',.01),('outer_circle',.05)]:
      out=region(z,error,BB,rho,alpha,kind)
      rows.append(dict(**meta,model=model,epoch=t,car=car+1,scope=scope,block_alpha=alpha,kind=kind,rho=rho,in_set=bool(np.linalg.norm(delta)<=rho+1e-12),error_x=error[0],error_y=error[1],error_norm=np.linalg.norm(error),**out))
 return rows,mat,structure_error,supportcheck

def metrics(meta,u,x,a,z):
 n=len(x);d=a['d'];vs=np.vstack([z['terms'],z['terms'].sum(0),z['difference'],z['dn'],z['dl']]);names=['gradient','remainder','jacobian','sum','difference','nonlinear_error','affine_error'];row=dict(**meta,available=True,reason='AVAILABLE',state_dimension=n,rank=n,condition_j=a['s'][0]/a['s'][-1],condition_h=(a['s'][0]/a['s'][-1])**2,independent_affine_difference=a['independent_difference'],reconstruction_max=z['reconstruction_max'],backward_error=z['backward_error'],residual_norm=z['residual_norm'],eta_norm=z['eta_norm'],delta_j_norm=z['delta_j_norm'],gradient_inf=max(abs(z['gradient'])),weak0_dimension=z['weak0'].shape[1],weakN_dimension=z['weakN'].shape[1])
 for rtol in CFG['rank_sensitivity']:row['rank_'+str(rtol)]=int(sum(a['s']>rtol*a['s'][0]))
 for name,v in zip(names,vs):
  row[name+'_position_rms']=np.linalg.norm(v[:24])/np.sqrt(12);row[name+'_weak0_norm']=np.linalg.norm(z['weak0'].T@(v/d));row[name+'_weakN_norm']=np.linalg.norm(z['weakN'].T@(v/d));row[name+'_bias']=v[-1] if n==25 else None;row[name+'_bias_abs']=abs(v[-1]) if n==25 else None
  for car in range(2):row[name+f'_car{car+1}_rms']=np.linalg.norm(v[:24].reshape(6,2,2)[:,car])/np.sqrt(6)
 den=sum(np.linalg.norm(v[:24]) for v in z['terms']);row['position_cancellation']=1-np.linalg.norm(z['terms'].sum(0)[:24])/den if den else None
 for i,j in [(0,1),(0,2),(1,2)]:
  vi,vj=z['terms'][i,:24],z['terms'][j,:24];dd=np.linalg.norm(vi)*np.linalg.norm(vj);row[f'cos_{names[i]}_{names[j]}']=vi@vj/dd if dd else None
 return row,dict(**meta,dimension=n,reference=a['x'],affine_delta=z['dl'],nonlinear_delta=z['dn'],terms=z['terms'],difference=z['difference'],weak0=z['weak0'],weakN=z['weakN'],singular_values=a['s'],gradient=z['gradient'])

def main(out):
 out.mkdir(parents=True,exist_ok=False);count=source_check();save(out/'TESTS.json',tests());rows=[];regions=[];cat=collections.Counter();checks=dict(source_files=count,endpoint_cost_max=0.,endpoint_gradient_max=0.,affine_saved_max=0.,structural_gain_max=0.,centered_noise_support_max=0.);vectors=gzip.open(out/'VECTORS.jsonl.gz','wt');mats=gzip.open(out/'REGION_MATRICES.jsonl.gz','wt');identities=set()
 try:
  for meta,u,x,a,fin,v in endpoints():
   key=(meta['batch'],meta['id'],meta['method'],meta['init']);assert key not in identities;identities.add(key);cat[meta['batch']+'/'+meta['category']]+=1
   a,z=decompose(u,meta['method'],x,a);cost=float(z['r']@z['r']/2);grad=float(max(abs(z['gradient'])));checks['endpoint_cost_max']=max(checks['endpoint_cost_max'],abs(cost-fin['cost']));checks['endpoint_gradient_max']=max(checks['endpoint_gradient_max'],abs(grad-fin['gradient_inf']));assert abs(cost-fin['cost'])<1e-8 and abs(grad-fin['gradient_inf'])<1e-8
   row,vec=metrics(meta,u,x,a,z);rows.append(row);vectors.write(json.dumps(clean(vec),separators=(',',':'))+'\n')
   if meta['batch']=='PR121':
    rr,mm,err,sp=regional(meta,u,x,a);regions.extend(rr)
    for mat in mm:mats.write(json.dumps(clean(mat),separators=(',',':'))+'\n')
    checks['structural_gain_max']=max(checks['structural_gain_max'],err);checks['centered_noise_support_max']=max(checks['centered_noise_support_max'],sp);checks['affine_saved_max']=max(checks['affine_saved_max'],float(max(abs(a['x']+a['delta']-v['linear']['estimate']))))
   if len(rows)%300==0:print('readback',len(rows),flush=True)
 finally:vectors.close();mats.close()
 assert collections.Counter(r['batch'] for r in rows)=={'PR119':1200,'PR121':600};assert len(regions)==115200
 table(out/'DECOMPOSITION.csv.gz',rows);table(out/'REGIONS.csv.gz',regions)
 checks.update(endpoints=len(rows),region_points=len(regions),categories=dict(cat),reconstruction_max=max(r['reconstruction_max'] for r in rows),backward_error_max=max(r['backward_error'] for r in rows),condition_j_max=max(r['condition_j'] for r in rows),rank_counts=dict(collections.Counter(str(r['rank']) for r in regions)),unavailable_region_rows=sum(r['reason']!='AVAILABLE' for r in regions),source_files_after=source_check(),**CALLS)
 save(out/'CHECKS.json',checks);print(checks)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();protect();main(args.out)
