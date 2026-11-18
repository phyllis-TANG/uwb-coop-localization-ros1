"""Frozen single-epoch experiment. Each planned attempt gets one cold worker."""
import json
import os
import resource
import signal
import subprocess
import sys
from fractions import Fraction
from math import ceil
from pathlib import Path
from time import monotonic

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))
from common import DOC, read, write, digest, sha, load_module
from core import solve
from prepare import convert
from geometry import evaluate
from checker_v2 import b_fast
from runtime import plans

D = DOC / 'precontraction'
A = Path(os.getenv('PILOT_A_SOURCE', str(Path.home()/'b-pilot-lock')))
READY = read(D/'A_READY.json')
PLAN = read(D/'PLAN.json')


def prepare(x, producer):
    def expired(*_):
        raise TimeoutError('preprocessing watchdog')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 4)
    try:
        p = producer.propose(x)
    except (TimeoutError, ArithmeticError) as error:
        reason = 'FALLBACK_TIMEOUT' if isinstance(error, TimeoutError) else 'FALLBACK_ERROR'
        skip = {producer.C.direction_id(*direction): reason for direction in producer.C.DIRECTIONS}
        p = producer.propose(x, skip=skip)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    # Search uses Decimal. Relax candidate supports outward to micrometres.
    box = [list(v) for v in x['domains'][:4]]
    for index, row in enumerate(p['directions']):
        if row['status'] == 'CERTIFIED':
            sign = row['sign']
            candidate = sign * Fraction(ceil(sign * Fraction(row['candidate_endpoint']) * 10**6), 10**6)
            endpoint = sign * min(sign*candidate, sign*Fraction(row['original_endpoint']))
            row.update(candidate_endpoint=str(candidate), adopted_endpoint=str(endpoint))
        box[index//2][index%2] = row['adopted_endpoint']
    empty = any(Fraction(lo)>Fraction(hi) for lo,hi in box)
    p.update(contracted_domain=None if empty else box, status='EMPTY_PROVED' if empty else 'BOX_CERTIFIED')
    return p


def worker(folder):
    job = read(folder/'job.json')
    case, settings, method = job['case'], job['settings'], job['method']
    x = case['a_input']
    costs = {}
    def timed(label, fn, *args):
        start = monotonic()
        value = fn(*args)
        costs[label] = monotonic()-start
        return value
    contract = load_module('published_contract', A/READY['entry'])
    p = None
    y = x
    if job['arm']=='contracted':
        producer = load_module('published_producer', A/READY['producer_entry'])
        p = timed('preprocessing', prepare, x, producer)
        y = timed('precheck_and_derive', contract.restricted_input, x, p)
    tree = cert = None
    if y is not None:
        model = convert(y)
        tree = timed('search', solve, model, method, settings, {'8':'24','9':'26'})
        timed('checkpoint_io', write, folder/'tree.json.gz', tree)
        timed('B_check', b_fast.audit, model, method, settings, tree)
    raw = tree if tree is not None else {'nodes':[]}
    regions = timed('projection', b_fast.projections, case['model'], raw)
    timed('projection_audit', b_fast.audit_projection, case['model'], raw, regions)
    if tree is not None:
        cert = timed('conversion', b_fast.make_certificate, dict(case,a_input=y), method, settings, tree, regions)
    if p is not None:
        cert = dict(schema_version=contract.VERSION, original_input_hash=x['input_hash'], preprocessing=p,
                    preprocess_hash=contract.K.digest(p), restricted_input_hash=y['input_hash'] if y else None,
                    search_certificate=cert)
        verdict = timed('A_check', contract.check_composite, x, cert)
        assert verdict['accepted']
    else:
        verdict = timed('A_check', contract.V2.check, x, cert)
        assert verdict['certificate_valid']
    ev = timed('evaluation', evaluate, case['model'], method, settings, raw, case['evaluation'])
    timed('evidence_io', write, folder/'proof.json.gz', dict(original=x,restricted=y,certificate=cert,
          regions=regions,evaluation=ev,verdict=verdict))
    write(folder/'worker.json', costs)


def run(stage, stop):
    inputs = read(DOC/'INPUTS.json.gz')
    assert sha(DOC/'INPUTS.json.gz') == PLAN['input_file_sha256']
    assert all(sha(A/path)==value for path,value in READY['file_hashes'].items())
    os.sched_setaffinity(0,{PLAN['cpu']})
    if stage=='dev':
        case=read(D/'development/case.json')
        jobs=[dict(case=case,method='P4',settings=dict(read(D/'development/settings.json'),total_seconds=120,memory_bytes=1024**3),arm=a,id=a) for a in ['original','contracted']]
    elif stage=='pilot':
        cases={c['id']:c for c in inputs['deterministic']}
        jobs=[]
        for row in PLAN['jobs']:
            case=cases[row['case']]
            assert digest(case)==row['input_sha256']
            jobs.append(dict(case=case,settings=row['settings'],arm=row['arm'],method='P4',id=row['case']+'_'+row['arm']))
    else:
        gate=read(D/'runs'/('pilot' if stage=='deterministic' else 'deterministic')/'decision.json')
        assert gate['expand']
        jobs=plans(inputs,stage)
        for job in jobs:
            job['arm']='contracted' if job['method']=='P4' else 'original'
    base=D/'runs'/stage
    base.mkdir(parents=True,exist_ok=True)
    freeze=subprocess.check_output(['git','log','-1','--format=%H','--',str(HERE)],text=True).strip()
    for job in jobs[:stop]:
        folder=base/job['id']
        if folder.exists():
            if not (folder/'receipt.json').exists():raise RuntimeError('uncertain attempt '+str(folder))
            continue
        folder.mkdir()
        start=monotonic()
        write(folder/'job.json',dict(job,freeze=freeze))
        s=job['settings']
        def limit():
            resource.setrlimit(resource.RLIMIT_AS,(s['memory_bytes'],)*2)
        try:
            with (folder/'log.txt').open('w') as log:
                subprocess.run([sys.executable,HERE,'worker',folder],check=True,stdout=log,stderr=log,
                               preexec_fn=limit,timeout=max(.001,s['total_seconds']-(monotonic()-start)))
            status='COMPLETE'
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as error:
            status=type(error).__name__
        write(folder/'receipt.json',dict(status=status,freeze=freeze))
        wall=monotonic()-start
        write(folder/'wall.json',dict(seconds=wall,status=status if wall<=s['total_seconds'] else 'TIMEOUT'))
        print(job['id'],status,wall,flush=True)


if __name__=='__main__':
    if sys.argv[1]=='worker':
        worker(Path(sys.argv[2]))
    else:
        run(sys.argv[1],int(sys.argv[2]))
