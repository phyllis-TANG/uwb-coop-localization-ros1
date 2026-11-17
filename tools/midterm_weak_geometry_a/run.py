"""Only this entry point imports the frozen optimizer. Saved input + new start only."""
from common import *
import argparse,subprocess,time,collections
from scipy.optimize import least_squares
from adapter import solve

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--smoke',action='store_true');args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
    if args.smoke:
        u=read(OLD/'development_fixture/inputs/p00-s26011601.json.gz');rows=[dict(id='p00-s26011601',input=u,initials=initials(u['obs']['anchors'],u['obs']['start']))]
    else:rows=list(records(DOC/'INPUTS.jsonl.gz'))
    source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['tools/midterm_weak_geometry_a','tools/midterm_prior_mechanism_b','tools/midterm_simulation_validation','tools/midterm_simulation_s2','tools/midterm_simulation_phase1'] for p in (ROOT/folder).glob('*.py')}
    contract=dict(config=CFG,source=source,inputs_sha256=hashlib.sha256((DOC/'INPUTS.jsonl.gz').read_bytes()).hexdigest(),smoke=args.smoke)
    if (out/'CONTRACT.json').exists():assert read(out/'CONTRACT.json')==contract,'Source changed since start'
    else:save(out/'CONTRACT.json',contract);save(out/'START.json',dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())))
    completed=0
    for rec in rows:
        for m in CFG['methods']:
            for ini in CFG['initializations']:
                u=copy.deepcopy(rec['input']);u['obs']['start']=rec['initials'][ini];u['input_sha256']=digest(u['obs']);base=out/f"{rec['id']}-{m}-{ini}";previous=None
                for stage in ['P0','P1']:
                    path=Path(str(base)+f'-{stage}.json.gz')
                    if path.exists():z=read(path);assert z['input_digest']==digest(u);previous=z['result'];continue
                    calls=[0]
                    def counted(*a,**kw):calls[0]+=1;return least_squares(*a,**kw)
                    # Persist attempt before call; a crash cannot silently erase exposure.
                    attempt=Path(str(path)+'.attempt.json');assert not attempt.exists(),'Interrupted stage: inspect attempt before any rerun'
                    save(attempt,dict(time_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),input_digest=digest(u)))
                    result=solve(SOURCE,u,m,stage,previous,solver=counted);save(path,dict(id=rec['id'],method=m,init=ini,stage=stage,input_digest=digest(u),optimizer_calls=calls[0],result=result));previous=result
                completed+=1
        if completed%120==0:print('completed configurations',completed,flush=True)
    evidence=[];counter=collections.Counter();calls=0
    for rec in rows:
        for m in CFG['methods']:
            for ini in CFG['initializations']:
                stages={};nc=0
                for stage in ['P0','P1']:
                    z=read(out/f"{rec['id']}-{m}-{ini}-{stage}.json.gz");stages[stage]=compact(z['result']);nc+=z['optimizer_calls']
                calls+=nc;counter[stages['P1']['category']]+=1;evidence.append(dict(id=rec['id'],method=m,init=ini,stages=stages,optimizer_calls=nc))
    write_records(out/'ENDPOINTS.jsonl.gz',evidence);save(out/'COUNTS.json',dict(configurations=len(evidence),stage_records=2*len(evidence),optimizer_calls=calls,categories=dict(counter),smoke=args.smoke));print(read(out/'COUNTS.json'))
if __name__=='__main__':main()
