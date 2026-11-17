"""Independent vectorized math, streaming audit/portable packing. NO optimizer imports."""
import argparse,collections,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
from io_utils import read,save,csvsave,canonical,digest,interval

def objective(u,method,x):
    o=u['obs'];p=x[:24].reshape(6,2,2);a=np.array(o['anchors']);n=len(x)
    d=p[:,:,None,:]-a;dist=np.sqrt(np.sum(d*d,axis=-1));dp=p[:,1]-p[:,0];peer=np.sqrt(np.sum(dp*dp,axis=-1));v=np.column_stack([dist.reshape(6,8),peer]);j=np.zeros((6,9,n))
    for t in range(6):
        for car in range(2):j[t,car*4:car*4+4,4*t+2*car:4*t+2*car+2]=d[t,car]/dist[t,car,:,None]
        j[t,8,4*t:4*t+2]=-dp[t]/peer[t];j[t,8,4*t+2:4*t+4]=dp[t]/peer[t]
    if method=='B2':
        col=0 if o['kind']=='wall' else 8;v[:,col]+=x[-1];j[:,col,-1]=1
    y=np.array(o['ranges']).reshape(6,9)
    if method=='B3_full_oracle':y=y-np.array(u['injection']).reshape(6,9)
    k=8 if method=='B0' else 9;r=[((v-y)/o['range_sigma'])[:,:k].ravel()];js=[j[:,:k].reshape(-1,n)/o['range_sigma']]
    mj=np.zeros((20,n))
    for i in range(20):mj[i,i]=-1;mj[i,i+4]=1
    r.append((np.diff(p.reshape(6,4),axis=0).ravel()-o['movement'])/o['motion_sigma']);js.append(mj/o['motion_sigma'])
    if o['prior_sigma'] is not None:
        r.append((x[:4]-o['prior_center'])/o['prior_sigma']);pj=np.zeros((4,n));pj[:,:4]=np.eye(4);js.append(pj/o['prior_sigma'])
    return np.concatenate(r),np.vstack(js)

def check_input(u,c):
    q=u['condition'];o=u['obs'];assert digest(o)==u['input_sha256']
    p=np.array(u['truth']);a=np.array(o['anchors']);clean=np.column_stack([np.linalg.norm(p[:,:,None,:]-a,axis=-1).reshape(6,8),np.linalg.norm(p[:,1]-p[:,0],axis=-1)]).ravel()
    expected=np.zeros((6,9));seq=c['injection_sequences_m'][q['injection']];link=c['links'][q['candidate']]
    expected[:,link['row_within_epoch']]=seq['candidate'];expected[:,link['other_row_within_epoch']]=seq['other'];inj=expected.ravel()
    assert np.array_equal(inj,u['injection'])
    assert [x['index'] for x in u['actual_faults']]==np.flatnonzero(inj).tolist()
    assert np.max(np.abs(clean+np.array(u['noise']['range'])-u['no_fault_ranges']))<1e-12
    assert np.max(np.abs(np.array(o['ranges'])-inj-u['no_fault_ranges']))<1e-12
    assert np.max(np.abs(np.diff(p.reshape(6,4),axis=0).ravel()+u['noise']['motion']-np.array(o['movement'])))<1e-12
    survey=np.array(c['geometries'][q['geometry']]['survey']);start=np.vstack([survey,survey+np.cumsum(np.array(o['movement']).reshape(5,4),axis=0)]).ravel()
    assert np.array_equal(start,o['start']) and np.array_equal(survey,o['prior_center']) and o['prior_sigma']==.5

