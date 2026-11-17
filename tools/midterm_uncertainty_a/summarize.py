"""Seed-cluster descriptive summaries, no localization/refitting."""
import argparse,csv,json,gzip
from pathlib import Path
from collections import Counter
import numpy as np
from scipy.stats import chi2,spearmanr
VIEWS=['total_curvature','fixed_prior_noise','data_only']
def dump(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def table(p,rows):
    if not rows:return
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
def interval(c,v,counts):
    active=v>0
    if active.sum()<30:return None,None,'FEWER_THAN_30_EFFECTIVE_SEEDS'
    if v.sum()<.9*len(v)*max(v.max(),1):return None,None,'MORE_THAN_10_PERCENT_UNAVAILABLE_OR_UNSELECTED'
    proportions=c[active]/v[active]
    if np.ptp(proportions)<1e-14:return None,None,'CONSTANT_EMPIRICAL_CLUSTERS'
    den=counts@v;num=counts@c;z=num[den>0]/den[den>0]
    lo,hi=np.quantile(z,[.025,.975]);return float(lo),float(hi),'SEED_CLUSTER_PERCENTILE'
def metrics(q,selected,threshold,counts,trajectory=False):
    q=np.atleast_2d(q) if q.ndim==1 else q
    ok=np.isfinite(q);covered=ok&(q<=threshold)
    if trajectory:
        ok=ok.all(axis=1)[:,None];covered=covered.all(axis=1)[:,None]
    planned=ok.size;subset=int(selected.sum()*ok.shape[1]);v=(ok*selected[:,None]).sum(axis=1);c=(covered*selected[:,None]).sum(axis=1)
    lo,hi,why=interval(c,v,counts);jl,jh,jwhy=interval(c,np.full(len(q),ok.shape[1]),counts)
    return dict(planned=planned,selected_planned=subset,selected_seeds=int(selected.sum()),available=int(v.sum()),unavailable=subset-int(v.sum()),covered=int(c.sum()),coverage_available=float(c.sum()/v.sum()) if v.sum() else None,covered_over_full_plan=float(c.sum()/planned),ci_low=lo,ci_high=hi,ci_status=why,joint_ci_low=jl,joint_ci_high=jh,joint_ci_status=jwhy)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();args.out.mkdir(parents=True,exist_ok=False)
    rows=list(csv.DictReader((args.input/'RUNS.csv').open()));z=np.load(args.input/'MARGINALS.npz');print(z.files,flush=True)
    q=z['position_q'];cov=z['covariance_components'];err=z['position_error'];bq=z['bias_q'];bv=z['bias_variance'];be=z['bias_error'];r2=z['position_bias_multiple_R2'];reason=z['reasons']
    counts=np.zeros((10000,50));draw=np.random.default_rng(91327061).integers(0,50,(10000,50))
    for i in range(10000):counts[i]=np.bincount(draw[i],minlength=50)
    cover=[];bias=[];moments=[];rel=[];groups={};conditions={}
    for cid in sorted({r['id'] for r in rows}):
      for method in ['B0','B1','B2','B3']:
        ids=np.array(sorted([i for i,r in enumerate(rows) if r['id']==cid and r['method']==method],key=lambda i:int(rows[i]['seed'])));assert len(ids)==50
        groups[cid,method]=ids;first=rows[ids[0]];base={k:first[k] for k in ['id','geometry','motion','kind','bias_m','panel','prior','method']};conditions[cid]=base
        accepted=np.array([rows[i]['accepted']=='True' for i in ids]);subsets={'all':np.ones(50,bool),'accepted':accepted,'not_accepted':~accepted}
        for vi,view in enumerate(VIEWS):
          for car in [1,2]:
            blocks=np.arange(car-1,12,2);qq=q[ids,vi][:,blocks]
            for level in [.95,.99]:
              for sub,sel in subsets.items():
                for mode in ['point_average','all_times']+['t'+str(t) for t in range(6)]:
                  a=qq if mode in ['point_average','all_times'] else qq[:,[int(mode[1:])]]
                  item=dict(base,view=view,car=car,level=level,subset=sub,aggregation=mode,**metrics(a,sel,chi2.ppf(level,2),counts,mode=='all_times'))
                  rr=reason[ids,vi][:,blocks];rr=rr if mode in ['point_average','all_times'] else rr[:,[int(mode[1:])]]
                  item['unavailable_point_reasons']=json.dumps(dict(Counter(rr[sel][rr[sel]!='AVAILABLE'])),sort_keys=True)
                  cover.append(item)
            for t,k in enumerate(blocks):
              e=err[ids,k];cc=cov[ids,vi,k];valid=np.isfinite(cc).all(axis=1);tr=cc[:,0]+cc[:,2];det=cc[:,0]*cc[:,2]-cc[:,1]**2
              empirical=np.cov(e.T,ddof=1);mu=e.mean(axis=0)
              moments.append(dict(base,view=view,car=car,time=t,seeds=50,available=int(valid.sum()),mean_ex=float(mu[0]),mean_ey=float(mu[1]),mean_error_squared=float(mu@mu),mse=float(np.mean(np.sum(e*e,axis=1))),empirical_cov_xx=float(empirical[0,0]),empirical_cov_xy=float(empirical[0,1]),empirical_cov_yy=float(empirical[1,1]),empirical_trace=float(np.trace(empirical)),predicted_trace=float(np.mean(tr[valid])) if valid.any() else None,mean_q=float(np.mean(q[ids,vi,k][valid])) if valid.any() else None,mean_area95=float(np.mean(np.pi*chi2.ppf(.95,2)*np.sqrt(det[valid]))) if valid.any() else None))
            actual=np.sqrt(np.mean(np.sum(err[ids][:,blocks]**2,axis=2),axis=1));tr=cov[ids,vi][:,blocks,0]+cov[ids,vi][:,blocks,2];unc=np.sqrt(np.mean(tr,axis=1));res=np.array([float(rows[i]['data_residual_rms']) for i in ids]);good=np.isfinite(unc)
            def rho(a,b):
                return float(spearmanr(a,b).statistic) if len(a)>2 and np.ptp(a)>0 and np.ptp(b)>0 else None
            rel.append(dict(base,view=view,car=car,seeds=50,available=int(good.sum()),residual_error_spearman=rho(res,actual),uncertainty_error_spearman=rho(unc[good],actual[good]),residual_uncertainty_spearman=rho(res[good],unc[good])))
          if method=='B2':
            for level in [.95,.99]:
              for sub,sel in subsets.items():
                item=dict(base,view=view,level=level,subset=sub,**metrics(bq[ids,vi,None],sel,chi2.ppf(level,1),counts))
                valid=np.isfinite(bq[ids,vi])&sel;ee=be[ids][sel];vv=bv[ids,vi][valid];cou=r2[ids,vi][valid]
                item.update(unavailable_reasons=json.dumps(dict(Counter(z['bias_reasons'][ids,vi][sel][~np.isfinite(bq[ids,vi][sel])]))),mean_error=float(ee.mean()) if len(ee) else None,mse=float(np.mean(ee**2)) if len(ee) else None,empirical_variance=float(np.var(ee,ddof=1)) if len(ee)>1 else None,mean_predicted_variance=float(vv.mean()) if len(vv) else None,mean_halfwidth=float(np.mean(np.sqrt(chi2.ppf(level,1)*vv))) if len(vv) else None,mean_position_bias_R2=float(np.nanmean(cou)) if np.isfinite(cou).any() else None)
                bias.append(item)
    table(args.out/'COVERAGE.csv',cover);table(args.out/'BIAS_COVERAGE.csv',bias);table(args.out/'EMPIRICAL_MOMENTS.csv',moments);table(args.out/'ASSOCIATIONS.csv',rel)
    pri=[]
    for geom in ['good','weak','near']:
      match={b['panel']:cid for cid,b in conditions.items() if b['geometry']==geom and b['motion']=='static' and b['kind']=='peer' and float(b['bias_m'])==.3}
      for method in ['B0','B1','B2','B3']:
       for panel in ['no_prior','strong','shifted_strong']:
        if panel not in match:continue
        a=groups[match['core'],method];b=groups[match[panel],method];assert [rows[i]['seed'] for i in a]==[rows[i]['seed'] for i in b]
        for car in [1,2]:
         blocks=np.arange(car-1,12,2)
         for vi,view in enumerate(VIEWS):
          ea=np.mean(np.sum(err[a][:,blocks]**2,axis=2),axis=1);eb=np.mean(np.sum(err[b][:,blocks]**2,axis=2),axis=1);ta=np.mean(cov[a,vi][:,blocks,0]+cov[a,vi][:,blocks,2],axis=1);tb=np.mean(cov[b,vi][:,blocks,0]+cov[b,vi][:,blocks,2],axis=1);valid=np.isfinite(ta)&np.isfinite(tb)
          pri.append(dict(geometry=geom,method=method,car=car,view=view,comparison=panel+'-core',core_id=match['core'],other_id=match[panel],paired_seeds=50,paired_available=int(valid.sum()),core_mse=float(ea.mean()),other_mse=float(eb.mean()),mse_difference=float(np.mean(eb-ea)),core_trace=float(np.mean(ta[valid])) if valid.any() else None,other_trace=float(np.mean(tb[valid])) if valid.any() else None,tightens_and_error_increases=int(np.sum(valid&(tb<ta)&(eb>ea)))))
    table(args.out/'PRIOR_COMPARISONS.csv',pri)
    table(args.out/'NOT_STATIONARY.csv',[r for r in rows if r['accepted']!='True'])
    worst=np.where(np.array([r['method']=='B2' for r in rows])[:,None],q[:,0,:],np.nan);i,k=np.unravel_index(np.nanargmax(worst),worst.shape)
    cases={'worst_B2_total_point':dict(rows[i],block=int(k),q=float(q[i,0,k]),error=err[i,k].tolist(),covariance_components=cov[i,0,k].tolist()),'first_unavailable':None}
    unavailable=np.argwhere(~np.isfinite(q))
    if len(unavailable):
        i,v,k=unavailable[0];cases['first_unavailable']=dict(rows[i],view=VIEWS[v],block=int(k),reason=str(reason[i,v,k]))
    dump(args.out/'CASES.json',cases)
    dump(args.out/'SUMMARY_CHECKS.json',dict(position_rows=len(cover),bias_rows=len(bias),moment_rows=len(moments),seed_clusters=50,bootstrap_draws=10000,all_position_checks_passed=all(r['available']+r['unavailable']==r['selected_planned'] and r['covered']<=r['available']<=r['selected_planned']<=r['planned'] for r in cover),not_stationary=25))
if __name__=='__main__':main()
