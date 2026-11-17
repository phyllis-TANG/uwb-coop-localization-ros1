"""Frozen offline region evaluation. Reads saved states; never imports or calls a solver."""
import argparse,collections,csv,platform,subprocess
import scipy
from regions import *
def writer(path,fields):
 f=gzip.open(path,'wt',newline='') if path.suffix=='.gz' else path.open('x',newline='');w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();return f,w
def ci(values,c,key):
 x=np.asarray(values,float)
 if len(x)<c['bootstrap']['minimum_valid_seeds']:return None,None
 seed=int(hashlib.sha256(canonical([c['bootstrap']['seed'],key])).hexdigest()[:16],16);rng=np.random.default_rng(seed);b=x[rng.integers(0,len(x),(c['bootstrap']['repetitions'],len(x)))].mean(axis=1);return np.quantile(b,[.025,.975]).tolist()
def summarize(rows,c,out):
 keys=['condition','geometry','sigma','mechanism','method','car','view','kind','rho'];groups=collections.defaultdict(list)
 for r in rows:groups[tuple(r[k] for k in keys)].append(r)
 result=[];paired=[]
 for key,rs in sorted(groups.items(),key=lambda x:str(x[0])):
  for subset in ['all','accepted','inside','outside']:
   sel=[r for r in rs if subset=='all' or subset=='accepted' and r['accepted'] or subset=='inside' and r['in_set'] is True or subset=='outside' and r['in_set'] is False]
   s=dict(zip(keys,key));s.update(subset=subset,planned_seeds=len(rs),subset_seeds=len(sel),accepted_seeds=sum(r['accepted'] for r in sel),available_points=sum(r['available_points'] for r in sel),planned_points=6*len(sel),covered_points=sum(r['covered_points'] for r in sel),fully_available_seeds=sum(r['available_points']==6 for r in sel),all_six_covered=sum(r['all_covered'] is True for r in sel))
   s['coverage_available']=s['covered_points']/s['available_points'] if s['available_points'] else None;s['coverage_full_denominator_lower']=s['covered_points']/s['planned_points'] if s['planned_points'] else None
   s['all_six_available_rate']=s['all_six_covered']/s['fully_available_seeds'] if s['fully_available_seeds'] else None
   for field in ['radius_mean','area_mean','position_mse','center_error_norm']:
    a=[r[field] for r in sel if r[field] is not None];s[field]=float(np.mean(a)) if a else None
   vals=[r['coverage_point'] for r in sel if r['coverage_point'] is not None]
   s['coverage_ci_low'],s['coverage_ci_high']=ci(vals,c,list(key)+[subset]) if len(vals)>=c['bootstrap']['minimum_valid_fraction']*len(sel) else (None,None)
   result.append(s)
 # Rho differences are paired against the same noise-circle baseline, not the ellipse.
 index={(r['id'],r['car'],r['view'],r['kind'],r['rho']):r for r in rows}
 diffs=collections.defaultdict(list)
 for r in rows:
  if r['kind']!='combined_circle':continue
  b=index[(r['id'],r['car'],r['view'],'noise_circle',0.)]
  k=tuple(r[x] for x in keys)
  diffs[k].append((r,b))
 for key,pairs in sorted(diffs.items(),key=lambda x:str(x[0])):
  s=dict(zip(keys,key));valid=[(r,b) for r,b in pairs if r['coverage_point'] is not None and b['coverage_point'] is not None];s.update(planned_pairs=len(pairs),valid_pairs=len(valid))
  for field in ['coverage_point','radius_mean']:
   d=[r[field]-b[field] for r,b in valid];s[field+'_difference']=float(np.mean(d)) if d else None
   lo,hi=ci(d,c,list(key)+[field]) if len(d)>=c['bootstrap']['minimum_valid_fraction']*len(pairs) else (None,None);s[field+'_ci_low']=lo;s[field+'_ci_high']=hi
  paired.append(s)
 for name,data in [('SUMMARY.csv',result),('PAIRED_DIFFERENCES.csv',paired)]:
  f,w=writer(out/name,list(data[0]));w.writerows(OLD.clean(data));f.close()
 return result

