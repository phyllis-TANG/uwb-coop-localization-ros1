"""Separate-batch seed-cluster statistics. No pooling conditions as independent n."""
import argparse,collections
from functools import lru_cache
from scipy.stats import spearmanr
from common import *
REASONS={0:'AVAILABLE',1:'RANK_DEFICIENT',2:'NONFINITE_MARGINAL',3:'NONPOSITIVE_MARGINAL',4:'NO_FINITE_ESTIMATE'}

def load(directory):
 rows=[];arrays=collections.defaultdict(list);infos=[];checks=[]
 for p in sorted(directory.glob('shard-[0-9][0-9][0-9]')):
  done=json.loads((p/'DONE.json').read_text())
  for name,h in done['outputs'].items():assert sha(p/name)==h
  rr=csvread(p/'RUNS.csv.gz');rows.extend(rr);infos.extend(csvread(p/'INFORMATION.csv.gz'));checks.append(json.loads((p/'CHECKS.json').read_text()))
  with np.load(p/'POINTS.npz') as z:
   for key in z.files:arrays[key].append(z[key])
 return rows,{key:np.concatenate(v) for key,v in arrays.items()},infos,checks

class Cluster:
 def __init__(self,n):
  self.n=n;rng=np.random.default_rng(CFG['bootstrap_seed']);self.counts=np.array([np.bincount(v,minlength=n) for v in rng.integers(0,n,(CFG['bootstrap_repetitions'],n))],float)
 @lru_cache(15000)
 def ratio(self,ct,vt,maximum):
  c=np.array(ct,float);v=np.array(vt,float);valid=v>0
  if valid.sum()<CFG['minimum_valid_seeds']:return None,None,'INSUFFICIENT_EFFECTIVE_SEEDS'
  if v.sum()<(1-CFG['maximum_missing_fraction'])*self.n*maximum:return None,None,'EXCESS_UNAVAILABLE_OR_UNSELECTED'
  if np.ptp(c[valid]/v[valid])<1e-14:return None,None,'CONSTANT_EMPIRICAL_CLUSTERS'
  den=self.counts@v;z=(self.counts@c)[den>0]/den[den>0];lo,hi=np.quantile(z,[.025,.975]);return float(lo),float(hi),'SEED_CLUSTER_PERCENTILE'
 def counts_summary(self,q,selected,threshold,trajectory=False):
  ok=np.isfinite(q);co=ok&(q<=threshold)
  if trajectory:ok=ok.all(axis=1)[:,None];co=co.all(axis=1)[:,None]
  ntime=ok.shape[1];v=(ok*selected[:,None]).sum(axis=1);c=(co*selected[:,None]).sum(axis=1)
  lo,hi,status=self.ratio(tuple(c),tuple(v),ntime);jl,jh,jst=self.ratio(tuple(c),tuple(np.full(self.n,ntime)),ntime)
  return dict(planned=self.n*ntime,selected_planned=int(selected.sum()*ntime),selected_seeds=int(selected.sum()),not_selected=int((~selected).sum()*ntime),available=int(v.sum()),unavailable=int(selected.sum()*ntime-v.sum()),covered=int(c.sum()),coverage_available=float(c.sum()/v.sum()) if v.sum() else None,covered_over_full_plan=float(c.sum()/(self.n*ntime)),ci_low=lo,ci_high=hi,ci_status=status,joint_ci_low=jl,joint_ci_high=jh,joint_ci_status=jst)
 def difference(self,d):
  valid=np.isfinite(d);mean=float(np.mean(d[valid])) if valid.any() else None;lo=hi=None
  if valid.sum()<CFG['minimum_valid_seeds']:status='INSUFFICIENT_EFFECTIVE_SEEDS'
  elif valid.mean()<1-CFG['maximum_missing_fraction']:status='EXCESS_UNAVAILABLE_OR_UNSELECTED'
  elif np.ptp(d[valid])<1e-14:status='CONSTANT_EMPIRICAL_CLUSTERS'
  else:
   den=self.counts@valid;z=(self.counts@np.where(valid,d,0))[den>0]/den[den>0];lo,hi=map(float,np.quantile(z,[.025,.975]));status='PAIRED_SEED_PERCENTILE'
  return dict(planned=self.n,paired_available=int(valid.sum()),unavailable=self.n-int(valid.sum()),mean_difference=mean,ci_low=lo,ci_high=hi,ci_status=status)

