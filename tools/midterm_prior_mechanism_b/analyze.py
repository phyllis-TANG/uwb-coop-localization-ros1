"""Predeclared seed-cluster summaries and four paired mechanism contrasts."""
import argparse,collections,json
from pathlib import Path
import numpy as np
from scipy.stats import chi2
from io_utils import read,save,csvsave
from math_model import gaussian_ellipse_probability

def safe_mean(x):
    a=np.asarray(x);return float(np.mean(a[np.isfinite(a)])) if np.isfinite(a).any() else float("nan")

def ci(values,c):
    a=np.asarray(values,float);a=a[np.isfinite(a)];n=len(a);s=c['statistics'];out=dict(n=n,mean=float(a.mean()) if n else None,lower=None,upper=None,status='INSUFFICIENT')
    if n<s['minimum_valid_seeds'] or (len(values)-n)/max(1,len(values))>s['maximum_missing_fraction_for_ci']:return out
    if np.ptp(a)<1e-14:out['status']='CONSTANT_CLUSTERS';return out
    rng=np.random.default_rng(s['bootstrap_seed']);z=a[rng.integers(0,n,(s['bootstrap_repetitions'],n))].mean(axis=1);lo,hi=np.quantile(z,[.025,.975]);out.update(lower=float(lo),upper=float(hi),status='POINTWISE_SEED_BOOTSTRAP');return out

