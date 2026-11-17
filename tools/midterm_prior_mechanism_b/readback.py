"""No-optimizer independent readback, full-denominator metrics and portable states."""
import argparse,collections,gzip,hashlib,json
from pathlib import Path
import numpy as np
from io_utils import read,save,csvsave,digest,canonical
from math_model import objective,reference,algebra,ellipse,deterministic_rhs

def input_check(u,c):
    o=u['obs'];q=u['condition'];seed=u['seed'];assert digest(o)==u['input_sha256'];truth=np.tile(np.array(c['geometries'][q['geometry']]['initial_positions']), (6,1,1));assert np.array_equal(truth,u['truth'])
    a=np.array(o['anchors']);assert np.array_equal(a,c['geometries'][q['geometry']]['anchors']);clean=np.column_stack([np.linalg.norm(truth[:,:,None,:]-a,axis=-1).reshape(6,8),np.linalg.norm(truth[:,1]-truth[:,0],axis=-1)]).ravel();inj=np.zeros(54);inj[8::9]=q['bias_m'];assert np.array_equal(inj,u['oracle'])
    for name,n in [('range',54),('motion',20)]:
        noise=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,c['noise'][name+'_stream']]))).normal(0,c['noise'][name+'_sigma_m'],n);assert np.array_equal(noise,u['noise'][name])
    assert np.max(abs(np.array(o['ranges'])-clean-inj-u['noise']['range']))<1e-12;assert np.array_equal(o['movement'],u['noise']['motion'])
    survey=np.array(c['geometries'][q['geometry']]['survey']);start=np.vstack([survey,survey+np.cumsum(np.array(o['movement']).reshape(5,4),axis=0)]).ravel();assert np.array_equal(start,o['start'])
    center=survey if q['mechanism']=='fixed_survey' else truth[0].ravel().astype(float)
    if q['mechanism']=='random_correct':
        z=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,c['prior_stream']]))).normal(size=4);assert np.array_equal(z,u['prior_standard_noise']);center=center+q['prior_sigma']*z
    else:assert u['prior_standard_noise'] is None
    assert np.array_equal(center,o['prior_center']) and o['prior_sigma']==q['prior_sigma'] and o['range_sigma']==c['noise']['range_sigma_m'] and o['motion_sigma']==c['noise']['motion_sigma_m']

def records_from_raw(run,out,meta):
    fp=None
    for i,item in enumerate(meta['plan']):
        if i%900==0:
            if fp:fp.close()
            fp=gzip.open(out/f'EVIDENCE-{i//900:03}.jsonl.gz','xb');fp.write(canonical(dict(type='RUN',value=meta))+b'\n')
        p=run/'inputs'/f"{item['id']}.json.gz";u=read(p) if p.exists() else None;results={}
        for m in meta['config']['methods']:
            results[m]={}
            for stage in ['P0','P1','LINEAR']:
                p=run/'stages'/item['id']/f'{m}-{stage}.json.gz';z=read(p) if p.exists() else None
                if z:
                    assert z['input_sha256']==digest(u) and z['config_sha256']==meta['config_sha256'];results[m][stage]=z['result']
                else:results[m][stage]=None
        record=dict(item=item,input=u,results=results);compact=dict(item=item,input=u,results={m:{stage:None if s is None else {k:v for k,v in s.items() if k not in ['residual','jacobian','gradient','scaled_gradient','analytic_covariance','information']} for stage,s in stages.items()} for m,stages in results.items()});fp.write(canonical(dict(type='UNIT',value=compact))+b'\n');yield record
    if fp:fp.close()

def records_from_evidence(path):
    for p in sorted(path.glob('EVIDENCE-*.jsonl.gz')):
        for line in gzip.open(p,'rt'):
            z=json.loads(line)
            if z['type']=='UNIT':yield z['value']