def rho(a,b):
 v=np.isfinite(a)&np.isfinite(b)
 return float(spearmanr(a[v],b[v]).statistic) if v.sum()>2 and np.ptp(a[v])>0 and np.ptp(b[v])>0 else None

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',choices=list(CFG['batches']),required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 rows,z,info,checks=load(a.input);spec=CFG['batches'][a.batch];n=spec['seeds'];assert len(rows)==spec['methods'];cluster=Cluster(n)
 q=z['q'];cov=z['covariance'];err=z['error'];reason=z['reason'];tr=cov[...,0]+cov[...,2];err2=np.sum(err**2,axis=-1);bq=z['bias_q'];bv=z['bias_variance'];be=z['bias_error'];groups={};bases={}
 for i,r in enumerate(rows):groups.setdefault((r['id'],r['method']),[]).append(i)
 groups={k:np.array(sorted(v,key=lambda i:int(rows[i]['seed']))) for k,v in groups.items()};assert len(groups)==288 and all(len(ids)==n for ids in groups.values())
 cover=[];bias=[];mom=[];assoc=[];fail=[]
 for (cid,m),ids in sorted(groups.items()):
  r=rows[ids[0]];base={k:r[k] for k in ['batch','id','geometry','motion','candidate','injection','noise_model','method']};bases[cid,m]=base
  cats=np.array([rows[i]['category'] for i in ids]);subsets={'all':np.ones(n,bool),'accepted':cats=='ACCEPTED','not_stationary':cats=='NOT_STATIONARY','budget_exhausted':cats=='BUDGET_EXHAUSTED'}
  for v,view in enumerate(VIEWS):
   for car in [1,2]:
    blocks=np.arange(car-1,12,2);qq=q[ids,v][:,blocks]
    for level in CFG['levels']:
     for sub,sel in subsets.items():
      for agg in ['point_average','all_times']+[f't{t}' for t in range(6)]:
       aq=qq if agg in ['point_average','all_times'] else qq[:,[int(agg[1:])]];rr=reason[ids,v][:,blocks];rr=rr if agg in ['point_average','all_times'] else rr[:,[int(agg[1:])]]
       counts={REASONS[int(k)]:int(val) for k,val in collections.Counter(rr[sel].ravel()).items() if k!=0}
       cover.append(dict(base,view=view,car=car,level=level,subset=sub,aggregation=agg,**cluster.counts_summary(aq,sel,quantile(level,2),agg=='all_times'),unavailable_point_reasons=json.dumps(counts,sort_keys=True)))
    for t,k in enumerate(blocks):
     ee=err[ids,k];valid=np.isfinite(ee).all(axis=1);vv=np.isfinite(q[ids,v,k]);evalid=ee[valid];mu=evalid.mean(axis=0) if valid.any() else np.full(2,np.nan);emp=np.cov(evalid.T,ddof=1) if valid.sum()>1 else np.full((2,2),np.nan)
     cc=cov[ids,v,k][vv];ev=np.linalg.eigvalsh(np.stack([np.stack([cc[:,0],cc[:,1]],axis=-1),np.stack([cc[:,1],cc[:,2]],axis=-1)],axis=1)) if len(cc) else np.empty((0,2))
     row=dict(base,view=view,car=car,time=t,planned=n,error_available=int(valid.sum()),available=int(vv.sum()),unavailable=n-int(vv.sum()),mean_ex=float(mu[0]),mean_ey=float(mu[1]),mean_error_squared=float(mu@mu),empirical_xx=float(emp[0,0]),empirical_xy=float(emp[0,1]),empirical_yy=float(emp[1,1]),empirical_trace=float(np.trace(emp)),mse=float(np.mean(np.sum(evalid**2,axis=1))) if len(evalid) else None,predicted_trace=float(np.mean(tr[ids,v,k][vv])) if vv.any() else None,mean_q=float(np.mean(q[ids,v,k][vv])) if vv.any() else None)
     for level in CFG['levels']:
      threshold=quantile(level,2);suffix=str(int(level*100));row['area'+suffix]=float(np.mean(np.pi*threshold*np.sqrt(ev.prod(axis=1)))) if len(ev) else None;row['minor'+suffix]=float(np.mean(np.sqrt(threshold*ev[:,0]))) if len(ev) else None;row['major'+suffix]=float(np.mean(np.sqrt(threshold*ev[:,1]))) if len(ev) else None
     if len(evalid)>1:assert abs(row['mse']-((len(evalid)-1)/len(evalid)*row['empirical_trace']+row['mean_error_squared']))<1e-12
     mom.append(row)
    actual=np.sqrt(np.mean(err2[ids][:,blocks],axis=1));unc=np.sqrt(np.mean(tr[ids,v][:,blocks],axis=1));res=np.array([float(rows[i]['data_residual_rms']) for i in ids]);failure=np.where(np.isfinite(qq).all(axis=1),np.mean(qq>quantile(.95,2),axis=1),np.nan)
    assoc.append(dict(base,view=view,car=car,planned=n,available=int(np.isfinite(failure).sum()),residual_error_spearman=rho(res,actual),residual_noncoverage_spearman=rho(res,failure),error_uncertainty_spearman=rho(actual,unc),mean_residual=float(res.mean()),mean_rmse=float(actual.mean()),mean_uncertainty_scale=float(unc.mean())))
   if m=='B2':
    eligible=bool(np.all(z['bias_eligible'][ids]));assert eligible or not z['bias_eligible'][ids].any()
    for level in CFG['levels']:
     for sub,sel in subsets.items():
      item=dict(base,view=view,level=level,subset=sub,bias_truth_defined=eligible,**cluster.counts_summary(bq[ids,v,None],sel,quantile(level,1)))
      item['eligible_planned']=item['selected_planned'] if eligible else 0;item['not_applicable']=0 if eligible else item['selected_planned']
      item['bias_policy']='MATCHED_CONSTANT' if eligible else 'NO_UNIQUE_TRUE_CONSTANT';item['unavailable_reasons']='{}' if eligible and item['unavailable']==0 else json.dumps({'INTERVAL_UNAVAILABLE' if eligible else 'NOT_APPLICABLE_MODEL':item['unavailable']})
      if not eligible:item.update(available=0,unavailable=0,covered=None,coverage_available=None,covered_over_full_plan=None,ci_low=None,ci_high=None,ci_status='NOT_APPLICABLE_MODEL',joint_ci_low=None,joint_ci_high=None,joint_ci_status='NOT_APPLICABLE_MODEL')
      eligible_sel=sel&np.isfinite(bq[ids,v]);item['mean_halfwidth']=float(np.mean(np.sqrt(quantile(level,1)*bv[ids,v][eligible_sel]))) if eligible_sel.any() else None
      bias.append(item)
 for i,r in enumerate(rows):
  if r['category']!='ACCEPTED' or (reason[i]!=0).any():fail.append(dict(r,unavailable_blocks=int(np.sum(reason[i]!=0)),A_covered95=int(np.sum(q[i,0]<=quantile(.95,2))),B_covered95=int(np.sum(q[i,1]<=quantile(.95,2))),C_covered95=int(np.sum(q[i,2]<=quantile(.95,2))),planned_points=12))
 csvwrite(a.out/'COVERAGE.csv.gz',cover);csvwrite(a.out/'BIAS_COVERAGE.csv.gz',bias);csvwrite(a.out/'MOMENTS.csv.gz',mom);csvwrite(a.out/'ASSOCIATIONS.csv.gz',assoc);csvwrite(a.out/'FAILURES.csv.gz',fail)
 pairs=[]
 def compare(base,kind,idx1,v1,idx0,v0,car,subset):
  assert [rows[i]['seed'] for i in idx1]==[rows[i]['seed'] for i in idx0]
  blocks=np.arange(car-1,12,2);e1=np.mean(err2[idx1][:,blocks],axis=1);e0=np.mean(err2[idx0][:,blocks],axis=1);sel=np.ones(n,bool) if subset=='all' else np.array([rows[i]['accepted']=='True' and rows[j]['accepted']=='True' for i,j in zip(idx1,idx0)])
  t1=np.mean(tr[idx1,v1][:,blocks],axis=1);t0=np.mean(tr[idx0,v0][:,blocks],axis=1)
  for metric,diff in [('mse',e1-e0),('trace',t1-t0)]:pairs.append(dict(base,comparison=kind,car=car,subset=subset,metric=metric,level=None,**cluster.difference(np.where(sel,diff,np.nan)),error_and_coverage_improved=None))
  for level in CFG['levels']:
   a1=q[idx1,v1][:,blocks];a0=q[idx0,v0][:,blocks];valid=sel&np.isfinite(a1).all(axis=1)&np.isfinite(a0).all(axis=1);diff=np.mean(a1<=quantile(level,2),axis=1)-np.mean(a0<=quantile(level,2),axis=1)
   pairs.append(dict(base,comparison=kind,car=car,subset=subset,metric='point_coverage',level=level,**cluster.difference(np.where(valid,diff,np.nan)),error_and_coverage_improved=int(np.sum(valid&(e1<e0)&(diff>0)))))
 for (cid,m),ids in sorted(groups.items()):
  base=dict(bases[cid,m]);
  for car in [1,2]:
   for sub in ['all','both_accepted']:
    for v0 in [0,1]:compare(dict(base,view='C_true_noise'),f'C-{VIEWS[v0]}',ids,2,ids,v0,car,sub)
    if m=='B2':
     for other in ['B1','B0']:
      for v in range(3):compare(dict(base,view=VIEWS[v]),'B2-'+other,ids,v,groups[cid,other],v,car,sub)
    if a.batch=='noise' and base['noise_model']!='iid_004':
     ref=next(k for k,b in bases.items() if b['method']==m and b['noise_model']=='iid_004' and all(b[f]==base[f] for f in ['geometry','motion','candidate','injection']))
     for v in range(3):compare(dict(base,view=VIEWS[v]),base['noise_model']+'-iid_004',ids,v,groups[ref],v,car,sub)
 csvwrite(a.out/'PAIRED.csv.gz',pairs)
 cases=[]
 for factor in sorted({r['injection'] if a.batch=='fault' else r['noise_model'] for r in rows}):
  ids=[i for i,r in enumerate(rows) if r['method']=='B2' and r['injection' if a.batch=='fault' else 'noise_model']==factor];qq=q[ids,2];j,k=np.unravel_index(np.nanargmax(qq),qq.shape);i=ids[j];cases.append(dict(rows[i],view=VIEWS[2],block=int(k),q=float(q[i,2,k]),error=err[i,k].tolist(),covariance=cov[i,2,k].tolist()))
 write_json(a.out/'CASES.json',cases)
 categories=dict(collections.Counter(r['category'] for r in rows));assert categories==spec['categories']
 check=dict(batch=a.batch,methods=len(rows),inputs=len(rows)//4,categories=categories,position_blocks_per_view=len(rows)*12,unavailable_blocks_by_view={view:int(np.sum(reason[:,v]!=0)) for v,view in enumerate(VIEWS)},data_or_total_information_records=len(info),rank_deficient=sum(r['reason']=='RANK_DEFICIENT' for r in info),rank_sensitivity_disagreements={str(t):sum(r['rank_'+str(t)]!=r['rank'] for r in info) for t in CFG['rank_sensitivity']},max_jacobian_condition=max(float(r['condition']) for r in info if r['condition']),source_stage_records=sum(c['stage_records'] for c in checks),max_cost_diff=max(c['max_cost_diff'] for c in checks),max_gradient_diff=max(c['max_gradient_diff'] for c in checks),crosscheck_cases=sum(c['crosscheck_cases'] for c in checks),max_covariance_crosscheck=max(c['max_covariance_crosscheck'] for c in checks),coverage_rows=len(cover),bias_rows=len(bias),bias_eligible_methods=int(z['bias_eligible'].sum()),optimizer_calls=0,passed=True)
 assert all(r['available']+r['unavailable']==r['selected_planned'] and r['covered']<=r['available'] for r in cover)
 write_json(a.out/'CHECKS.json',check);print(json.dumps(check),flush=True)
if __name__=='__main__':main()
