"""Exclusive durable stage files, exact resume, seed-level paired analysis and readback."""
import argparse
import collections
import contextlib
import fcntl
import gzip
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import numpy as np
import scipy
from core import ROOT,DOC,blank,canonical,clean,conditions,digest,evaluate,generate,independent_residual,load_config,solve_stage

def read(path):
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data)

def exclusive(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True);data=canonical(obj)
    if path.suffix=='.gz':data=gzip.compress(data,mtime=0)
    fd,tmp=tempfile.mkstemp(prefix='.pending-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.link(tmp,path)  # no replacement: FileExistsError is intentional
        dfd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(dfd)
        finally:os.close(dfd)
    finally:os.unlink(tmp)

def versions():return dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def source_hashes():
    import hashlib
    paths=sorted((ROOT/'tools/midterm_simulation_validation').glob('*.py'))+[ROOT/'tools/midterm_simulation_s2/prototype.py',ROOT/'tools/midterm_simulation_phase1/identifiability.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

def verify_freeze():
    import hashlib
    manifest=read(DOC/'FREEZE_MANIFEST.json')
    for name,value in manifest['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=value:raise ValueError('Freeze hash mismatch: '+name)
    return manifest

def provenance(c,mode,freeze):
    head=git('rev-parse','HEAD')
    if mode=='formal':
        verify_freeze()
        if freeze!=head:raise ValueError('--frozen-commit must equal full checkout HEAD')
        if git('status','--porcelain','--untracked-files=no'):raise ValueError('Formal checkout must be clean')
        if digest(c)!=digest(load_config()):raise ValueError('Formal config must equal frozen CONFIG.json')
        dep=c['required_dependencies'];v=versions()
        if not v['python'].startswith(dep['python_major_minor']+'.') or v['numpy']!=dep['numpy'] or v['scipy']!=dep['scipy']:raise ValueError('Frozen dependency mismatch')
    return dict(frozen_commit=head,source_sha256=source_hashes(),dependencies=versions())

def plan(c,mode,subset=None):
    cs=conditions(c)
    if mode=='formal':
        expected=c['expected']
        if len(cs)!=expected['conditions'] or len(c['seeds']['formal'])!=expected['formal_seeds'] or len(cs)*len(c['seeds']['formal'])!=expected['formal_paired_units'] or len(cs)*len(c['seeds']['formal'])*len(c['methods'])!=expected['formal_method_runs']:raise ValueError('Frozen matrix cardinality mismatch')
    if subset is not None:
        if mode=='formal':raise ValueError('No condition filtering in formal mode')
        cs=[x for x in cs if x['id'] in subset]
    return [dict(id=f"{q['id']}-s{seed}",condition=q,seed=seed) for q in cs for seed in c['seeds'][mode]]

def event(out,name,**details):
    with (out/'events.jsonl').open('a') as f:
        f.write(canonical(dict(event=name,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**details)).decode()+'\n');f.flush();os.fsync(f.fileno())

def stagepath(out,uid,method,stage):return out/'stages'/uid/f'{method}-{stage}.json.gz'

def run(out,c,mode,freeze=None,resume=False,subset=None,solver_override=None,stop_after=None):
    """solver_override/stop_after are only used by separate artificial checks, not CLI."""
    out=Path(out)
    if not resume:out.mkdir(parents=True,exist_ok=False)
    if not out.is_dir():raise ValueError('Resume directory missing')
    with (out/'run.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        current=provenance(c,mode,freeze)
        if resume:
            meta=read(out/'RUN.json')
            if meta['config_sha256']!=digest(c) or meta['mode']!=mode:raise ValueError('Resume config/mode mismatch')
            for key in ['frozen_commit','source_sha256','dependencies']:
                if current[key]!=meta[key]:raise ValueError('Resume provenance changed: '+key)
            expected=meta['plan'];event(out,'RESUME',policy='only absent durable stages; failures are complete')
        else:
            expected=plan(c,mode,subset)
            meta=dict(schema_version=1,mode=mode,config=c,config_sha256=digest(c),plan=expected,plan_sha256=digest(expected),**current)
            exclusive(out/'RUN.json',meta);event(out,'RUN_CREATED',planned_methods=len(expected)*len(c['methods']))
        attempts=collections.Counter()
        for line in (out/'events.jsonl').read_text().splitlines():
            e=json.loads(line)
            if e['event']=='STAGE_STARTED':attempts[(e['unit'],e['method'],e['stage'])]+=1
        made=0
        try:
            for item in expected:
                ip=out/'inputs'/f"{item['id']}.json.gz"
                if ip.exists():unit=read(ip)
                else:
                    if any(stagepath(out,item['id'],m,s).exists() for m in c['methods'] for s in ['P0','P1']):raise ValueError('Missing input for existing stages; do not regenerate corrupted run')
                    try:unit=generate(c,item['condition'],item['seed'])
                    except Exception as exc:unit=dict(condition=item['condition'],seed=item['seed'],generation_exception=repr(exc))
                    exclusive(ip,unit)
                for method in c['methods']:
                    if stagepath(out,item['id'],method,'P1').exists() and not stagepath(out,item['id'],method,'P0').exists():raise ValueError('P1 exists without P0; inconsistent run')
                    previous=None
                    for stage in ['P0','P1']:
                        path=stagepath(out,item['id'],method,stage)
                        if path.exists():
                            saved=read(path)
                            if saved['unit']!=item['id'] or saved['method']!=method or saved['stage']!=stage or saved['config_sha256']!=meta['config_sha256'] or saved['input_record_sha256']!=digest(unit):raise ValueError('Existing stage provenance mismatch')
                            previous=saved['result'];continue
                        attempt=attempts[item['id'],method,stage]+1
                        event(out,'STAGE_STARTED',unit=item['id'],method=method,stage=stage,attempt=attempt,retry_reason='interrupted_before_durable_record' if attempt>1 else None)
                        if 'generation_exception' in unit:
                            result=blank(stage);result.update(execution='EXCEPTION' if stage=='P0' else 'SKIPPED',category='INPUT_EXCEPTION' if stage=='P0' else 'SKIPPED_INVALID_P0',exception=unit['generation_exception'])
                        else:
                            kwargs={}
                            if solver_override is not None:kwargs['solver']=solver_override(item,method,stage)
                            result=solve_stage(c,unit,method,stage,previous,**kwargs)
                        exclusive(path,dict(unit=item['id'],method=method,stage=stage,attempt=attempt,config_sha256=meta['config_sha256'],input_record_sha256=digest(unit),result=result))
                        previous=result;made+=1;event(out,'STAGE_COMPLETED',unit=item['id'],method=method,stage=stage,category=result['category'])
                        if stop_after is not None and made>=stop_after:raise KeyboardInterrupt('intentional interruption check')
            event(out,'RUN_COMPLETED',new_stages=made)
        except BaseException as exc:
            event(out,'INTERRUPTED',reason=repr(exc),new_stages=made);raise
    return dict(new_stages=made,planned_methods=len(expected)*len(c['methods']))

def bootstrap(values,planned,c,complete=True):
    s=c['statistics'];n=len(values);out=dict(planned_seeds=planned,valid_seeds=n,missing_seeds=planned-n,mean=float(np.mean(values)) if n else None,ci95=None,ci_status=None,estimand='mean on available paired seeds; conditional if any missing')
    if not complete:out['ci_status']='RUN_INCOMPLETE'
    elif n<s['minimum_valid_seeds']:out['ci_status']='INSUFFICIENT_VALID_SEEDS'
    elif (planned-n)/planned>s['maximum_missing_fraction_for_ci']:out['ci_status']='MISSING_EXCEEDS_LIMIT'
    else:
        rng=np.random.Generator(np.random.PCG64(s['bootstrap_seed']))
        means=np.mean(np.array(values)[rng.integers(0,n,size=(s['bootstrap_repetitions'],n))],axis=1)
        alpha=(1-s['confidence'])/2;out['ci95']=np.quantile(means,[alpha,1-alpha]).tolist();out['ci_status']='POINTWISE_CONDITIONAL' if n<planned else 'POINTWISE_COMPLETE'
    return out

def collect(out):
    meta=read(out/'RUN.json');rows=[];c=meta['config']
    for item in meta['plan']:
        group={}
        for method in c['methods']:
            stages={s:read(stagepath(out,item['id'],method,s))['result'] if stagepath(out,item['id'],method,s).exists() else None for s in ['P0','P1']}
            final=stages['P1'];row=dict(unit=item['id'],condition=item['condition'],seed=item['seed'],method=method,completed=all(x is not None for x in stages.values()),category=final['category'] if final else 'NOT_COMPLETED',accepted=final['accepted'] if final else False,usable_estimate=final['usable_estimate'] if final else False,position_mse=final['position_mse'] if final else [None,None],position_rmse=final['position_rmse'] if final else [None,None],position_error_exceeds=final['position_error_exceeds'] if final else None,position_error_exceeds_by_car=final['position_error_exceeds_by_car'] if final else [None,None],total_nfev=sum((x['nfev'] or 0) for x in stages.values() if x),total_elapsed_s=sum(x['elapsed_s'] for x in stages.values() if x),bias_error=final['bias_error'] if final else None,bias_error_exceeds=final['bias_error_exceeds'] if final else None,P0_category=stages['P0']['category'] if stages['P0'] else None,D=[None,None],D_both_accepted=[None,None],B2_minus_B1=[None,None],B2_minus_B1_both_accepted=[None,None],stages=stages)
            group[method]=row;rows.append(row)
        for method,row in group.items():
            b0=group['B0']
            if row['usable_estimate'] and b0['usable_estimate']:
                row['D']=[a-b for a,b in zip(row['position_mse'],b0['position_mse'])]
                if row['accepted'] and b0['accepted']:row['D_both_accepted']=row['D'][:]
            if method=='B2' and row['usable_estimate'] and group['B1']['usable_estimate']:
                row['B2_minus_B1']=[a-b for a,b in zip(row['position_mse'],group['B1']['position_mse'])]
                if row['accepted'] and group['B1']['accepted']:row['B2_minus_B1_both_accepted']=row['B2_minus_B1'][:]
    return meta,rows

def summarize(out):
    meta,rows=collect(out);c=meta['config'];groups=[]
    for cid in dict.fromkeys(x['condition']['id'] for x in rows):
        for method in c['methods']:
            rs=sorted([r for r in rows if r['condition']['id']==cid and r['method']==method],key=lambda x:x['seed']);n=len(rs)
            g=dict(condition=rs[0]['condition'],method=method,planned=n,completed=sum(r['completed'] for r in rs),valid_error_count=sum(r['usable_estimate'] for r in rs),accepted=sum(r['accepted'] for r in rs),numerical_failures=sum(r['completed'] and not r['accepted'] for r in rs),not_completed=sum(not r['completed'] for r in rs),categories=dict(collections.Counter(r['category'] for r in rs)),P0_categories=dict(collections.Counter(r['P0_category'] for r in rs)),position_error_valid=sum(r['position_error_exceeds'] is not None for r in rs),position_error_exceeds=sum(r['position_error_exceeds'] is True for r in rs),position_error_exceeds_by_car=[sum(r['position_error_exceeds_by_car'][i] is True for r in rs) for i in [0,1]],bias_error_valid=sum(r['bias_error'] is not None for r in rs),bias_error_exceeds=sum(r['bias_error_exceeds'] is True for r in rs),metrics={})
            complete=all(r['completed'] for r in rs)
            for field in ['position_mse','position_rmse','D','D_both_accepted','B2_minus_B1','B2_minus_B1_both_accepted']:
                if field.startswith('B2_') and method!='B2':continue
                for car in [0,1]:g['metrics'][f'{field}_car{car+1}']=bootstrap([r[field][car] for r in rs if r[field][car] is not None],n,c,complete)
            if method=='B2':g['metrics']['bias_error']=bootstrap([r['bias_error'] for r in rs if r['bias_error'] is not None],n,c,complete)
            groups.append(g)
    return dict(config_sha256=meta['config_sha256'],planned_methods=len(rows),completed_methods=sum(r['completed'] for r in rows),independent_seeds=len(set(r['seed'] for r in rows)),formal_method_records=sum(r['completed'] for r in rows) if meta['mode']=='formal' else 0,groups=groups,interpretation='No superiority inference from success subsets; pointwise intervals, no rare-risk/real-vehicle/protection-level guarantee',rows=rows)

def verify(out):
    meta,rows=collect(out);c=meta['config'];tol=c['verification'];checks=dict(planned_methods=len(rows),stage_records=0,recomputed_states=0,unavailable_states=0,missing_stages=0,max_residual_difference=0.,max_gradient_difference=0.,max_scalar_difference=0.,errors=[])
    if source_hashes()!=meta['source_sha256']:checks['errors'].append('source SHA mismatch')
    if versions()!=meta['dependencies']:checks['errors'].append('dependency mismatch')
    if meta['mode']=='formal' and git('rev-parse','HEAD')!=meta['frozen_commit']:checks['errors'].append('formal frozen commit mismatch')
    if digest(c)!=meta['config_sha256'] or digest(meta['plan'])!=meta['plan_sha256']:raise ValueError('Run metadata hash mismatch')
    for row in rows:
        unit=read(out/'inputs'/f"{row['unit']}.json.gz") if (out/'inputs'/f"{row['unit']}.json.gz").exists() else None
        if unit is not None and 'obs' in unit and digest(unit['obs'])!=unit['input_sha256']:checks['errors'].append('input hash '+row['unit'])
        for stage,result in row['stages'].items():
            if result is None:checks['missing_stages']+=1;continue
            checks['stage_records']+=1;stored=read(stagepath(out,row['unit'],row['method'],stage))
            if stored['config_sha256']!=meta['config_sha256'] or stored['input_record_sha256']!=digest(unit):checks['errors'].append('stage provenance '+row['unit'])
            if result['usable_estimate']:
                # Failure is permitted: only usable stored states can be evaluated.
                try:
                    repeated=evaluate(c,unit,row['method'],stage,result['estimate'],result)
                    for field in ['position_mse','position_rmse','bias_error','cost','gradient_inf','scaled_gradient_inf']:
                        a=result[field];b=repeated[field]
                        if a is None or b is None:
                            if a!=b:checks['errors'].append('null mismatch '+field)
                        else:
                            diff=float(np.max(np.abs(np.asarray(a)-np.asarray(b))));checks['max_scalar_difference']=max(checks['max_scalar_difference'],diff)
                    if result['endpoint_valid']:
                        rr=independent_residual(unit,row['method'],np.array(result['estimate']));diff=float(np.max(np.abs(rr-np.array(result['residual']))));checks['max_residual_difference']=max(checks['max_residual_difference'],diff)
                        gg=np.array(result['jacobian']).T@rr;gd=float(np.max(np.abs(gg-np.array(result['gradient']))));checks['max_gradient_difference']=max(checks['max_gradient_difference'],gd)
                    checks['recomputed_states']+=1
                except Exception as exc:checks['errors'].append('readback '+repr(exc))
            else:
                checks['unavailable_states']+=1
                if any(x is not None for x in result['position_mse']+result['position_rmse']) or result['bias_error'] is not None:checks['errors'].append('unavailable state has errors')
            expected=bool(result['endpoint_valid'] and result['scipy_success'] and result['gradient_inf'] is not None and result['gradient_inf']<=c['acceptance']['physical_gradient_inf_max'])
            if result['accepted']!=expected:checks['errors'].append('acceptance mismatch')
            if stage=='P1' and row['stages']['P0'] is not None and not row['stages']['P0']['endpoint_valid'] and result['category']!='SKIPPED_INVALID_P0':checks['errors'].append('invalid continuation')
            cov=result['information']['covariance']
            if result['information']['status']!='FINITE_LOCAL_INVERSE' and cov is not None:checks['errors'].append('uncertainty status/covariance mismatch')
            if cov is not None and not np.all(np.isfinite(np.array(cov))):checks['errors'].append('nonfinite covariance serialized as finite')
    for key,limit in [('max_residual_difference',tol['residual_absolute_tolerance']),('max_gradient_difference',tol['gradient_absolute_tolerance']),('max_scalar_difference',tol['scalar_absolute_tolerance'])]:
        if checks[key]>limit:checks['errors'].append(key+' exceeds tolerance')
    checks['passed']=not checks['errors'];return checks

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    for name in ['run','resume']:
        a=sub.add_parser(name);a.add_argument('--out',required=True,type=Path);a.add_argument('--config',type=Path,default=DOC/'CONFIG.json');a.add_argument('--mode',choices=['development','formal'],required=True);a.add_argument('--frozen-commit');a.add_argument('--conditions',nargs='+')
    for name in ['summarize','verify']:
        a=sub.add_parser(name);a.add_argument('--out',required=True,type=Path);a.add_argument('--save',type=Path)
    args=p.parse_args()
    if args.command in ['run','resume']:
        c=load_config(args.config);result=run(args.out,c,args.mode,args.frozen_commit,args.command=='resume',args.conditions)
    elif args.command=='summarize':result=summarize(args.out)
    else:result=verify(args.out)
    if getattr(args,'save',None):exclusive(args.save,result);print(json.dumps(dict(saved=str(args.save),passed=result.get('passed')),ensure_ascii=False))
    else:print(json.dumps(clean(result),ensure_ascii=False,indent=2,allow_nan=False))
    if args.command=='verify' and not result['passed']:raise SystemExit(1)
if __name__=='__main__':main()
