"""Independent streaming readback and paired seed inference. Never fits or generates inputs."""
import argparse,collections,csv,gzip,hashlib,json,math,sys
from pathlib import Path
import numpy as np

def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(x):return hashlib.sha256(canonical(x)).hexdigest()
def save(p,x):
    with p.open('xb') as f:f.write(canonical(x))
def csvsave(p,rows):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(rows)
def objective(unit,method,x):
    o=unit['obs'];pts=x[:24].reshape(6,2,2);anchors=np.array(o['anchors']);n=len(x)
    delta=pts[:,:,None,:]-anchors[None,None,:,:];rr=np.linalg.norm(delta,axis=-1)
    peer=pts[:,1]-pts[:,0];pr=np.linalg.norm(peer,axis=-1)
    v=np.column_stack([rr.reshape(6,8),pr]);j=np.zeros((6,9,n))
    for t in range(6):
        for car in range(2):j[t,4*car:4*car+4,4*t+2*car:4*t+2*car+2]=delta[t,car]/rr[t,car,:,None]
        j[t,8,4*t:4*t+2]=-peer[t]/pr[t];j[t,8,4*t+2:4*t+4]=peer[t]/pr[t]
    if method=='B2':
        k=0 if o['kind']=='wall' else 8;v[:,k]+=x[-1];j[:,k,-1]=1
    y=np.array(o['ranges']).reshape(6,9)
    if method=='B3':y=y-np.array(unit['oracle']).reshape(6,9)
    keep=8 if method=='B0' else 9
    res=[((v-y)/o['range_sigma'])[:,:keep].ravel()];jac=[j[:,:keep].reshape(-1,n)/o['range_sigma']]
    mj=np.zeros((20,n))
    for k in range(20):mj[k,k]=-1;mj[k,k+4]=1
    res.append((np.diff(pts.reshape(6,4),axis=0).ravel()-o['movement'])/o['motion_sigma']);jac.append(mj/o['motion_sigma'])
    if o['prior_sigma'] is not None:
        res.append((x[:4]-o['prior_center'])/o['prior_sigma']);pj=np.zeros((4,n));pj[:,:4]=np.eye(4);jac.append(pj/o['prior_sigma'])
    return np.concatenate(res),np.vstack(jac)

