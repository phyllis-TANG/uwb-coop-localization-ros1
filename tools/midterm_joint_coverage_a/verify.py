"""Independent 2x2 algebra/count readback and clustering checks, no refitting."""
import argparse
from common import *
sys.path.insert(0,str(Path(__file__).resolve().parent))
from summarize import load,Cluster

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--batch',choices=list(CFG['batches']),required=True);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--summary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();rows,z,_,_=load(args.input)
 c=z['covariance'];ex=z['error'][:,None,:,0];ey=z['error'][:,None,:,1];det=c[...,0]*c[...,2]-c[...,1]**2
 independent=(c[...,2]*ex*ex-2*c[...,1]*ex*ey+c[...,0]*ey*ey)/det;assert np.allclose(independent,z['q'],equal_nan=True,rtol=1e-10,atol=1e-10)
 btruth=z['bias_eligible'];assert np.isnan(z['bias_q'][~btruth]).all();assert np.allclose(z['bias_error'][btruth,None]**2/z['bias_variance'][btruth],z['bias_q'][btruth],rtol=1e-10,atol=1e-10)
 groups={}
 for i,r in enumerate(rows):groups.setdefault((r['id'],r['method']),[]).append(i)
 q=z['q'];qlevels={str(l):quantile(l,2) for l in CFG['levels']};checked=0
 def selection(ids,sub):return [i for i in ids if sub=='all' or rows[i]['category']=={'accepted':'ACCEPTED','not_stationary':'NOT_STATIONARY','budget_exhausted':'BUDGET_EXHAUSTED'}[sub]]
 for r in csvread(args.summary/'COVERAGE.csv.gz'):
  ids=groups[r['id'],r['method']];sel=selection(ids,r['subset']);blocks=list(range(int(r['car'])-1,12,2));agg=r['aggregation']
  if agg.startswith('t'):blocks=[blocks[int(agg[1:])]]
  vals=q[sel,VIEWS.index(r['view'])][:,blocks];valid=np.isfinite(vals);covered=valid&(vals<=qlevels[r['level']])
  if agg=='all_times':valid=valid.all(axis=1);covered=covered.all(axis=1)
  assert int(r['available'])==valid.sum() and int(r['covered'])==covered.sum() and int(r['selected_planned'])==valid.size and int(r['unavailable'])==valid.size-valid.sum()
  expected_plan=CFG['batches'][args.batch]['seeds']*(1 if agg=='all_times' else len(blocks));assert int(r['planned'])==expected_plan
  assert abs(float(r['covered_over_full_plan'])-covered.sum()/expected_plan)<1e-14
  if valid.sum():assert abs(float(r['coverage_available'])-covered.sum()/valid.sum())<1e-14
  else:assert r['coverage_available']==''
  checked+=1
 bchecked=0
 for r in csvread(args.summary/'BIAS_COVERAGE.csv.gz'):
  ids=selection(groups[r['id'],r['method']],r['subset'])
  if r['bias_truth_defined']=='False':assert r['covered']=='' and r['coverage_available']=='' and r['covered_over_full_plan']=='' and int(r['eligible_planned'])==0
  else:
   v=z['bias_q'][ids,VIEWS.index(r['view'])];assert int(r['available'])==np.isfinite(v).sum() and int(r['covered'])==np.sum(v<=quantile(float(r['level']),1))
  bchecked+=1
 # Correct Ω cannot change the saved errors; iid model must coincide with B exactly to precision.
 iid=np.array([r['noise_model']=='iid_004' for r in rows]);assert np.allclose(c[iid,1],c[iid,2],rtol=1e-12,atol=1e-12)
 # Effective n is seed, not six duplicate time points; unavailable never succeeds.
 cl=Cluster(50);test=np.ones((50,1));test[:10]=10;test[10:12]=np.nan;sel=np.ones(50,bool);one=cl.counts_summary(test,sel,6);six=cl.counts_summary(np.repeat(test,6,axis=1),sel,6)
 assert one['covered']==38 and one['available']==48 and one['unavailable']==2 and one['covered_over_full_plan']==.76
 for k in ['ci_low','ci_high','joint_ci_low','joint_ci_high']:assert abs(one[k]-six[k])<1e-12
 assert cl.counts_summary(np.ones((50,6)),sel,6)['ci_status']=='CONSTANT_EMPIRICAL_CLUSTERS'
 assert cl.counts_summary(test,np.zeros(50,bool),6)['coverage_available'] is None
 result=dict(batch=args.batch,passed=True,methods=len(rows),position_q_max_relative_error=float(np.nanmax(abs(independent-q)/np.maximum(1,abs(q)))),position_coverage_rows_checked=checked,bias_rows_checked=bchecked,invalid_true_bias_not_evaluated=True,B_equals_C_for_iid004=True,unavailable_not_success=True,seed_cluster_duplication_invariance=True,optimizer_calls=0)
 write_json(args.out,result);print(json.dumps(result))
if __name__=='__main__':main()
