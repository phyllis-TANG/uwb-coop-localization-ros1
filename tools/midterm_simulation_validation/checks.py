"""Artificial failures and exposed-input regression only; never uses formal seeds."""
import argparse
import copy
import gzip
import json
import time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.optimize import least_squares
from core import B,ROOT,conditions,digest,generate,information,load_config,objective,solve_stage
from pipeline import bootstrap,event,exclusive,read,run,source_hashes,summarize,verify

def boom(*args,**kwargs):raise RuntimeError('INTENTIONAL_EXCEPTION_CHECK')
def nonfinite(fun,start,**kwargs):return SimpleNamespace(x=np.full_like(start,np.nan),status=2,success=True,message='INTENTIONAL_NONFINITE_CHECK',nfev=1,njev=1)
def finite_not_stationary(fun,start,**kwargs):return SimpleNamespace(x=start,status=2,success=True,message='INTENTIONAL_FTOL_AT_START',nfev=1,njev=1)
def budget(fun,start,**kwargs):
    kwargs['max_nfev']=1
    return least_squares(fun,start,**kwargs)

def run_checks(out):
    out.mkdir(parents=True,exist_ok=False);c=load_config();results=dict(formal_runs=0,artificial_checks={},regression={},config_checks={},bootstrap_checks={},resume_checks={});start=time.perf_counter()
    # Each fixture has all four methods, one already-exposed development input.
    for label,fault in [('normal',least_squares),('exception',boom),('nonfinite',nonfinite),('budget',budget),('finite_not_stationary',finite_not_stationary),('P1_exception',boom),('P1_nonfinite',nonfinite),('B0_exception_other_methods_valid',None)]:
        path=out/label
        def choose(item,method,stage):
            if label.startswith('P1_') and stage=='P0':return least_squares
            return boom if fault is None and method=='B0' else least_squares if fault is None else fault
        run(path,c,'development',subset=['c00'],solver_override=choose)
        s=summarize(path);v=verify(path);exclusive(path/'summary.json.gz',s);exclusive(path/'verification.json',v)
        assert read(path/'summary.json.gz')['planned_methods']==4
        assert read(path/'summary.json.gz')['rows']==s['rows']
        assert v['passed'],v
        assert s['planned_methods']==s['completed_methods']==4
        rs=s['rows'];assert all(r['completed'] for r in rs)
        if label in ['exception','nonfinite']:
            assert all(not r['usable_estimate'] and r['position_mse']==[None,None] and r['D']==[None,None] and r['category']=='SKIPPED_INVALID_P0' for r in rs)
            assert all(g['valid_error_count']==0 and g['numerical_failures']==1 for g in s['groups'])
            assert v['recomputed_states']==0 and v['unavailable_states']==8
        if label.startswith('P1_'):
            assert all(not r['usable_estimate'] and r['position_mse']==[None,None] and r['D']==[None,None] for r in rs)
            assert v['recomputed_states']==4 and v['unavailable_states']==4
            assert all(r['category']==('EXCEPTION' if label=='P1_exception' else 'NONFINITE') for r in rs)
        if label=='budget':assert all(r['category']=='BUDGET_EXHAUSTED' and r['usable_estimate'] and not r['accepted'] for r in rs)
        if label=='finite_not_stationary':assert all(r['category']=='NOT_STATIONARY' and r['usable_estimate'] for r in rs)
        if fault is None:
            assert not rs[0]['usable_estimate'] and all(r['usable_estimate'] for r in rs[1:])
            assert all(r['D']==[None,None] for r in rs)
            assert rs[2]['B2_minus_B1'][0] is not None
        results['artificial_checks'][label]=dict(planned=s['planned_methods'],valid=sum(r['usable_estimate'] for r in rs),numerical_failures=sum(not r['accepted'] for r in rs),categories=[r['category'] for r in rs],readback=v)
    # Exact resume: a durable P0 survives interruption; second resume is a no-op.
    path=out/'interruption'
    try:run(path,c,'development',subset=['c00'],stop_after=1)
    except KeyboardInterrupt:pass
    existing={str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*.gz')}
    partial=summarize(path);assert partial['completed_methods']==0 and partial['planned_methods']==4
    event(path,'STAGE_STARTED',unit='c00-s26011601',method='B0',stage='P1',attempt=1,retry_reason=None)
    event(path,'INTERRUPTED',reason='simulate process lost before P1 durable record')
    got=run(path,c,'development',resume=True)
    assert read(path/'stages/c00-s26011601/B0-P1.json.gz')['attempt']==2
    assert got['new_stages']==7
    assert all((path/k).read_bytes()==v for k,v in existing.items())
    assert run(path,c,'development',resume=True)['new_stages']==0
    assert verify(path)['passed']
    try:run(path,c,'development',subset=['c00'])
    except FileExistsError:pass
    else:raise AssertionError('Existing output was overwritten')
    # Complete saved failures are not retried either.
    for name in ['exception','nonfinite','budget']:
        assert run(out/name,c,'development',resume=True)['new_stages']==0
    results['resume_checks']=dict(interrupted_after_stages=1,resumed_stages=got['new_stages'],unchanged_existing_files=True,second_resume_stages=0,failed_records_not_retried=True,overwrite_rejected=True)
    # A single old c00-like input, all four methods, exact P0/P1 comparison.
    v2=ROOT/'docs/research/midterm_simulation_s2_v2'
    old_units=json.loads(gzip.decompress((v2/'supplement_inputs.json.gz').read_bytes()))
    old_records=json.loads(gzip.decompress((v2/'supplement_results.json.gz').read_bytes()))
    original=next(u for u in old_units if u['geometry']=='good' and u['motion']=='static' and u['profile']=='survey_weak')
    condition=next(x for x in conditions(c) if x['panel']=='core' and x['geometry']=='good' and x['motion']=='static' and x['kind']=='peer' and x['bias_m']==.3)
    unit=generate(c,condition,26011601);assert unit['obs']==original['obs'];maxdiff=0.
    for method in c['methods']:
        previous=None
        for stage in ['P0','P1']:
            rec=solve_stage(c,unit,method,stage,previous);previous=rec
            old=next(x['result'] for x in old_records if x['unit']==original['id'] and x['method']==method and x['protocol']==stage)
            maxdiff=max(maxdiff,float(np.max(np.abs(np.array(rec['estimate'])-old['estimate']))))
            assert np.allclose(rec['residual'],old['residual'],atol=1e-12,rtol=0)
            exclusive(out/'regression'/f'{method}-{stage}.json.gz',rec)
        f,q,_=objective(c,unit['obs'],method,np.array(unit['oracle']) if method=='B3' else None)
        oldfun,oldq,_=B.problem(unit['obs'],method,np.array(unit['oracle']) if method=='B3' else None)
        assert np.array_equal(q,oldq) and all(np.array_equal(a,b) for a,b in zip(f(q),oldfun(q)))
    assert maxdiff==0.;results['regression']=dict(old_input_sha_equal=True,objective_residual_and_jacobian_exact=True,stages=8,max_state_difference=maxdiff)
    # Generation-only checks on exposed seed: no expanded performance panel.
    allunits=[generate(c,q,26011601) for q in conditions(c)]
    pairs=0
    for geo in c['geometries']:
        core=next(u for u in allunits if u['condition']['panel']=='core' and u['condition']['geometry']==geo and u['condition']['motion']=='static' and u['condition']['kind']=='peer' and u['condition']['bias_m']==.3)
        for panel,key in [('no_prior','prior_sigma'),('strong','prior_sigma')]:
            other=next(u for u in allunits if u['condition']['panel']==panel and u['condition']['geometry']==geo and u['condition']['motion']=='static')
            a=copy.deepcopy(core['obs']);b=copy.deepcopy(other['obs']);a.pop(key);b.pop(key);assert a==b;pairs+=1
        strong=next(u for u in allunits if u['condition']['panel']=='strong' and u['condition']['geometry']==geo)
        shifted=next(u for u in allunits if u['condition']['panel']=='shifted_strong' and u['condition']['geometry']==geo)
        a=copy.deepcopy(strong['obs']);b=copy.deepcopy(shifted['obs']);a.pop('prior_center');b.pop('prior_center');assert a==b;pairs+=1
    assert all(u['noise']==allunits[0]['noise'] for u in allunits)
    def changed(mut):
        cc=copy.deepcopy(c);mut(cc);return cc,generate(cc,condition,26011601)
    cc,u=changed(lambda x:x['noise'].update(range_sigma_m=.08));assert np.allclose(np.array(u['noise']['range']),2*np.array(unit['noise']['range'])) and u['obs']['range_sigma']==.08
    cc,u=changed(lambda x:x['priors'].update(core_sigma_m=.7));assert u['obs']['prior_sigma']==.7 and u['obs']['start']==unit['obs']['start']
    cc,u=changed(lambda x:x['geometries']['good']['anchors'][0].__setitem__(0,-.1));assert u['obs']['anchors']!=unit['obs']['anchors']
    cc=copy.deepcopy(c);cc['motions']['turn']['x_amplitude_m']=.7
    turn=next(q for q in conditions(c) if q['motion']=='turn');assert generate(cc,turn,26011601)['truth']!=generate(c,turn,26011601)['truth']
    cc,u=changed(lambda x:x['geometries']['good']['survey'].__setitem__(0,1.3));assert u['obs']['start']!=unit['obs']['start']
    cc=copy.deepcopy(c);cc['seeds']['development']=[26011602];assert generate(cc,condition,26011602)['noise']!=unit['noise']
    # Solver options are consumed from configuration (capture without optimizing).
    captured={}
    def spy(fun,start,**kw):captured.update(kw);return finite_not_stationary(fun,start,**kw)
    cc=copy.deepcopy(c);cc['solver']['P0']['max_nfev']=7;rec=solve_stage(cc,unit,'B2','P0',solver=spy);assert captured['max_nfev']==7
    cc['acceptance']['physical_gradient_inf_max']=rec['gradient_inf']*2;assert solve_stage(cc,unit,'B2','P0',solver=spy)['accepted']
    cc=copy.deepcopy(c);cc['statistics']['position_rmse_threshold_m']=0.;assert solve_stage(cc,unit,'B2','P0',solver=spy)['position_error_exceeds']
    ni=information(c,np.full((78,25),np.nan),'B2');assert ni['status']=='NONFINITE_INFORMATION' and ni['covariance'] is None
    singular=information(c,np.zeros((78,25)),'B2');assert singular['status']=='RANK_DEFICIENT' and singular['covariance'] is None
    # Finite J can still yield unrepresentable covariance; no fake inverse.
    tiny=information(c,np.eye(25)*1e-200,'B2');assert tiny['status']=='NONFINITE_COVARIANCE' and tiny['covariance'] is None
    results['config_checks']=dict(generation_only_development_conditions=len(allunits),controlled_pairs=pairs,shared_noise_all_conditions=True,noise_geometry_motion_survey_prior_seed_solver_acceptance_statistics_changes_effective=True,nonfinite_information=ni['status'],nonfinite_covariance=tiny['status'],rank_deficient_covariance_null=True)
    cc=copy.deepcopy(c);cc['statistics'].update(minimum_valid_seeds=2,bootstrap_repetitions=37,maximum_missing_fraction_for_ci=.25)
    a=bootstrap([1.,2.,3.],3,cc);assert a==bootstrap([1.,2.,3.],3,cc) and a['ci95'] is not None
    assert bootstrap([],3,cc)['ci95'] is None and bootstrap([1.],3,cc)['ci_status']=='INSUFFICIENT_VALID_SEEDS'
    assert bootstrap([1.,2.],5,cc)['ci_status']=='MISSING_EXCEEDS_LIMIT'
    assert bootstrap([1.,2.,3.],3,cc,False)['ci_status']=='RUN_INCOMPLETE'
    results['bootstrap_checks']=dict(deterministic=True,repetitions_from_config=37,empty_and_insufficient_null=True,missing_limit_enforced=True,unfinished_run_no_ci=True)
    results.update(passed=True,elapsed_s=time.perf_counter()-start,source_sha256=source_hashes())
    exclusive(out/'CHECKS.json',results);return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True,type=Path);a=p.parse_args();print(json.dumps(run_checks(a.out),indent=2,ensure_ascii=False))