def audit(run,out,evidence=False):
    out.mkdir(parents=True,exist_ok=False);meta=read(run/'RUN.json');c=meta['config'];assert digest(c)==meta['config_sha256'] and digest(meta['plan'])==meta['plan_sha256'];save(out/'RUN.json',meta);n=len(meta['plan'])*8
    err=np.full((n,12,2),np.nan);q=np.full((n,2,12),np.nan);cov=np.full((n,2,12,3),np.nan);eigen=np.full((n,2,12,2),np.nan);bq=np.full((n,2),np.nan);bv=np.full((n,2),np.nan);be=np.full(n,np.nan);reasons=np.full((n,2,12),'NO_ESTIMATE',dtype='<U40');means=np.full((n,12,2),np.nan);predvar=np.full((n,12,3),np.nan);rows=[];checks=dict(optimizer_calls=0,inputs=0,stages=0,usable_stages=0,missing_stages=0,max_residual_diff=0.,max_jacobian_diff=0.,max_gradient_diff=0.,max_metric_diff=0.,max_linear_identity_diff=0.);seen=set();references={}
    for rec in (records_from_evidence(run) if evidence else records_from_raw(run,out,meta)):
        item,u,results=rec['item'],rec['input'],rec['results'];assert item['id'] not in seen;seen.add(item['id']);validinput=u is not None and 'generation_exception' not in u
        if validinput:input_check(u,c);checks['inputs']+=1
        for m in c['methods']:
            lin=None
            if validinput:
                xr=reference(u,m);r0,j0=objective(u,m,xr);a0=algebra(j0,m,c,item['condition']['mechanism']);mu=a0['gain']@deterministic_rhs(u,m) if a0['gain'] is not None else None;lin=(xr,r0,j0,a0,mu)
                key=item['condition']['id']+'/'+m
                if key not in references:references[key]=dict(condition=item['condition'],method=m,reference=xr.tolist(),rank=a0['rank'],mean=None if mu is None else mu.tolist(),curvature=None if mu is None else a0['curvature'].tolist(),noise=None if mu is None else a0['mechanism_noise'].tolist())
            for stage in ['P0','P1','LINEAR']:
                s=results[m][stage]
                if s is None:checks['missing_stages']+=1;continue
                checks['stages']+=1
                if not s['usable_estimate']:assert s['position_mse']==[None,None];continue
                x=np.array(s['estimate']);assert np.isfinite(x).all();checks['usable_stages']+=1
                if stage=='LINEAR':
                    xr,r0,j0,a0,mu=lin;rr=r0+j0@(x-xr);jj=j0;identity=(x-xr)-a0['gain']@(-r0);checks['max_linear_identity_diff']=max(checks['max_linear_identity_diff'],float(max(abs(identity))));assert np.max(abs(identity))<1e-9
                else:rr,jj=objective(u,m,x)
                grad=jj.T@rr;ms=np.mean(np.sum((x[:24].reshape(6,2,2)-u['truth'])**2,axis=-1),axis=0);checks['max_metric_diff']=max(checks['max_metric_diff'],float(max(abs(ms-s['position_mse']))));checks['max_gradient_diff']=max(checks['max_gradient_diff'],abs(float(max(abs(grad)))-s['gradient_inf']));assert abs(float(rr@rr/2)-s['cost'])<1e-9
                if 'residual' in s:
                    checks['max_residual_diff']=max(checks['max_residual_diff'],float(max(abs(rr-s['residual']))));checks['max_jacobian_diff']=max(checks['max_jacobian_diff'],float(np.max(abs(jj-s['jacobian']))))
                assert s['accepted']==bool(max(abs(grad))<=c['linear']['normal_equation_inf_tolerance'] if stage=='LINEAR' else s['scipy_success'] and max(abs(grad))<=c['acceptance']['physical_gradient_inf_max'])
            for kind,stage in [('nonlinear','P1'),('truth_linearized','LINEAR')]:
                s=results[m][stage];i=len(rows);usable=bool(s and s['usable_estimate']);row=dict(**item['condition'],unit=item['id'],seed=item['seed'],method=m,model=kind,completed=s is not None,usable=usable,accepted=s['accepted'] if s else False,category=s['category'] if s else 'NOT_COMPLETED',P0_category=results[m]['P0']['category'] if results[m]['P0'] else 'NOT_COMPLETED',cost=s['cost'] if s else None,gradient_inf=s['gradient_inf'] if s else None,warnings=len(s['warnings']) if s else 0,mse1=None,mse2=None,rmse1=None,rmse2=None,bias_error=None,rank=None)
                if usable:
                    x=np.array(s['estimate']);xr,r0,j0,a0,mu=lin;er=x-xr;err[i]=er[:24].reshape(12,2);jj=j0 if kind=='truth_linearized' else objective(u,m,x)[1];a=algebra(jj,m,c,item['condition']['mechanism']);row['rank']=a['rank']
                    for car in [1,2]:row[f'mse{car}']=float(np.mean(np.sum(err[i,car-1::2]**2,axis=-1)));row[f'rmse{car}']=np.sqrt(row[f'mse{car}'])
                    if m=='B2':be[i]=er[-1];row['bias_error']=float(er[-1])
                    if mu is not None:means[i]=mu[:24].reshape(12,2);cn=a0['mechanism_noise'];predvar[i]=[[cn[2*k,2*k],cn[2*k,2*k+1],cn[2*k+1,2*k+1]] for k in range(12)]
                    for v,name in enumerate(c['coverage']['views']):
                        cc=a[name]
                        for k in range(12):
                            block=None if cc is None else cc[2*k:2*k+2,2*k:2*k+2];z=ellipse(block,err[i,k],c);reasons[i,v,k]=a['status'] if cc is None else z['reason']
                            if block is not None:cov[i,v,k]=[block[0,0],block[0,1],block[1,1]]
                            if z['q'] is not None:q[i,v,k]=z['q'];eigen[i,v,k]=z['eigenvalues']
                        if m=='B2' and cc is not None and cc[-1,-1]>0:bv[i,v]=cc[-1,-1];bq[i,v]=er[-1]**2/cc[-1,-1]
                rows.append(row)
        if len(seen)%300==0:print('readback',len(seen),flush=True)
    assert seen=={x['id'] for x in meta['plan']} and len(rows)==n
    assert checks['max_residual_diff']<1e-9 and checks['max_jacobian_diff']<1e-9 and checks['max_gradient_diff']<1e-8 and checks['max_metric_diff']<1e-10
    checks.update(passed=True,planned_methods_each=n//2,completed=dict(collections.Counter(r['model'] for r in rows if r['completed'])),categories={kind:dict(collections.Counter(r['category'] for r in rows if r['model']==kind)) for kind in ['nonlinear','truth_linearized']})
    csvsave(out/'PER_RUN.csv',rows);csvsave(out/'FAILURES.csv',[r for r in rows if not r['accepted']]);save(out/'ROWS.json.gz',rows);save(out/'CHECKS.json',checks);save(out/'ANALYTIC_REFERENCES.json.gz',references);np.savez_compressed(out/'METRICS.npz',error=err,q=q,covariance=cov,eigen=eigen,bias_q=bq,bias_variance=bv,bias_error=be,reasons=reasons,analytic_mean=means,analytic_noise=predvar);return checks
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--portable',action='store_true');a=p.parse_args();print(audit(a.run,a.out,a.portable))
