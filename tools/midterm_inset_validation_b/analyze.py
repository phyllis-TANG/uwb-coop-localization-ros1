"""Optimizer-free ledger readback, affine probability references, full-denominator statistics."""
import argparse,collections,csv
from common import *

def csvfile(path,fields):
 f=gzip.open(path,'wt',newline='') if path.suffix=='.gz' else path.open('x',newline='');w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();return f,w
def writecsv(p,rows):
 f,w=csvfile(p,list(dict.fromkeys(k for r in rows for k in r)));w.writerows(clean(rows));f.close()
def records_from_run(out):
 meta=read(out/'RUN.json');yield dict(type='META',value=meta)
 for item in meta['plan']:
  u=read(out/'inputs'/f"{item['id']}.json.gz");lin=read(out/'linear'/f"{item['id']}.json.gz");assert lin['input_sha256']==digest(u);stages={};previous=None
  for stage in ['P0','P1']:
   i=stage_identity(meta['config'],item,u,stage,previous);p=REC.stage_path(out/'ledger',i);a=REC.read(p/'ATTEMPT.json');r=REC.read(p/'RESULT.json');d=REC.read(p/'DONE.json')
   assert a['identity']==i and r['identity']==i and r['attempt_id']==a['attempt_id'] and r['payload_sha256']==digest(r['payload'])
   assert d==dict(identity=i,attempt_id=a['attempt_id'],result_sha256=digest(r))
   assert r['payload']['execution']=='RETURNED';previous=r['payload']['value'];stages[stage]=dict(attempt=a,result=r,done=d)
  yield dict(type='UNIT',value=dict(item=item,input=u,linear=lin['result'],stages=stages))