def audit_stage(u,m,r,c,checks,full):
    checks['stage_records']+=1
    if not r['usable_estimate']:
        assert r['position_mse']==[None,None] and r['position_rmse']==[None,None];checks['unavailable_states']+=1;return
    x=np.array(r['estimate']);err=x[:24].reshape(6,2,2)-u['truth'];mse=np.mean(np.sum(err**2,axis=-1),axis=0)
    checks['max_metric_diff']=max(checks['max_metric_diff'],float(np.max(np.abs(mse-r['position_mse']))));assert np.allclose(mse,r['position_mse'],rtol=0,atol=1e-12)
    assert r['position_error_exceeds_by_car']==(np.sqrt(mse)>c['statistics']['position_rmse_threshold_m']).tolist()
    if r['endpoint_valid']:
        rr,j=objective(u,m,x);g=j.T@rr;scale=np.r_[np.full(24,c['solver']['position_scale_m']),c['solver']['bias_scale_m']] if m=='B2' else np.full(24,c['solver']['position_scale_m'])
        checks['max_cost_diff']=max(checks['max_cost_diff'],abs(float(rr@rr/2)-r['cost']));checks['max_gradient_diff']=max(checks['max_gradient_diff'],abs(float(np.max(abs(g)))-r['gradient_inf']))
        if full:
            checks['max_residual_diff']=max(checks['max_residual_diff'],float(np.max(abs(rr-r['residual']))));checks['max_jacobian_diff']=max(checks['max_jacobian_diff'],float(np.max(abs(j-r['jacobian']))));checks['max_gradient_vector_diff']=max(checks['max_gradient_vector_diff'],float(np.max(abs(g-r['gradient']))));assert np.allclose(g*scale,r['scaled_gradient'],atol=1e-9,rtol=0)
        assert r['accepted']==bool(r['scipy_success'] and max(abs(g))<=c['acceptance']['physical_gradient_inf_max'])
    if m=='B2':
        link=c['links'][u['condition']['candidate']];b=x[-1];inj=np.array(u['injection']);mean=float(inj[link['indices']].mean());mask=np.zeros(54);mask[link['indices']]=1;rem=inj-b*mask
        assert abs(r['candidate_injection_mean_m']-mean)<1e-12 and abs(r['unabsorbed_injection_rms_m']-np.sqrt(np.mean(rem**2)))<1e-12
        if u['condition']['injection'] in ['zero','constant']:assert abs(r['bias_error']-(b-mean))<1e-12
        else:assert r['bias_error'] is None and r['bias_error_exceeds'] is None
    checks['recomputed_states']+=1

def newchecks():return dict(inputs=0,stage_records=0,recomputed_states=0,unavailable_states=0,missing_stages=0,max_metric_diff=0.,max_cost_diff=0.,max_gradient_diff=0.,max_residual_diff=0.,max_jacobian_diff=0.,max_gradient_vector_diff=0.,optimizer_calls=0)
def finishchecks(ck,c):
    assert ck['max_cost_diff']<1e-10 and ck['max_gradient_diff']<1e-9 and ck['max_residual_diff']<1e-10 and ck['max_jacobian_diff']<1e-10 and ck['max_gradient_vector_diff']<1e-9
    ck['passed']=True;return ck