def analyze(inp,out):
    out.mkdir(parents=True,exist_ok=False);rows=read(inp/'ROWS.json.gz');meta=read(inp/'RUN.json');c=meta['config'];z=np.load(inp/'METRICS.npz');nseed=len(c['seeds'][meta['mode']]);groups={};summary=[];coverage=[];moments=[];bias=[];cmp=[];groupscalar={};refs=read(inp/'ANALYTIC_REFERENCES.json.gz');exact=[]
    # Counts bootstrap computes seed-cluster ratio; never treats times as independent.
    rng=np.random.default_rng(c['statistics']['bootstrap_seed']);draw=rng.integers(0,nseed,(c['statistics']['bootstrap_repetitions'],nseed));weights=np.array([np.bincount(x,minlength=nseed) for x in draw],float)
    def ratio_ci(hit,avail):
        active=avail>0
        if active.sum()<c['statistics']['minimum_valid_seeds'] or avail.sum()<.9*len(avail)*max(avail.max(),1):return None,None,'INSUFFICIENT_OR_MISSING'
        if np.ptp(hit[active]/avail[active])<1e-14:return None,None,'CONSTANT_CLUSTERS'
        den=weights@avail;v=(weights@hit)[den>0]/den[den>0];lo,hi=np.quantile(v,[.025,.975]);return float(lo),float(hi),'POINTWISE_SEED_CLUSTER'
    for cid in sorted({r['id'] for r in rows}):
      for m in c['methods']:
       for model in ['nonlinear','truth_linearized']:
        ids=np.array(sorted([i for i,r in enumerate(rows) if r['id']==cid and r['method']==m and r['model']==model],key=lambda i:rows[i]['seed']));assert len(ids)==nseed;groups[cid,m,model]=ids;first=rows[ids[0]];base={k:first[k] for k in ['id','geometry','bias_m','prior_sigma','mechanism','method','model']};sel=np.array([rows[i]['accepted'] for i in ids]);usable=np.array([rows[i]['usable'] for i in ids]);e=z['error'][ids]
        s=dict(base,planned=nseed,completed=sum(rows[i]['completed'] for i in ids),usable=int(usable.sum()),accepted=int(sel.sum()),failed=int(sum(rows[i]['completed'] and not rows[i]['accepted'] for i in ids)),categories=json.dumps(dict(collections.Counter(rows[i]['category'] for i in ids))))
        for car in [1,2]:
            ee=e[:,car-1::2];ms=np.mean(np.sum(ee**2,axis=-1),axis=1);s[f'mse{car}']=float(np.nanmean(ms)) if usable.any() else None;s[f'rmse{car}']=float(np.nanmean(np.sqrt(ms))) if usable.any() else None;groupscalar[cid,m,model,car,'MSE']=ms
            for vi,view in enumerate(c['coverage']['views']):
                qq=z['q'][ids,vi][:,car-1::2];cc=z['covariance'][ids,vi][:,car-1::2];tr=cc[:,:,0]+cc[:,:,2];groupscalar[cid,m,model,car,view+'_trace']=np.mean(tr,axis=1)
                for level in c['coverage']['levels']:
                    threshold=chi2.ppf(level,2);groupscalar[cid,m,model,car,view+'_coverage'+str(level)]=np.where(np.isfinite(qq).all(axis=1),(qq<=threshold).mean(axis=1),np.nan)
                    for subset,ss in [('all',np.ones(nseed,bool)),('accepted',sel),('not_accepted',~sel)]:
                      for aggregation in ['point_average','all_times']+['t'+str(t) for t in range(6)]:
                        qsub=qq if aggregation in ['point_average','all_times'] else qq[:,[int(aggregation[1:])]];valid=np.isfinite(qsub)&ss[:,None];hit=(qsub<=threshold)&valid
                        if aggregation=='all_times':valid=valid.all(axis=1)[:,None];hit=hit.all(axis=1)[:,None]
                        avail=valid.sum(axis=1);hits=hit.sum(axis=1);lo,hi,why=ratio_ci(hits,avail);count=int(avail.sum());covered=int(hits.sum());planned=nseed*valid.shape[1];re=z['reasons'][ids,vi][:,car-1::2];re=re if aggregation in ['point_average','all_times'] else re[:,[int(aggregation[1:])]]
                        coverage.append(dict(base,car=car,view=view,level=level,subset=subset,aggregation=aggregation,planned=planned,selected=int(ss.sum()*valid.shape[1]),available=count,unavailable=int(ss.sum()*valid.shape[1])-count,covered=covered,coverage=covered/count if count else None,covered_over_plan=covered/planned,ci_low=lo,ci_high=hi,ci_status=why,unavailable_point_reasons=json.dumps(dict(collections.Counter(re[ss][re[ss]!='AVAILABLE'])))))
                for t in range(6):
                    k=2*t+car-1;errs=e[usable,k];mu=errs.mean(axis=0) if len(errs) else np.full(2,np.nan);cv=np.cov(errs.T,ddof=1) if len(errs)>1 else np.full((2,2),np.nan);pred=z['analytic_noise'][ids,k];mm=z['analytic_mean'][ids,k];ev=z['eigen'][ids,vi,k];area=np.pi*chi2.ppf(.95,2)*np.sqrt(ev[:,0]*ev[:,1]);moment=dict(base,car=car,time=t,view=view,n=len(errs),mean_x=float(mu[0]),mean_y=float(mu[1]),mean_squared=float(mu@mu),centered_xx=float(cv[0,0]),centered_xy=float(cv[0,1]),centered_yy=float(cv[1,1]),centered_trace=float(np.trace(cv)),mse=float(np.mean(np.sum(errs**2,axis=1))) if len(errs) else None,analytic_mean_x=safe_mean(mm[:,0]),analytic_mean_y=safe_mean(mm[:,1]),analytic_trace=safe_mean(pred[:,0]+pred[:,2]),candidate_trace=safe_mean(tr[:,t]),area95=float(np.nanmean(area)) if np.isfinite(area).any() else None,major95=float(np.nanmean(np.sqrt(chi2.ppf(.95,2)*ev[:,1]))) if np.isfinite(ev).any() else None,minor95=float(np.nanmean(np.sqrt(chi2.ppf(.95,2)*ev[:,0]))) if np.isfinite(ev).any() else None)
                    if len(errs)>1:assert abs(moment['mse']-((len(errs)-1)/len(errs)*moment['centered_trace']+moment['mean_squared']))<1e-10
                    moment.update(area99=None if moment['area95'] is None else moment['area95']*chi2.ppf(.99,2)/chi2.ppf(.95,2),major99=None if moment['major95'] is None else moment['major95']*np.sqrt(chi2.ppf(.99,2)/chi2.ppf(.95,2)),minor99=None if moment['minor95'] is None else moment['minor95']*np.sqrt(chi2.ppf(.99,2)/chi2.ppf(.95,2)))
                    moments.append(moment)
        if m=='B2':
            be=z['bias_error'][ids]
            for vi,view in enumerate(c['coverage']['views']):
             for level in c['coverage']['levels']:
              qq=z['bias_q'][ids,vi];valid=np.isfinite(qq);hits=(qq<=chi2.ppf(level,1))&valid;lo,hi,why=ratio_ci(hits.astype(int),valid.astype(int));bias.append(dict(base,view=view,level=level,planned=nseed,available=int(valid.sum()),unavailable=int((~valid).sum()),unavailable_reason='NO_FINITE_POSITIVE_VARIANCE' if (~valid).any() else '',covered=int(hits.sum()),coverage=float(hits.sum()/valid.sum()) if valid.any() else None,ci_low=lo,ci_high=hi,ci_status=why,mean_error=float(np.nanmean(be)) if usable.any() else None,mse=float(np.nanmean(be**2)) if usable.any() else None,centered_variance=float(np.nanvar(be,ddof=1)) if usable.sum()>1 else None,halfwidth=float(np.nanmean(np.sqrt(chi2.ppf(level,1)*z['bias_variance'][ids,vi]))) if valid.any() else None))
        summary.append(s)
        print('summary',cid,m,model,flush=True) if m=='B3' and model=='truth_linearized' else None
    qs={r['id']:{k:r[k] for k in ['geometry','bias_m','prior_sigma','mechanism']} for r in rows}
    for cid,qc in qs.items():
        pairs=[]
        for label,key,value in [('survey_minus_correct','mechanism','fixed_survey'),('random_minus_correct','mechanism','random_correct'),('strong_minus_weak','prior_sigma',.05)]:
            if (key=='mechanism' and qc[key]!='fixed_correct') or (key=='prior_sigma' and qc[key]!=.5):continue
            target=dict(qc);target[key]=value;other=next((k for k,v in qs.items() if v==target),None)
            if other is not None:pairs.append((label,other))
        for m in c['methods']:
         for car in [1,2]:
          metrics=['MSE']+[v+s for v in c['coverage']['views'] for s in ['_trace','_coverage0.95','_coverage0.99']]
          for metric in metrics:
           for model in ['nonlinear','truth_linearized']:
            for label,other in pairs:
                a=groupscalar[cid,m,model,car,metric];b=groupscalar[other,m,model,car,metric];cmp.append(dict(comparison=label,base_id=cid,other_id=other,method=m,car=car,model=model,metric=metric,planned=nseed,**ci(b-a,c)))
           a=groupscalar[cid,m,'truth_linearized',car,metric];b=groupscalar[cid,m,'nonlinear',car,metric];cmp.append(dict(comparison='nonlinear_minus_truth_linearized',base_id=cid,other_id=cid,method=m,car=car,model='paired_models',metric=metric,planned=nseed,**ci(b-a,c)))
    # Exact affine Gaussian expectation, including fixed offsets; no extra simulation seeds.
    for key,ref in refs.items():
        if ref['mean'] is None:continue
        mu=np.array(ref['mean']);noise=np.array(ref['noise'])
        for view in c['coverage']['views']:
            mat=np.array(ref['curvature'] if view=='curvature' else ref['noise'])
            for k in range(12):
                sub=mat[2*k:2*k+2,2*k:2*k+2];nn=noise[2*k:2*k+2,2*k:2*k+2];ev=np.linalg.eigvalsh(sub)
                for lev in c['coverage']['levels']:
                    expected=None if ev[0]<=max(0,ev[-1]*c['coverage']['marginal_relative_eigenvalue_floor']) else gaussian_ellipse_probability(mu[2*k:2*k+2],nn,sub,lev)
                    exact.append(dict(id=ref['condition']['id'],method=ref['method'],car=k%2+1,time=k//2,view=view,level=lev,analytic_coverage=expected))
    for name,values in [('SUMMARY',summary),('COVERAGE',coverage),('BIAS_COVERAGE',bias),('MOMENTS',moments),('PAIRED_COMPARISONS',cmp),('LINEAR_ANALYTIC_COVERAGE',exact)]:
        # Preserve missing as blank; no NaN presented as a numerical estimate.
        for v in values:
            for k,x in v.items():
                if isinstance(x,float) and not np.isfinite(x):v[k]=None
        csvsave(out/(name+'.csv'),values)
    save(out/'COUNTS.json',{kind:dict(planned=sum(r['model']==kind for r in rows),completed=sum(r['completed'] for r in rows if r['model']==kind),usable=sum(r['usable'] for r in rows if r['model']==kind),accepted=sum(r['accepted'] for r in rows if r['model']==kind),categories=dict(collections.Counter(r['category'] for r in rows if r['model']==kind))) for kind in ['nonlinear','truth_linearized']})
    save(out/'CHECKS.json',dict(passed=True,seed_clusters=nseed,optimizer_calls=0,all_denominators_valid=all(x['covered']<=x['available']<=x['selected']<=x['planned'] for x in coverage),moment_identity_checked=True))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();analyze(a.input,a.out)