def interval(values,planned,cfg,complete=True):
    s=cfg['statistics'];a=np.array(values);n=len(a)
    out=dict(planned_seeds=planned,valid_seeds=n,missing_seeds=planned-n,mean=float(a.mean()) if n else None,ci95=None,ci_status=None,estimand='mean on available paired seeds; conditional if any missing')
    if not complete:out['ci_status']='RUN_INCOMPLETE'
    elif n<s['minimum_valid_seeds']:out['ci_status']='INSUFFICIENT_VALID_SEEDS'
    elif (planned-n)/planned>s['maximum_missing_fraction_for_ci']:out['ci_status']='MISSING_EXCEEDS_LIMIT'
    else:
        rng=np.random.Generator(np.random.PCG64(s['bootstrap_seed']));idx=rng.integers(0,n,(s['bootstrap_repetitions'],n))
        alpha=(1-s['confidence'])/2
        out.update(ci95=np.quantile(a[idx].mean(axis=1),[alpha,1-alpha]).tolist(),ci_status='POINTWISE_CONDITIONAL' if n<planned else 'POINTWISE_COMPLETE')
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);z=ap.parse_args();z.out.mkdir(parents=True,exist_ok=False)
    meta=read(z.run/'RUN.json');cfg=meta['config'];assert digest(cfg)==meta['config_sha256'] and digest(meta['plan'])==meta['plan_sha256']
    rows=[];index={};stagecounts=collections.Counter();p0counts=collections.Counter();gradmax=0.;resmax=0.;jacmax=0.;metricmax=0.;records=0;missing=0
    allcompact=[];inputs=[]
    for item in meta['plan']:
        unit=read(z.run/'inputs'/(item['id']+'.json.gz'));inputs.append(unit)
        assert unit['condition']==item['condition'] and unit['seed']==item['seed'] and digest(unit['obs'])==unit['input_sha256']
        for m in cfg['methods']:
            compact={};states={}
            for stage in ['P0','P1']:
                path=z.run/'stages'/item['id']/(m+'-'+stage+'.json.gz')
                if not path.exists():missing+=1;states[stage]=None;continue
                stored=read(path);r=stored['result'];records+=1
                assert stored['unit']==item['id'] and stored['method']==m and stored['stage']==stage and stored['config_sha256']==meta['config_sha256'] and stored['input_record_sha256']==digest(unit)
                xx=r['estimate'];states[stage]=r
                if r['usable_estimate']:
                    x=np.array(xx);error=x[:24].reshape(6,2,2)-unit['truth'];mse=np.mean(np.sum(error**2,axis=-1),axis=0)
                    metricmax=max(metricmax,float(max(abs(mse-r['position_mse']))))
                    assert np.allclose(mse,r['position_mse'],atol=1e-12,rtol=0)
                    assert np.allclose(np.sqrt(mse),r['position_rmse'],atol=1e-12,rtol=0)
                    assert r['position_error_exceeds']==(np.sqrt(mse.mean())>cfg['statistics']['position_rmse_threshold_m'])
                    assert r['position_error_exceeds_by_car']==(np.sqrt(mse)>cfg['statistics']['position_rmse_threshold_m']).tolist()
                    if m=='B2':
                        be=float(x[-1]-unit['condition']['bias_m']);assert abs(be-r['bias_error'])<1e-12
                        assert r['bias_error_exceeds']==(abs(be)>cfg['statistics']['absolute_bias_error_threshold_m'])
                    if r['endpoint_valid']:
                        rr,j=objective(unit,m,x);g=j.T@rr
                        resmax=max(resmax,float(max(abs(rr-r['residual']))));jacmax=max(jacmax,float(np.max(abs(j-r['jacobian']))));gradmax=max(gradmax,float(max(abs(g-r['gradient']))))
                        assert abs(.5*rr@rr-r['cost'])<1e-10
                        assert np.allclose(g*(np.r_[np.ones(24),.1] if m=='B2' else np.ones(24)),r['scaled_gradient'],atol=1e-9,rtol=0)
                    # Use independently evaluated errors for derived tables.
                    r=dict(r,position_mse=mse.tolist(),position_rmse=np.sqrt(mse).tolist())
                    states[stage]=r
                else:assert r['position_mse']==[None,None] and r['position_rmse']==[None,None] and r['bias_error'] is None
                accepted=bool(r['endpoint_valid'] and r['scipy_success'] and r['gradient_inf'] is not None and r['gradient_inf']<=cfg['acceptance']['physical_gradient_inf_max'])
                assert accepted==r['accepted']
                if r['execution']=='EXCEPTION':category=r['category'];assert category in ['EXCEPTION','INPUT_EXCEPTION']
                elif r['execution']=='SKIPPED':category='SKIPPED_INVALID_P0';assert not states['P0']['endpoint_valid'] and r['residual_calls']==0
                elif not r['endpoint_valid']:category='NONFINITE'
                elif accepted:category='ACCEPTED'
                elif r['hit_budget']:category='BUDGET_EXHAUSTED'
                elif r['gradient_inf']>cfg['acceptance']['physical_gradient_inf_max']:category='NOT_STATIONARY'
                else:category='SOLVER_STOP_FAILURE'
                assert category==r['category']
                stagecounts[stage+':'+category]+=1
                info={k:v for k,v in r['information'].items() if k!='covariance'}
                compact[stage]={k:v for k,v in r.items() if k not in ['jacobian','information']};compact[stage]['information']=info
            final=states['P1'];p0=states['P0'];assert final is not None and p0 is not None
            p0counts[p0['category']]+=1
            row=dict(unit=item['id'],condition=item['condition'],seed=item['seed'],method=m,completed=True,category=final['category'],accepted=final['accepted'],usable_estimate=final['usable_estimate'],position_mse=final['position_mse'],position_rmse=final['position_rmse'],position_error_exceeds=final['position_error_exceeds'],position_error_exceeds_by_car=final['position_error_exceeds_by_car'],bias_error=final['bias_error'],bias_error_exceeds=final['bias_error_exceeds'],P0_category=p0['category'],D=[None,None],D_both_accepted=[None,None],B2_minus_B1=[None,None],B2_minus_B1_both_accepted=[None,None],gradient_inf=final['gradient_inf'],termination=final['termination'],nfev_total=(p0['nfev'] or 0)+(final['nfev'] or 0),rank=final['information']['rank'])
            rows.append(row);index[item['id'],m]=row
            allcompact.append(dict(unit=item['id'],method=m,input_record_sha256=digest(unit),stages=compact))
    assert len(rows)==7200 and records==14400 and missing==0
    assert resmax<=cfg['verification']['residual_absolute_tolerance'] and gradmax<=cfg['verification']['gradient_absolute_tolerance'] and jacmax<1e-10
    for r in rows:
        b0=index[r['unit'],'B0'];b1=index[r['unit'],'B1']
        if r['usable_estimate'] and b0['usable_estimate']:
            r['D']=(np.array(r['position_mse'])-b0['position_mse']).tolist()
            if r['accepted'] and b0['accepted']:r['D_both_accepted']=r['D'][:]
        if r['method']=='B2' and r['usable_estimate'] and b1['usable_estimate']:
            r['B2_minus_B1']=(np.array(r['position_mse'])-b1['position_mse']).tolist()
            if r['accepted'] and b1['accepted']:r['B2_minus_B1_both_accepted']=r['B2_minus_B1'][:]
    groups=[]
    for cid in dict.fromkeys(r['condition']['id'] for r in rows):
        for method in cfg['methods']:
            rs=sorted([r for r in rows if r['condition']['id']==cid and r['method']==method],key=lambda r:r['seed']);n=len(rs)
            group=dict(condition=rs[0]['condition'],method=method,planned=n,completed=n,valid_error_count=sum(r['usable_estimate'] for r in rs),accepted=sum(r['accepted'] for r in rs),numerical_failures=sum(not r['accepted'] for r in rs),not_completed=0,categories=dict(collections.Counter(r['category'] for r in rs)),P0_categories=dict(collections.Counter(r['P0_category'] for r in rs)),position_error_valid=sum(r['position_error_exceeds'] is not None for r in rs),position_error_exceeds=sum(r['position_error_exceeds'] is True for r in rs),position_error_exceeds_by_car=[sum(r['position_error_exceeds_by_car'][i] is True for r in rs) for i in [0,1]],bias_error_valid=sum(r['bias_error'] is not None for r in rs),bias_error_exceeds=sum(r['bias_error_exceeds'] is True for r in rs),metrics={})
            for field in ['position_mse','position_rmse','D','D_both_accepted','B2_minus_B1','B2_minus_B1_both_accepted']:
                if field.startswith('B2_') and method!='B2':continue
                for car in range(2):group['metrics'][field+f'_car{car+1}']=interval([r[field][car] for r in rs if r[field][car] is not None],n,cfg)
            if method=='B2':group['metrics']['bias_error']=interval([r['bias_error'] for r in rs if r['bias_error'] is not None],n,cfg)
            groups.append(group)
    flat=[]
    for r in rows:
        row={**r['condition'],**{k:r[k] for k in ['unit','seed','method','completed','category','accepted','usable_estimate','bias_error','bias_error_exceeds','P0_category','gradient_inf','termination','nfev_total','rank']}}
        for k in ['position_mse','position_rmse','D','D_both_accepted','B2_minus_B1','B2_minus_B1_both_accepted','position_error_exceeds_by_car']:
            for car in range(2):row[k+f'_car{car+1}']=r[k][car]
        flat.append(row)
    csvsave(z.out/'PER_RUN.csv',flat)
    summaries=[]
    for g in groups:
        for metric,v in g['metrics'].items():summaries.append(dict(**g['condition'],method=g['method'],metric=metric,planned=g['planned'],completed=g['completed'],accepted=g['accepted'],**{k:v[k] for k in ['valid_seeds','missing_seeds','mean','ci_status']},ci_lower=v['ci95'][0] if v['ci95'] else None,ci_upper=v['ci95'][1] if v['ci95'] else None))
    csvsave(z.out/'SUMMARY.csv',summaries)
    csvsave(z.out/'FAILURES.csv',[{**g['condition'],'method':g['method'],**{k:g[k] for k in ['planned','completed','valid_error_count','accepted','numerical_failures','not_completed','position_error_valid','position_error_exceeds','bias_error_valid','bias_error_exceeds']},'categories':json.dumps(g['categories']),'P0_categories':json.dumps(g['P0_categories'])} for g in groups])
    # Explicit same-seed prior contrasts; supplemental descriptive intervals use frozen bootstrap settings.
    prior=[]
    for geo in ['good','weak','near']:
        for method in cfg['methods']:
            pools={panel:sorted([r for r in rows if r['condition']['panel']==panel and r['condition']['geometry']==geo and r['condition']['motion']=='static' and r['condition']['kind']=='peer' and r['condition']['bias_m']==.3 and r['method']==method],key=lambda r:r['seed']) for panel in ['core','no_prior','strong','shifted_strong']}
            for dest,base in [('no_prior','core'),('strong','core'),('shifted_strong','strong')]:
                assert [r['seed'] for r in pools[dest]]==[r['seed'] for r in pools[base]]
                for metric in ['position_mse_car1','position_mse_car2','bias_error']:
                    if metric=='bias_error' and method!='B2':continue
                    vals=[]
                    for ra,rb in zip(pools[dest],pools[base]):
                        if ra['usable_estimate'] and rb['usable_estimate']:
                            a=ra['bias_error'] if metric=='bias_error' else ra['position_mse'][int(metric[-1])-1]
                            b=rb['bias_error'] if metric=='bias_error' else rb['position_mse'][int(metric[-1])-1]
                            vals.append(a-b)
                    iv=interval(vals,50,cfg)
                    prior.append(dict(geometry=geo,method=method,contrast=dest+' minus '+base,metric=metric,mean=iv['mean'],valid_seeds=iv['valid_seeds'],ci_lower=iv['ci95'][0] if iv['ci95'] else None,ci_upper=iv['ci95'][1] if iv['ci95'] else None,ci_status=iv['ci_status']))
    csvsave(z.out/'PRIOR_CONTRASTS.csv',prior)
    save(z.out/'GROUPS.json',groups)
    # Compact evidence retains estimates, r, gradients, spectra, failure metadata; J/Cov regenerate from locked math.
    with (z.out/'EVIDENCE.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:
            f.write(canonical(dict(type='RUN',value=meta))+b'\n')
            for u in inputs:f.write(canonical(dict(type='INPUT',value=u))+b'\n')
            for u in allcompact:f.write(canonical(dict(type='METHOD',value=u))+b'\n')
    checks=dict(passed=True,planned_methods=7200,completed_methods=len(rows),missing_methods=0,stage_records=records,missing_stages=missing,independent_seeds=50,paired_units=1800,usable_final_estimates=sum(r['usable_estimate'] for r in rows),accepted_final=sum(r['accepted'] for r in rows),stage_categories=dict(stagecounts),max_residual_difference=resmax,max_jacobian_difference=jacmax,max_gradient_difference=gradmax,max_metric_difference=metricmax,optimizer_calls=0,formal_inputs_generated_by_readback=0,config_sha256=meta['config_sha256'])
    save(z.out/'INDEPENDENT_CHECKS.json',checks);print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