def analyze(out):
 c=config();out.mkdir(parents=True,exist_ok=False)
 for p,h in json.loads((DOC/'FREEZE_MANIFEST.json').read_text())['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
 vers=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__);assert vers==c['versions']
 records=source();seed_rows=[];fail=[];matrices=[];transfers=[];curvatures=[];reasons=[];endpoints=[];states=[]
 point_fields=['id','condition','seed','method','car','epoch','view','kind','rho','accepted','in_set','center_error_norm','error_x','error_y','error_norm','reason','covered','radius','area','noise_radius','bias_radius']
 pf,pw=writer(out/'POINTS.csv.gz',point_fields)
 counts=collections.Counter();counts['unique_method_endpoints']=len(records);counts['pair_records']=c['expected']['pair_records'];counts['real_optimizer_calls']=0;counts['formal_runs']=0
 try:
  for i,v in enumerate(records):
   u=v['input'];r=v['result'];m=v['method'];x=np.array(r['estimate']) if r.get('estimate') is not None else None;usable=bool(r.get('usable_estimate') and x is not None and np.isfinite(x).all());counts['usable_endpoints']+=usable;counts['accepted_endpoints']+=bool(r['accepted'])
   if not r['accepted']:fail.append(dict(id=v['id'],category=r['category'],usable=usable,gradient=r['gradient_inf']))
   center=float(np.linalg.norm(np.array(u['obs']['prior_center'])-np.array(u['truth'])[0].ravel()));err=x[:24].reshape(6,2,2)-u['truth'] if usable else None
   if usable:
    rr,j=OLD.M.objective(u,m,x);assert np.isclose(rr@rr/2,r['cost'],atol=2e-9,rtol=1e-10);assert np.isclose(max(abs(j.T@rr)),r['gradient_inf'],atol=2e-8,rtol=1e-7)
   endpoints.append(dict(id=v['id'],input_sha256=v['input_sha256'],condition=v['condition'],seed=v['seed'],method=m,category=r['category'],accepted=r['accepted'],center_error_norm=center));states.append(np.pad(x,(0,25-len(x)),constant_values=np.nan) if usable else np.full(25,np.nan))
   pcs=[];pts=[];pcur=[];prs=[]
   for view in c['views']:
    a=local(u,m,x if usable else None,view,c);pcs.append(np.full((6,2,2,2),np.nan));pts.append(np.full((6,2,2,4),np.nan));pcur.append(np.full((6,2,2,2),np.nan));prs.append(a['status']);counts['local_'+a['status']]+=1
    for car in range(2):
     kinds=[('noise_ellipse',0.),('noise_circle',0.)]+[('combined_circle',rho) for rho in c['rho_m'] if rho>0]
     if view!='endpoint_exact':kinds=[('curvature_ellipse',0.)]+kinds
     for kind,rho in kinds:
      in_set=None if kind=='curvature_ellipse' else center<=rho+1e-12;points=[]
      for t in range(6):
       sl=slice(4*t+2*car,4*t+2*car+2);P=None if a['C'] is None else a['C'][sl,sl];B=None if a['T'] is None else a['T'][sl];PC=None if a['curvature'] is None else a['curvature'][sl,sl]
       if P is not None:pcs[-1][t,car]=P;pts[-1][t,car]=B
       if PC is not None:pcur[-1][t,car]=PC
       z=region(PC if kind=='curvature_ellipse' else P,B,rho,err[t,car] if usable else np.zeros(2),c,ellipse=kind.endswith('ellipse'))
       if a['status']!='AVAILABLE':z['reason']=a['status']
       if z['reason']!='AVAILABLE':counts['point_unavailable_'+z['reason']]+=1
       q=dict(id=v['id'],condition=v['condition'],seed=v['seed'],method=m,car=car+1,epoch=t,view=view,kind=kind,rho=rho,accepted=r['accepted'],in_set=in_set,center_error_norm=center,error_x=float(err[t,car,0]) if usable else None,error_y=float(err[t,car,1]) if usable else None,error_norm=float(np.linalg.norm(err[t,car])) if usable else None,**z);pw.writerow(OLD.clean(q));points.append(q);counts['point_rows']+=1
      avail=[z for z in points if z['reason']=='AVAILABLE'];sr={k:v[k] for k in ['id','condition','geometry','sigma','mechanism','method','seed']};sr.update(car=car+1,view=view,kind=kind,rho=rho,accepted=r['accepted'],in_set=in_set,center_error_norm=center,position_mse=float(np.mean(np.sum(err[:,car]**2,axis=1))) if usable else None,available_points=len(avail),covered_points=sum(z['covered'] for z in avail),coverage_point=sum(z['covered'] for z in avail)/6 if len(avail)==6 else None,all_covered=all(z['covered'] for z in avail) if len(avail)==6 else None,radius_mean=float(np.mean([z['radius'] for z in avail])) if avail else None,area_mean=float(np.mean([z['area'] for z in avail])) if avail else None,unavailable_reason=';'.join(sorted(set(z['reason'] for z in points if z['reason']!='AVAILABLE'))));seed_rows.append(sr)
   matrices.append(pcs);transfers.append(pts);curvatures.append(pcur);reasons.append(prs)
   if (i+1)%400==0:print('read-only endpoints',i+1,flush=True)
 finally:pf.close()
 f,w=writer(out/'PER_SEED.csv.gz',list(seed_rows[0]));w.writerows(OLD.clean(seed_rows));f.close()
 f,w=writer(out/'ENDPOINT_FAILURES.csv',['id','category','usable','gradient']);w.writerows(fail);f.close()
 np.savez_compressed(out/'LOCAL_MATRICES.npz',P=np.array(matrices),B=np.array(transfers),curvature=np.array(curvatures),status=np.array(reasons),state=np.array(states),id=np.array([v['id'] for v in records]))
 save(out/'ENDPOINTS.json.gz',endpoints);summarize(seed_rows,c,out);save(out/'COUNTS.json',dict(counts));save(out/'RUN.json',dict(config=c,config_sha256=digest(c),analysis_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),versions=vers,formal_runs=0,real_optimizer_calls=0));print(dict(counts));return counts
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();analyze(a.out)