def from_archive(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def interval(x,c,key):
 x=np.asarray(x,float)
 if len(x)<c['statistics']['minimum_valid_seeds']:return [None,None]
 seed=int(hashlib.sha256(canonical([c['statistics']['bootstrap_seed'],key])).hexdigest()[:16],16);rng=np.random.default_rng(seed);z=x[rng.integers(0,len(x),(c['statistics']['repetitions'],len(x)))].mean(axis=1);return np.quantile(z,[.025,.975]).tolist()

def summarize(rows,c,out):
 keys=['condition','geometry','sigma','delta','model','view','kind','rho','car'];groups=collections.defaultdict(list)
 for r in rows:groups[tuple(r[k] for k in keys)].append(r)
 summaries=[]
 for key,rs in sorted(groups.items(),key=lambda x:str(x[0])):
  for subset in ['all','accepted']:
   selected=[r for r in rs if subset=='all' or r['accepted']];valid=[r for r in selected if r['available_points']==6];av=sum(r['available_points'] for r in selected);hit=sum(r['covered_points'] for r in selected)
   z=dict(zip(keys,key));z.update(subset=subset,planned_seeds=len(rs),subset_seeds=len(selected),accepted_seeds=sum(r['accepted'] for r in selected),in_set_seeds=sum(r['in_set'] is True for r in selected),planned_points=6*len(selected),available_points=av,covered_points=hit,fully_available_seeds=len(valid),all_covered_seeds=sum(r['all_covered'] is True for r in selected),coverage_available=hit/av if av else None,coverage_full_denominator_lower=hit/(6*len(selected)) if selected else None,all_six_available_rate=sum(r['all_covered'] for r in valid)/len(valid) if valid else None)
   for field in ['radius_mean','area_mean','mse','mean_error_x','mean_error_y','linear_expected_coverage']:
    vals=[r[field] for r in selected if r.get(field) is not None];z[field]=float(np.mean(vals)) if vals else None
   z['rmse_from_mean_mse']=np.sqrt(z['mse']) if z['mse'] is not None else None
   vals=[r['point_coverage'] for r in valid];z['coverage_ci_low'],z['coverage_ci_high']=interval(vals,c,list(key)+[subset]) if len(valid)>=c['statistics']['minimum_valid_fraction']*len(selected) else [None,None]
   summaries.append(z)
 writecsv(out/'SUMMARY.csv',summaries)
 # Matched linear/nonlinear comparisons; both estimated from the exact same input.
 idx={(r['id'],r['model'],r['view'],r['kind'],r['rho'],r['car']):r for r in rows};pairs=collections.defaultdict(list)
 for r in rows:
  if r['model']!='NL':continue
  b=idx[(r['id'],'LINEAR',r['view'],r['kind'],r['rho'],r['car'])];pairs[tuple(r[k] for k in keys if k!='model')].append((r,b))
 ps=[]
 for key,rs in sorted(pairs.items(),key=lambda x:str(x[0])):
  for subset in ['all','both_accepted']:
   sel=[(r,b) for r,b in rs if subset=='all' or r['accepted'] and b['accepted']];z=dict(zip([k for k in keys if k!='model'],key));z.update(subset=subset,planned_pairs=len(rs),selected_pairs=len(sel))
   for field in ['point_coverage','radius_mean','mse']:
    ds=[r[field]-b[field] for r,b in sel if r.get(field) is not None and b.get(field) is not None];z[field+'_pairs']=len(ds);z[field+'_NL_minus_LINEAR']=float(np.mean(ds)) if ds else None;z[field+'_ci_low'],z[field+'_ci_high']=interval(ds,c,list(key)+[field,subset]) if len(ds)>=c['statistics']['minimum_valid_fraction']*len(sel) else [None,None]
   ps.append(z)
 writecsv(out/'PAIRED_NL_LINEAR.csv',ps)

def analyze(iterator,out,archive=False):
 out.mkdir(parents=True,exist_ok=False);c=config();count=collections.Counter();perseed=[];failures=[];endpoints=[];matrixP=[];matrixB=[];matrixCurve=[];matrixStatus=[];mom=collections.defaultdict(list);theory_cache={};pairing={};meta=None
 fields=['id','condition','seed','geometry','sigma','delta','model','view','kind','rho','car','epoch','accepted','in_set','reason','error_x','error_y','covered','radius','area','linear_expected_coverage']
 pf,pw=csvfile(out/'POINTS.csv.gz',fields);pack=gzip.open(out/'EVIDENCE.jsonl.gz','wt') if archive else None
 try:
  for entry in iterator:
   if pack:pack.write(canonical(entry).decode()+'\n')
   if entry['type']=='META':meta=entry['value'];assert meta['config']==c;continue
   v=entry['value'];item=v['item'];u=v['input'];q=item['condition'];uid=item['id'];lin=v['linear'];p0=v['stages']['P0']['result']['payload']['value'];nl=v['stages']['P1']['result']['payload']['value'];count['units']+=1
   # All sigma/center conditions share observations and survey-integrated start.
   pairkey=(q['geometry'],item['seed']);shared=digest({k:u['obs'][k] for k in ['ranges','movement','start']})
   if pairkey in pairing:assert pairing[pairkey]==shared
   pairing[pairkey]=shared
   checklin=affine(u,c);assert checklin['category']==lin['category'] and checklin['rank']==lin['rank']
   for name in ['estimate','mean','covariance','residual']:assert np.allclose(checklin[name],lin[name],atol=1e-9,rtol=1e-8)
   delta=np.array(u['obs']['prior_center'])-np.array(u['truth'])[0].ravel();assert np.allclose(delta,[0,q['delta_m'],0,0],atol=c['boundary_tolerance_m'],rtol=0)
   for stage,r in [('P0',p0),('P1',nl)]:
    count['optimizer_calls']+=r['optimizer_invocations'] or 0;count['persisted_stages']+=1;count['warnings']+=len(r['warnings']);count['budget_stages']+=int(r['hit_budget'])
    if r['usable_estimate']:
     rr,jj=M.objective(u,'B2',np.array(r['estimate']));assert np.isclose(rr@rr/2,r['cost'],rtol=1e-10,atol=1e-9);assert np.isclose(max(abs(jj.T@rr)),r['gradient_inf'],rtol=1e-7,atol=2e-8)
   localPs=[];localBs=[];localCs=[];localSs=[]
   for model,result in [('NL',nl),('LINEAR',lin)]:
    valid=result['usable_estimate'];count[model+'_usable']+=int(valid);count[model+'_accepted']+=int(result['accepted']);count[model+'_runs']+=1
    if not result['accepted']:failures.append(dict(id=uid,model=model,category=result['category'],usable=valid))
    x=np.array(result['estimate']) if valid else None;e=x[:24].reshape(6,2,2)-u['truth'] if valid else None
    if model=='LINEAR' and valid:mom[q['id']].append(dict(item=item,error=x-np.array(lin['reference']),mean=np.array(lin['mean']),covariance=np.array(lin['covariance'])))
    ps=[];bs=[];cs=[];ss=[]
    for view in ['GN','exact']:
     if model=='NL':a=R.local(u,'B2',x,'endpoint_GN' if view=='GN' else 'endpoint_exact',c['region'])
     else:
      j=np.array(lin['jacobian']);a=R.quantities(j,j.T@j,u['obs']['prior_sigma'],np.r_[np.ones(24),.1],c['region'],exact=view=='exact') if valid else dict(status='NO_FINITE_ESTIMATE',C=None,T=None,curvature=None)
     ps.append(np.full((6,2,2,2),np.nan));bs.append(np.full((6,2,2,4),np.nan));cs.append(np.full((6,2,2,2),np.nan));ss.append(a['status'])
     kinds=([('curvature_ellipse',0.)] if view=='GN' else [])+[('noise_ellipse',0.),('noise_circle',0.)]+[('combined_circle',rho) for rho in c['region']['rho_m'] if rho>0]
     for car in range(2):
      for kind,rho in kinds:
       isin=None if kind=='curvature_ellipse' else np.linalg.norm(delta)<=rho+c['boundary_tolerance_m'];points=[]
       for t in range(6):
        sl=slice(4*t+2*car,4*t+2*car+2);P=None if a['C'] is None else a['C'][sl,sl];B=None if a['T'] is None else a['T'][sl];PC=None if a['curvature'] is None else a['curvature'][sl,sl]
        if P is not None:ps[-1][t,car]=P;bs[-1][t,car]=B
        if PC is not None:cs[-1][t,car]=PC
        region=R.region(PC if kind=='curvature_ellipse' else P,B,rho,e[t,car] if valid else np.zeros(2),c['region'],ellipse=kind.endswith('ellipse'))
        if a['status']!='AVAILABLE':region['reason']=a['status']
        theory=None
        if model=='LINEAR' and region['reason']=='AVAILABLE':
         key=(q['id'],view,kind,rho,car,t)
         if key not in theory_cache:
          cand=PC if kind=='curvature_ellipse' else P if kind=='noise_ellipse' else np.eye(2)*region['radius']**2/R.quantile(.95)
          theory_cache[key]=M.gaussian_ellipse_probability(np.array(lin['mean'])[sl],np.array(lin['covariance'])[sl,sl],cand,.95)
         theory=theory_cache[key]
         if isin and kind in ['noise_circle','combined_circle']:assert theory>=.95-1e-7,'Linear set guarantee violated analytically'
        point=dict(id=uid,condition=q['id'],seed=item['seed'],geometry=q['geometry'],sigma=q['prior_sigma'],delta=q['delta_m'],model=model,view=view,kind=kind,rho=rho,car=car+1,epoch=t,accepted=result['accepted'],in_set=isin,reason=region['reason'],error_x=float(e[t,car,0]) if valid else None,error_y=float(e[t,car,1]) if valid else None,covered=region['covered'],radius=region['radius'],area=region['area'],linear_expected_coverage=theory);pw.writerow(clean(point));points.append(point);count['point_rows']+=1
        if region['reason']!='AVAILABLE':count[model+'_unavailable_'+region['reason']]+=1
       available=[p for p in points if p['reason']=='AVAILABLE'];expected=[p['linear_expected_coverage'] for p in available if p['linear_expected_coverage'] is not None];mse=float(np.mean(np.sum(e[:,car]**2,axis=1))) if valid else None
       row={k:point[k] for k in ['id','condition','seed','geometry','sigma','delta','model','view','kind','rho','car','accepted','in_set']};row.update(available_points=len(available),covered_points=sum(p['covered'] for p in available),point_coverage=sum(p['covered'] for p in available)/6 if len(available)==6 else None,all_covered=all(p['covered'] for p in available) if len(available)==6 else None,radius_mean=float(np.mean([p['radius'] for p in available])) if available else None,area_mean=float(np.mean([p['area'] for p in available])) if available else None,mse=mse,rmse=np.sqrt(mse) if mse is not None else None,mean_error_x=float(e[:,car,0].mean()) if valid else None,mean_error_y=float(e[:,car,1].mean()) if valid else None,linear_expected_coverage=float(np.mean(expected)) if expected else None,unavailable_reason=';'.join(sorted(set(p['reason'] for p in points if p['reason']!='AVAILABLE'))));perseed.append(row)
    localPs.append(ps);localBs.append(bs);localCs.append(cs);localSs.append(ss)
   endpoints.append(uid);matrixP.append(localPs);matrixB.append(localBs);matrixCurve.append(localCs);matrixStatus.append(localSs)
   if count['units']%100==0:print('analyzed units',count['units'],flush=True)
 finally:
  pf.close()
  if pack:pack.close()
 expected=c['expected']['formal_methods'] if meta['mode']=='formal' else c['expected']['development_methods'];assert count['units']==expected
 writecsv(out/'PER_SEED.csv.gz',perseed);writecsv(out/'FAILURES.csv',failures or [dict(id='',model='',category='NONE',usable='')]);summarize(perseed,c,out)
 moments=[]
 for condition,rs in mom.items():
  errors=np.array([v['error'] for v in rs]);mu=rs[0]['mean'];C=rs[0]['covariance'];emp=errors.mean(axis=0);var=np.var(errors,axis=0,ddof=1) if len(rs)>1 else np.full(25,np.nan)
  for k in range(25):
   cv=C[k,k];det=cv<1e-18;z=(emp[k]-mu[k])/np.sqrt(cv/len(rs)) if not det else None;ratio=var[k]/cv if not det and len(rs)>1 else None;flag=abs(emp[k]-mu[k])>c['linear_sanity']['singular_mean_absolute_tolerance'] if det else abs(z)>c['linear_sanity']['mean_z_flag'] or (ratio is not None and not c['linear_sanity']['variance_ratio_bounds'][0]<=ratio<=c['linear_sanity']['variance_ratio_bounds'][1])
   moments.append(dict(condition=condition,coordinate=k,seeds=len(rs),analytic_mean=mu[k],empirical_mean=emp[k],analytic_variance=cv,empirical_center_variance=var[k] if len(rs)>1 else None,mean_z=z,variance_ratio=ratio,deterministic_coordinate=det,diagnostic_flag=bool(flag)))
 writecsv(out/'LINEAR_MOMENTS.csv',moments);np.savez_compressed(out/'LOCAL_MATRICES.npz',id=np.array(endpoints),P=np.array(matrixP),B=np.array(matrixB),curvature=np.array(matrixCurve),status=np.array(matrixStatus))
 save(out/'COUNTS.json',dict(count));save(out/'RUN.json',meta);return dict(count)
if __name__=='__main__':
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--run',type=Path);g.add_argument('--archive',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(analyze(records_from_run(a.run) if a.run else from_archive(a.archive),a.out,archive=bool(a.run)))
