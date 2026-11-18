"""Reproduce PR132's frozen algorithms on its second supported segment."""
import sys, json, gzip, shutil, subprocess, hashlib, os
from pathlib import Path
import numpy as np
T=Path(__file__).resolve().parent
sys.path.insert(0,str(T.parent/'continuous'))
import coverage, prepare, replay, runner
from checker import audit, metrics
D=coverage.OLD/'replication'
OLD=coverage.DOC
A=Path(os.environ.get('MOON_SECOND_ART','/home/ubuntu22/moon-second-artifacts'))
A.mkdir(exist_ok=True)
def load(p):return json.loads(p.read_bytes())
def setup():
    coverage.DOC=D
    coverage.ART=A
    shutil.copyfile(OLD/'SUPPLEMENT_RECEIPT.json',D/'SUPPLEMENT_RECEIPT.json')
    sys.argv.append('--augment')
    coverage.main()
    evidence=load(D/'COVERAGE_AUDIT.json')
    assert evidence['candidates'][1]['longest_pass']==[109.66,114.]
    # Inherited generator chooses the first candidate. Give it the audited backup only.
    coverage.write(D/'BOTH_CANDIDATES.json',evidence)
    evidence['candidates']=evidence['candidates'][1:]
    coverage.write(D/'COVERAGE_AUDIT.json',evidence)
    prepare.DOC=D
    prepare.ART=A
    prepare.main()
    records=json.loads(gzip.decompress((D/'INPUTS.json.gz').read_bytes()))
    records=[r for r in records if r['reference']['condition']!='correlated_optional']
    (D/'INPUTS.json.gz').write_bytes(gzip.compress(json.dumps(records,sort_keys=True).encode(),mtime=0))
    protocol=load(D/'PROTOCOL.json')
    protocol.update(base_sha='9d10bc7da28961ab914175c3f3e7bdc1f1bf02ef',optional='outside replication plan')
    coverage.write(D/'PROTOCOL.json',protocol)
    replay.DOC=D
    replay.export()
    replay.cpu()
    files=[D/n for n in ('INPUTS.json.gz','ROUTE.json','PROTOCOL.json','terrain.npz','continuous_route.usda','COVERAGE_AUDIT.json')]+[T/'run.py']+[T.parent/'continuous'/n for n in ('coverage.py','prepare.py','replay.py','runner.py','checker.py','estimator.py')]
    coverage.write(D/'FREEZE.json',{str(p.relative_to(coverage.ROOT)):coverage.sha(p) for p in files})
def execute():
    freeze=sys.argv[2]
    manifest=json.loads(subprocess.check_output(['git','show',freeze+':docs/research/lunar_end_to_end/replication/FREEZE.json']))
    assert all(coverage.sha(coverage.ROOT/p)==h for p,h in manifest.items())
    runner.DOC=D
    runner.ART=A
    tasks=runner.plan('main')
    records={r['observation']['id']:r for r in runner.inputs()}
    results=[]
    for task in tasks:
        r=records[task['id']]
        key=task['key']
        out=A/(key+'.json')
        attempt=A/(key+'.attempt')
        if not out.exists():
            attempt.touch(exist_ok=False)
            z=runner.solve(r['observation'],task['method'],None,lambda q:coverage.write(A/(key+'.checkpoint'),q))
            z.update(method=task['method'],rho=None,task=task,input_sha256=r['input_sha256'],freeze=freeze)
            z['metrics']=metrics(r['observation'],r['reference'],z['x'],z['method'])
            coverage.write(out,z)
        z=load(out)
        assert z['freeze']==freeze and z['input_sha256']==prepare.digest(r['observation'])
        audit(r['observation'],z)
        results.append(z)
    assert len(results)==120
    (D/'ENDPOINTS.json.gz').write_bytes(gzip.compress(json.dumps(results).encode(),mtime=0))
    print('Verified',len(results),'endpoints')
if __name__=='__main__':
    if sys.argv[1]=='prepare':setup()
    else:execute()
