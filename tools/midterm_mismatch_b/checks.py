"""Exposed-seed regressions and artificial failures. Never formal seeds."""
import argparse,copy,shutil,time
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from scipy.optimize import least_squares
from io_utils import read,save,digest
from adapter import config,conditions,generate,injection,solver_problem,solve,V
from run import run
from readback import raw,portable_check,objective
from analyze import analyze

def boom(*a,**kw):raise RuntimeError('INTENTIONAL_EXCEPTION')
def nonfinite(fun,x,**kw):return SimpleNamespace(x=np.full_like(x,np.nan),status=2,success=True,message='INTENTIONAL_NONFINITE',nfev=1,njev=1)
def budget(fun,x,**kw):kw['max_nfev']=1;return least_squares(fun,x,**kw)
def main(out):
    out.mkdir(parents=True,exist_ok=False);c=config();start=time.perf_counter();checks=dict(formal_runs=0,development_seed=26011601,inputs_checked=0,regression_stages=0,max_objective_difference=0.,max_endpoint_difference=0.,max_oracle_difference=0.,max_independent_jacobian_difference=0.)
    run(out/'panel',c,'development',workers=2)
    for q in conditions(c):
        u=read(out/'panel/inputs'/f"{q['id']}-s26011601.json.gz");checks['inputs_checked']+=1;link=c['links'][q['candidate']];inj=np.array(u['injection']);seq=c['injection_sequences_m'][q['injection']]
        assert np.array_equal(inj[link['indices']],seq['candidate']) and np.array_equal(inj[link['other_indices']],seq['other'])
        assert len(u['actual_faults'])==np.count_nonzero(inj)
        checks['max_oracle_difference']=max(checks['max_oracle_difference'],float(np.max(abs(np.array(u['obs']['ranges'])-inj-u['no_fault_ranges']))))
        for m in c['methods']:
            f,x,receipt=solver_problem(c,u['obs'],m,inj if m=='B3_full_oracle' else None);r,j=f(x);rr,jj=objective(u,m,x);checks['max_independent_jacobian_difference']=max(checks['max_independent_jacobian_difference'],float(np.max(abs(j-jj))));assert np.allclose(r,rr,atol=1e-12,rtol=0)
            if m=='B0':
                changed=copy.deepcopy(u['obs']);changed['ranges'][8]+=123.;f2,x2,receipt2=solver_problem(c,changed,m);assert receipt==receipt2 and np.array_equal(f(x)[0],f2(x2)[0])
            if m=='B2':
                # Only obs is solver-consumed; poisoned true fault metadata never reaches it.
                poison=copy.deepcopy(u);poison['injection']=[987.]*54;poison['actual_faults']=[]
                f2,x2,r2=solver_problem(c,poison['obs'],m);assert receipt==r2 and np.array_equal(f(x)[0],f2(x2)[0])
            if q['injection'] in ['zero','constant']:
                oldq=dict(id=q['id'],geometry=q['geometry'],motion=q['motion'],kind=q['candidate'],bias_m=0. if q['injection']=='zero' else .3,prior='survey_core');old=V.generate(c,oldq,26011601);assert old['obs']==u['obs'];oldm='B3' if m=='B3_full_oracle' else m
                of,ox,_=V.objective(c,old['obs'],oldm,np.array(old['oracle']) if oldm=='B3' else None);checks['max_objective_difference']=max(checks['max_objective_difference'],float(max(abs(r-of(ox)[0]))),float(np.max(abs(j-of(ox)[1]))))
                prev=None
                for stage in ['P0','P1']:
                    rec=V.solve_stage(c,old,oldm,stage,prev);prev=rec;actual=read(out/'panel/stages'/f"{q['id']}-s26011601"/f'{m}-{stage}.json.gz')['result'];checks['max_endpoint_difference']=max(checks['max_endpoint_difference'],float(max(abs(np.array(rec['estimate'])-actual['estimate']))));checks['regression_stages']+=1
    ck=raw(out/'panel',out/'panel_readback');assert ck['passed'];assert portable_check(out/'panel_readback',out/'panel_portable.json')['passed'];analyze(out/'panel_readback',out/'panel_analysis')
    failures={}
    for label,fault in [('exception',boom),('nonfinite',nonfinite),('budget',budget),('B0_exception',None)]:
        def pick(m,s):return boom if fault is None and m=='B0' else least_squares if fault is None else fault
        run(out/label,c,'development',ids=['m00'],workers=1,override=pick);r=raw(out/label,out/(label+'_readback'));assert r['passed'];analyze(out/(label+'_readback'),out/(label+'_analysis'));rows=read(out/(label+'_readback')/'ROWS.json.gz')
        if label in ['exception','nonfinite']:assert all(x['D1'] is None and x['mse1'] is None and not x['usable'] for x in rows)
        if label=='B0_exception':assert all(x['D1'] is None for x in rows) and rows[2]['B2_B1_1'] is not None
        before={str(p):p.read_bytes() for p in (out/label).rglob('*.gz')};assert run(out/label,c,'development',resume=True,workers=1)['new_stages']==0;assert all(Path(p).read_bytes()==b for p,b in before.items());failures[label]=r
    try:run(out/'interrupted',c,'development',ids=['m00'],workers=1,stop_after=1)
    except KeyboardInterrupt:pass
    before={str(p):p.read_bytes() for p in (out/'interrupted').rglob('*.gz')};assert run(out/'interrupted',c,'development',resume=True,workers=1)['new_stages']==7;assert all(Path(p).read_bytes()==b for p,b in before.items())
    try:run(out/'panel',c,'development',workers=1)
    except FileExistsError:pass
    else:raise AssertionError('overwrite accepted')
    # Separate copied fixture, not editing or deleting actual development evidence.
    shutil.copytree(out/'interrupted',out/'missing_fixture');(out/'missing_fixture/stages/m00-s26011601/B2-P1.json.gz').unlink();mc=raw(out/'missing_fixture',out/'missing_readback');assert mc['missing_stages']==1;analyze(out/'missing_readback',out/'missing_analysis')
    checks.update(artificial_failures=failures,missing_stage_recorded=True,resume_only_missing=True,overwrite_rejected=True,readback=ck,elapsed_s=time.perf_counter()-start,development_stage_bytes=sum(p.stat().st_size for p in (out/'panel/stages').rglob('*.gz')))
    assert checks['max_objective_difference']==0 and checks['max_endpoint_difference']==0 and checks['max_oracle_difference']<1e-12 and checks['max_independent_jacobian_difference']==0
    checks['passed']=True;save(out/'CHECKS.json',checks);print(checks)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.out)