def raw(run,out):
    out.mkdir(parents=True,exist_ok=False);meta=read(run/'RUN.json');c=meta['config'];assert digest(c)==meta['config_sha256'] and digest(meta['plan'])==meta['plan_sha256'];save(out/'RUN.json',meta)
    ck=newchecks();rows=[];hashes={};counts=collections.Counter();missing=[];portable=None
    for i,item in enumerate(meta['plan']):
        if i%900==0:
            if portable:portable.close()
            portable=gzip.open(out/f'EVIDENCE-{i//900:03}.jsonl.gz','xb');portable.write(canonical(dict(type='RUN',value=meta))+b'\n')
        ip=run/'inputs'/f"{item['id']}.json.gz"
        if not ip.exists():missing.append(dict(unit=item['id'],missing='input'));continue
        u=read(ip);hashes[str(ip.relative_to(run))]=hashlib.sha256(ip.read_bytes()).hexdigest()
        if 'generation_exception' not in u:check_input(u,c)
        ck['inputs']+=1;portable.write(canonical(dict(type='INPUT',value=u))+b'\n')
        group={}
        for m in c['methods']:
            stages={}
            for stage in ['P0','P1']:
                p=run/'stages'/item['id']/f'{m}-{stage}.json.gz'
                if not p.exists():ck['missing_stages']+=1;missing.append(dict(unit=item['id'],method=m,stage=stage));stages[stage]=None;continue
                obj=read(p);hashes[str(p.relative_to(run))]=hashlib.sha256(p.read_bytes()).hexdigest();r=obj['result'];assert obj['input_sha256']==digest(u) and obj['config_sha256']==meta['config_sha256'];audit_stage(u,m,r,c,ck,True);counts[stage+':'+r['category']]+=1
                if stage=='P1' and r['execution']=='SKIPPED':assert stages['P0'] is not None and not stages['P0']['endpoint_valid'] and r['residual_calls']==0
                stages[stage]={k:v for k,v in r.items() if k not in ['residual','jacobian','gradient','scaled_gradient','information']};stages[stage]['information']={k:v for k,v in r['information'].items() if k!='covariance'}
            portable.write(canonical(dict(type='METHOD',value=dict(unit=item['id'],method=m,input_sha256=digest(u),stages=stages)))+b'\n')
            f=stages['P1'];p0=stages['P0'];valid=f is not None and f['usable_estimate'];row={**item['condition'], 'unit':item['id'],'seed':item['seed'],'method':m,'completed':all(x is not None for x in stages.values()),'usable':bool(valid),'accepted':f['accepted'] if f else False,'category':f['category'] if f else 'NOT_COMPLETED','P0_category':p0['category'] if p0 else 'NOT_COMPLETED','cost':f['cost'] if f else None,'gradient_inf':f['gradient_inf'] if f else None,'scaled_gradient_inf':f['scaled_gradient_inf'] if f else None,'termination':f['termination'] if f else None,'nfev_total':sum((x['nfev'] or 0) for x in stages.values() if x),'elapsed_total_s':sum(x['elapsed_s'] for x in stages.values() if x),'warnings':sum(len(x['warnings']) for x in stages.values() if x),'bias_estimate':f['bias_estimate'] if f else None,'bias_error':f['bias_error'] if f else None,'bias_error_exceeds':f['bias_error_exceeds'] if f else None}
            for k in ['candidate_injection_mean_m','b_minus_candidate_mean_m','unabsorbed_injection_rms_m','unabsorbed_candidate_rms_m','unabsorbed_other_rms_m']:row[k]=f.get(k) if f else None
            for car in [1,2]:
                row[f'mse{car}']=f['position_mse'][car-1] if valid else None;row[f'rmse{car}']=f['position_rmse'][car-1] if valid else None;row[f'large{car}']=f['position_error_exceeds_by_car'][car-1] if valid else None
                row[f'D{car}']=None;row[f'D_accepted{car}']=None;row[f'B2_B1_{car}']=None;row[f'B2_B1_accepted{car}']=None
            row['residual_rms']=None;row['range_residual_rms_m']=None
            if valid and f['endpoint_valid']:
                rr,_=objective(u,m,np.array(f['estimate']));nr=48 if m=='B0' else 54;row['residual_rms']=float(np.sqrt(np.mean(rr**2)));row['range_residual_rms_m']=float(np.sqrt(np.mean((rr[:nr]*u['obs']['range_sigma'])**2)))
            group[m]=row;rows.append(row)
        for m,r in group.items():
            for car in [1,2]:
                if r['usable'] and group['B0']['usable']:
                    r[f'D{car}']=r[f'mse{car}']-group['B0'][f'mse{car}']
                    if r['accepted'] and group['B0']['accepted']:r[f'D_accepted{car}']=r[f'D{car}']
                if m=='B2' and r['usable'] and group['B1']['usable']:
                    r[f'B2_B1_{car}']=r[f'mse{car}']-group['B1'][f'mse{car}']
                    if r['accepted'] and group['B1']['accepted']:r[f'B2_B1_accepted{car}']=r[f'B2_B1_{car}']
        if (i+1)%500==0:print(f'readback {i+1}/{len(meta["plan"])}',flush=True)
    if portable:portable.close()
    for item in meta['plan']:
        # Missing inputs still receive all planned-method rows, no silent denominator loss.
        if not (run/'inputs'/f"{item['id']}.json.gz").exists():
            for m in c['methods']:
                r={k:None for k in rows[0]} if rows else {k:None for k in ['P0_category','cost','gradient_inf','scaled_gradient_inf','termination','nfev_total','elapsed_total_s','warnings','bias_estimate','bias_error','bias_error_exceeds','candidate_injection_mean_m','b_minus_candidate_mean_m','unabsorbed_injection_rms_m','unabsorbed_candidate_rms_m','unabsorbed_other_rms_m','mse1','mse2','rmse1','rmse2','large1','large2','D1','D2','D_accepted1','D_accepted2','B2_B1_1','B2_B1_2','B2_B1_accepted1','B2_B1_accepted2','residual_rms','range_residual_rms_m']};r.update(**item['condition'],unit=item['id'],seed=item['seed'],method=m,completed=False,usable=False,accepted=False,category='NOT_COMPLETED');rows.append(r)
    assert len(rows)==len(meta['plan'])*len(c['methods'])
    save(out/'RAW_SHA256.json.gz',hashes);save(out/'MISSING.json',missing);csvsave(out/'PER_RUN.csv',rows);csvsave(out/'FAILURES.csv',[r for r in rows if not r['accepted'] or r['large1'] or r['large2'] or r['bias_error_exceeds']]);csvsave(out/'NONACCEPTED.csv',[r for r in rows if not r['accepted']]);save(out/'ROWS.json.gz',rows)
    ck.update(stage_categories=dict(counts),planned_inputs=len(meta['plan']),planned_methods=len(rows),completed_methods=sum(r['completed'] for r in rows),valid_final=sum(r['usable'] for r in rows),accepted_final=sum(r['accepted'] for r in rows));save(out/'INDEPENDENT_CHECKS.json',finishchecks(ck,c));return ck

