"""Seed-cluster summaries; missing estimates never imputed as zero errors."""
from common import *
from model import CFG
import argparse,csv,collections
from scipy.stats import chi2
from functools import lru_cache
THRESHOLDS={x:float(chi2.ppf(x,2)) for x in [.95,.99]}
@lru_cache(None)
def draws(n):return np.random.default_rng(CFG["bootstrap_seed"]).integers(0,n,(CFG["bootstrap_repetitions"],n))

def interval(values,planned):
    x=np.asarray(values,float);x=x[np.isfinite(x)];n=len(x)
    if n<CFG['minimum_valid_seeds']:return None,None,'INSUFFICIENT_SEEDS'
    if (planned-n)/planned>CFG['maximum_missing_fraction']:return None,None,'EXCESS_MISSING'
    if np.ptp(x)==0:return None,None,'CONSTANT_CLUSTER'
    means=x[draws(n)].mean(1);lo,hi=np.quantile(means,[.025,.975]);return float(lo),float(hi),'POINTWISE_SEED_BOOTSTRAP' if n==planned else 'CONDITIONAL_VALID'
def mean(x):
    a=np.asarray(x,float);return float(np.mean(a[np.isfinite(a)])) if np.any(np.isfinite(a)) else None

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);d=cached_npz(args.input/'POINTS.npz');sel=read(args.input/'SELECTION.json');rows=list(csv.DictReader((args.input/'ENDPOINT_METRICS.csv').open()));coverage=[];metrics=[];paired=[];branch=[];within=[];failure=[]
    for cid in sorted({r['condition'] for r in rows}):
      for m in CFG['methods']:
        ss=[s for s in sel if s['condition']==cid and s['method']==m];assert len(ss)==40;first=rows[ss[0]['original_index']];base=dict(condition=cid,geometry=first['geometry'],mechanism=first['mechanism'],sigma=float(first['sigma']),noise_scale=float(first['noise_scale']),method=m)
        branch.append(dict(**base,planned_seeds=40,original_accepted=sum(rows[s['original_index']]['accepted']=='True' for s in ss),selected_available=sum(s['selected_index'] is not None for s in ss),at_least_two_accepted_candidates=sum(s['accepted_candidates']>=2 for s in ss),multiple_accepted_groups=sum(s['accepted_groups']>1 for s in ss),near_cost_distinct_position_seeds=sum(s['near_cost_distinct_pairs']>0 for s in ss),stable_all_five_seeds=sum(s['stable_all_five'] for s in ss),changed_initialization=sum(s['selected_init'] not in [None,'I0'] for s in ss),planned_configurations=200,additional_initialization_nfev=sum(int(rows[s['original_index']+i]['nfev']) for s in ss for i in range(1,5))))
        cats=collections.Counter(rows[s['original_index']+i]['category'] for s in ss for i in range(5))
        for cat,n in cats.items():failure.append(dict(**base,category=cat,count=n,planned_candidates=200))
        for mode in ['original','selected','original_accepted','stable_selected']:
          ids=[s['original_index'] if mode=='original' or (mode=='original_accepted' and rows[s['original_index']]['accepted']=='True') else s['selected_index'] if mode=='selected' or (mode=='stable_selected' and s['stable_all_five']) else None for s in ss]
          for car in range(2):
            keys=np.arange(car,12,2);q=np.full((40,2,6),np.nan);tr=q.copy();area=q.copy();err=np.full((40,6,2),np.nan);why=np.full((40,2,6),'NO_SELECTED_OR_SUBSET',dtype='<U32')
            for n,i in enumerate(ids):
                if i is not None:q[n]=d['q'][i][:,keys];tr[n]=d['trace'][i][:,keys];area[n]=d['area95'][i][:,keys];err[n]=d['error'][i][keys];why[n]=d['reason'][i][:,keys]
            rmse=np.sqrt(np.mean(np.sum(err**2,axis=2),axis=1));lo,hi,status=interval(rmse,40)
            metrics.append(dict(**base,mode=mode,car=car+1,planned=40,finite_error_seeds=int(np.isfinite(rmse).sum()),mean_rmse_m=mean(rmse),rmse_ci_low=lo,rmse_ci_high=hi,ci_status=status,mean_curvature_sqrt_trace_m=mean(np.sqrt(tr[:,0])),mean_noise_sqrt_trace_m=mean(np.sqrt(tr[:,1])),mean_curvature_area95_m2=mean(area[:,0])))
            for v,view in enumerate(['curvature','fixed_prior_noise']):
              for level in [.95,.99]:
                available=np.isfinite(q[:,v]);hit=available & (q[:,v]<=THRESHOLDS[level])
                for agg in ['point_mean','trajectory_all']+[f't{t}' for t in range(6)]:
                    if agg=='point_mean':av=available.sum(1);hc=hit.sum(1);plan=240;cluster=hc/6
                    elif agg=='trajectory_all':av=available.all(1).astype(int);hc=(hit.all(1)&available.all(1)).astype(int);plan=40;cluster=hc
                    else:t=int(agg[1:]);av=available[:,t].astype(int);hc=hit[:,t].astype(int);plan=40;cluster=hc
                    lo,hi,cs=interval(cluster,40);avsum=int(sum(av));hsum=int(sum(hc));reasoncounts=collections.Counter(why[:,v].ravel() if agg=='point_mean' else why[:,v,int(agg[1:])] if agg.startswith('t') and agg!='trajectory_all' else ['AVAILABLE' if a else 'INCOMPLETE_TRAJECTORY' for a in av])
                    vlo,vhi,vcs=interval([float(h/a) if a else np.nan for h,a in zip(hc,av)],40)
                    if agg=='point_mean' and any((av>0)&(av<6)):vlo=vhi=None;vcs='PARTIAL_SEED_AVAILABILITY_NO_CI'
                    coverage.append(dict(**base,mode=mode,car=car+1,view=view,level=level,aggregation=agg,planned=plan,available=avsum,unavailable=plan-avsum,covered=hsum,valid_coverage=hsum/avsum if avsum else None,planned_valid_and_covered=hsum/plan,planned_rate_ci_low=lo,planned_rate_ci_high=hi,ci_status=cs,valid_rate_ci_low=vlo,valid_rate_ci_high=vhi,valid_rate_ci_status=vcs,unavailable_reasons=json.dumps({k:n for k,n in reasoncounts.items() if k!='AVAILABLE'},sort_keys=True)))
        # Within-selected-group gives each seed one vote, regardless of number of members.
        for car in range(2):
          keys=np.arange(car,12,2)
          for v,view in enumerate(['curvature','fixed_prior_noise']):
            values=[];valid=[];counts=[]
            for s in ss:
              ii=s['selected_group_indices'];counts.append(len(ii))
              if not ii:values.append(0.);valid.append(0.);continue
              q=d['q'][ii,v][:,keys];av=np.isfinite(q);values.append(float(np.mean(av & (q<=THRESHOLDS[.95]))));valid.append(float(np.mean(av)))
            lo,hi,cs=interval(values,40);within.append(dict(**base,car=car+1,view=view,planned_seeds=40,group_available_seeds=sum(n>0 for n in counts),members_total=sum(counts),seed_weighted_available_points=6*sum(valid),seed_weighted_covered_points=6*sum(values),seed_weighted_valid_coverage=sum(values)/sum(valid) if sum(valid) else None,planned_valid_and_covered=float(np.mean(values)),ci_low=lo,ci_high=hi,ci_status=cs))
          for metric in ['rmse','coverage95','sqrt_trace']:
            delta=[]
            for s in ss:
              i,j=s['original_index'],s['selected_index']
              if j is None:delta.append(np.nan);continue
              def value(k):
                if metric=='rmse':return np.sqrt(np.mean(np.sum(d['error'][k,keys]**2,axis=1)))
                if metric=='sqrt_trace':return np.mean(np.sqrt(d['trace'][k,0,keys]))
                q=d['q'][k,0,keys];return np.mean(q<=THRESHOLDS[.95]) if np.isfinite(q).all() else np.nan
              delta.append(value(j)-value(i))
            lo,hi,cs=interval(delta,40);paired.append(dict(**base,car=car+1,metric=metric,contrast='selected-minus-original',planned_seeds=40,paired_valid=int(np.isfinite(delta).sum()),mean_difference=mean(delta),ci_low=lo,ci_high=hi,ci_status=cs))
    for name,x in [('COVERAGE',coverage),('METRICS',metrics),('PAIRED',paired),('BRANCH',branch),('WITHIN_GROUP',within),('FAILURES',failure)]:csvsave(out/(name+'.csv'),x)
    # Independent direct scalar-loop recount of key original/selected point-mean cells.
    maxdiff=0;nc=0
    for row in coverage:
      if row['mode'] not in ['original','selected'] or row['aggregation']!='point_mean':continue
      ss=[s for s in sel if s['condition']==row['condition'] and s['method']==row['method']];vv=0 if row['view']=='curvature' else 1;av=hit=0
      for s in ss:
        i=s['original_index'] if row['mode']=='original' else s['selected_index']
        if i is None:continue
        for k in range(row['car']-1,12,2):
          q=float(d['q'][i,vv,k]);av+=int(np.isfinite(q));hit+=int(np.isfinite(q) and q<=THRESHOLDS[row['level']])
      assert row['planned']==240 and row['unavailable']==240-av and 0<=hit<=av<=240
      maxdiff=max(maxdiff,abs(av-row['available']),abs(hit-row['covered']));nc+=1
    assert maxdiff==0;save(out/'COUNT_CHECKS.json',dict(cells_checked=nc,max_count_difference=maxdiff,optimizer_calls=0))
if __name__=='__main__':main()
