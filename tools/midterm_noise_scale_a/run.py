"""Only fitting entry point. Immutable stage checkpoints, bounded optimizer calls."""
from common import *
from model import CFG,conditions,generate,validate_inputs
from adapter import solve
from scipy.optimize import least_squares
import argparse,subprocess,time,collections

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--smoke',action='store_true');args=p.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    seeds=CFG['development_seeds'] if args.smoke else CFG['seeds'];limit=CFG['development_optimizer_call_limit'] if args.smoke else CFG['formal_optimizer_call_limit']
    codepaths=[ROOT/'tools/midterm_noise_scale_a'/s for s in ['common.py','model.py','run.py']]+[ROOT/k for k in ['tools/midterm_weak_geometry_a/common.py','tools/midterm_prior_mechanism_b/adapter.py','tools/midterm_prior_mechanism_b/io_utils.py','tools/midterm_prior_mechanism_b/math_model.py','tools/midterm_simulation_validation/core.py','tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py']]
    contract=dict(config=CFG,smoke=args.smoke,source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in codepaths},solver=SOURCE['solver'],acceptance=SOURCE['acceptance'],config_hash=hashlib.sha256((DOC/'CONFIG.json').read_bytes()).hexdigest())
    if (out/'CONTRACT.json').exists():assert read(out/'CONTRACT.json')==contract
    else:
        save(out/'CONTRACT.json',contract);save(out/'START.json',dict(execution_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),freeze_sha='c88571f51d7165f568847c9338005ddf4880addb',time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    inputs=[]
    for q in conditions():
        for seed in seeds:
            path=out/'inputs'/f"{q['id']}-s{seed}.json.gz"
            if not path.exists():save(path,generate(q,seed))
            inputs.append(read(path))
    check=validate_inputs(inputs)
    if not (out/'INPUT_CHECKS.json').exists():save(out/'INPUT_CHECKS.json',check)
    oldstages=list((out/'stages').glob('*.json.gz'));calls=sum(read(p)['optimizer_calls'] for p in oldstages)
    configurations=0
    for rec in inputs:
      for m in CFG['methods']:
       for ini in CFG['initializations']:
        u=copy.deepcopy(rec['input']);u['obs']['start']=rec['initials'][ini];u['input_sha256']=digest(u['obs']);previous=None
        for stage in ['P0','P1']:
            path=out/'stages'/f"{rec['id']}-{m}-{ini}-{stage}.json.gz"
            if path.exists():z=read(path);assert z['input_digest']==digest(u);previous=z['result'];continue
            attempt=Path(str(path)+'.attempt');assert not attempt.exists(),'Interrupted call: preserve exposure and investigate, do not silently retry';save(attempt,dict(input_digest=digest(u),time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
            count=[0]
            def counted(*a,**kw):
                nonlocal calls
                if calls>=limit:raise RuntimeError('FROZEN OPTIMIZER CALL LIMIT')
                calls+=1;count[0]+=1;return least_squares(*a,**kw)
            result=solve(SOURCE,u,m,stage,previous,solver=counted);save(path,dict(id=rec['id'],method=m,init=ini,stage=stage,input_digest=digest(u),optimizer_calls=count[0],result=result));previous=result
        configurations+=1
      if configurations%100==0:print('completed configurations',configurations,flush=True)
    endpoints=[];cats=collections.Counter()
    for rec in inputs:
      for m in CFG['methods']:
       for ini in CFG['initializations']:
        stages={};nc=0
        for stage in ['P0','P1']:
            z=read(out/'stages'/f"{rec['id']}-{m}-{ini}-{stage}.json.gz");stages[stage]=compact(z['result']);nc+=z['optimizer_calls']
        endpoints.append(dict(id=rec['id'],method=m,init=ini,stages=stages,optimizer_calls=nc));cats[stages['P1']['category']]+=1
    assert calls<=limit
    if not args.smoke:assert configurations==CFG['expected_configurations']
    write_records(out/'INPUTS.jsonl.gz',inputs);write_records(out/'ENDPOINTS.jsonl.gz',endpoints);save(out/'COUNTS.json',dict(inputs=len(inputs),configurations=configurations,stage_records=2*configurations,optimizer_calls=calls,call_limit=limit,categories=dict(cats),smoke=args.smoke));print(read(out/'COUNTS.json'))
if __name__=='__main__':main()