def portable_check(directory,out):
    ck=newchecks();seen_inputs=set();seen_methods=set()
    for p in sorted(directory.glob('EVIDENCE-*.jsonl.gz')):
        inputs={}
        with gzip.open(p,'rt') as f:
            for line in f:
                row=json.loads(line);v=row['value']
                if row['type']=='RUN':meta=v;c=v['config'];assert digest(c)==meta['config_sha256'];continue
                if row['type']=='INPUT':
                    key=v['condition']['id']+'-s'+str(v['seed']);assert key not in seen_inputs;seen_inputs.add(key);inputs[key]=v
                    if 'generation_exception' not in v:check_input(v,c)
                    ck['inputs']+=1;continue
                key=(v['unit'],v['method']);assert key not in seen_methods;seen_methods.add(key);u=inputs[v['unit']];assert digest(u)==v['input_sha256']
                for r in v['stages'].values():
                    if r is None:ck['missing_stages']+=1
                    else:audit_stage(u,v['method'],r,c,ck,False)
    assert len(seen_methods)<=len(meta['plan'])*len(c['methods']) and len(seen_inputs)<=len(meta['plan'])
    ck['missing_inputs']=len(meta['plan'])-len(seen_inputs);ck['missing_methods']=len(meta['plan'])*len(c['methods'])-len(seen_methods)
    ck['complete']=ck['missing_inputs']==0 and ck['missing_methods']==0 and ck['missing_stages']==0
    save(out,finishchecks(ck,c));return ck
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path);p.add_argument('--evidence',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(raw(a.run,a.out) if a.run else portable_check(a.evidence,a.out))
