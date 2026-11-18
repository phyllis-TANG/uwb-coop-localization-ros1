"""Original-domain gated experiment using the unchanged #133 cold worker."""
import os
import subprocess
import sys
from pathlib import Path
from time import monotonic
from statistics import median
from fractions import Fraction

HERE=Path(__file__).resolve()
sys.path.insert(0,str(HERE.parents[1]))
from common import DOC, ROOT, TOOL, digest, read, write, sha
from runtime import plans, identity
from checker_v2 import worker_v2
from checker_v2.a_loader import load_a
from checker_v2 import b_fast
from kernel import checker
from geometry import projections,evaluate
from a_bridge import make_certificate

D=DOC/'original_performance'
OLD=DOC/'precontraction'
INPUT=DOC/'INPUTS.json.gz'
LOCK=read(DOC/'checker_v2/A_SOURCE_LOCK.json')
LOCK['source_root']=str(ROOT)
INPUTS=read(INPUT)
PLAN=read(OLD/'PLAN.json')
assert sha(INPUT)==PLAN['input_file_sha256']


def schedule(stage):
    if stage=='dev':
        case=read(OLD/'development/case.json')
        case.update(id='development',group='dev')
        settings=dict(read(OLD/'development/settings.json'),total_seconds=120,memory_bytes=1024**3)
        return [dict(id=arm,arm=arm,method='P4',case=case,settings=settings) for arm in ('original','candidate')]
    if stage=='pilot':
        cases={c['id']:c for c in INPUTS['deterministic']}
        jobs=[]
        for spec in PLAN['jobs']:
            arm='original' if spec['arm']=='original' else 'candidate'
            case=cases[spec['case']]
            assert digest(case)==spec['input_sha256']
            jobs.append(dict(id=spec['case']+'_'+arm,arm=arm,method='P4',case=case,settings=spec['settings']))
        return jobs
    return [dict(j,arm='candidate' if j['method']=='P4' else 'original') for j in plans(INPUTS,stage)]


def run(stage):
    if stage in ('deterministic','random'):
        prior='pilot' if stage=='deterministic' else 'deterministic'
        assert read(D/prior/'decision.json')['expand']
    folder=D/stage
    folder.mkdir(exist_ok=True)
    freeze=subprocess.check_output(['git','log','-1','--format=%H','--',str(HERE.parent)],text=True).strip()
    os.sched_setaffinity(0,{PLAN['cpu']})
    stage_start=monotonic()
    jobs=schedule(stage)
    if stage!='dev':
        actual=[dict(id=j['id'],case_hash=digest(j['case']),settings=j['settings'],arm=j['arm']) for j in jobs]
        assert actual==read(D/'FROZEN_PLAN.json')[stage]
    for job in jobs:
        directory=folder/job['id']
        limit=job['settings']['total_seconds']
        if stage=='random':
            limit=min(limit,7200-(monotonic()-stage_start))
            if limit<=0:break
        directory.mkdir()  # fail closed on any previous attempt
        start=monotonic()
        job.update(identity=identity(job,freeze,LOCK),thresholds=INPUTS['thresholds'],source_lock=LOCK,remaining_seconds=limit-.5)
        write(directory/'job.json',job)
        try:
            with (directory/'log.txt').open('w') as log:
                subprocess.run([sys.executable,HERE,'worker',directory],timeout=limit-(monotonic()-start),stdout=log,stderr=log,check=True)
            row=read(directory/(job['id']+'.worker.json'))
        except (subprocess.SubprocessError,OSError) as e:
            row=dict(status='FAILED',error=str(e))
        write(directory/'receipt.json',row)
        elapsed=monotonic()-start
        write(directory/'wall.json',dict(seconds=elapsed,status=row['status'] if elapsed<=limit else 'TIMEOUT'))
        print(job['id'],round(elapsed,3),flush=True)


def verify(stage):
    folder=D/stage
    rows=[]
    pairs={}
    _,a=load_a(LOCK)
    for j in schedule(stage):
        unit=j['id']; directory=folder/unit
        row=dict(id=unit,method=j['method'],arm=j['arm'],group=j['case']['group'])
        rows.append(row)
        try:
            wall=read(directory/'wall.json');row.update(wall)
            assert wall['status']=='COMPLETED'
            record=read(directory/(unit+'.result.json.gz'))
            cert=read(directory/(unit+'.certificate.json.gz'))
            case,s,m=j['case'],j['settings'],j['method']
            assert (record['case'],record['settings'],record['method'])==(case,s,m)
            tree=record['result']
            assert b_fast.audit(case['model'],m,s,tree)==record['certificate_b']
            p=projections(case['model'],tree)
            assert p==record['projections'] and make_certificate(case,m,s,tree,p)==cert
            assert a.check(case['a_input'],cert)==record['certificate_a']['validation']
            ev=evaluate(case['model'],m,s,tree,case['evaluation'])
            assert ev==record['evaluation']
            if stage in ('dev','pilot'):
                scientific=digest({k:v for k,v in cert.items() if k!='cost'})
                assert pairs.setdefault(case['id'],scientific)==scientific
            resolution=tree['termination']=='RESOLUTION_COMPLETE' and not tree['queue'] and all(all(Fraction(b)-Fraction(a)<=Fraction(t) for (a,b),t in zip(n['box'],s['tolerance'])) for n in tree['nodes'] if n['status']=='UNDECIDED')
            row.update(status='PASS',nodes=len(tree['nodes']),resolution=resolution,evaluation=ev,areas={car:z['area_upper_m2'] for car,z in p.items()},costs=read(directory/'receipt.json')['costs'])
        except Exception as error:
            row.update(status='FAIL' if directory.exists() else 'NOT_RUN',error=repr(error))
    decision=dict(rows=rows,expand=False)
    valid=all(r['status']=='PASS' for r in rows)
    if stage=='pilot' and valid:
        totals={arm:sum(r['seconds'] for r in rows if r['arm']==arm) for arm in ('original','candidate')}
        decision.update(totals=totals,expand=totals['candidate']<totals['original'])
    if stage=='deterministic' and valid:
        groups={m:[r for r in rows if r['group']=='main' and r['method']==m] for m in ('P4','N4')}
        med={m:median(r['seconds'] for r in g) for m,g in groups.items()}
        decision.update(medians=med,expand=all(len(g)==12 and med[m]<=2 and all(r['resolution'] for r in g) for m,g in groups.items()))
    write(folder/'decision.json',decision)
    print(stage,valid,decision.get('totals'),decision.get('medians'),decision['expand'])


if __name__=='__main__':
    action,arg=sys.argv[1:]
    if action=='worker':
        path=Path(arg)/'job.json'
        if read(path)['arm']=='candidate':worker_v2.b_fast=checker()
        worker_v2.run(path,path.parent)
    elif action=='run':run(arg)
    else:verify(arg)
