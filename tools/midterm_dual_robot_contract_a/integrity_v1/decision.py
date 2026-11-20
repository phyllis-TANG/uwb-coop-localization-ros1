"""Per-vehicle epoch decision. Caller supplies publication and clock metadata."""
import argparse
from fractions import Fraction
from functools import lru_cache
import gzip
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import tempfile

BASE='8acffa9f4061e4740c18c7d0f1e09d28cf7f3155'
HEIGHT='da852740689113529b38815e1eb81f949ff5a8c6'
SRC='tools/midterm_dual_robot_contract_a/'
ROOT=Path(__file__).resolve().parents[3]


def rational(value):
    if not isinstance(value,str):
        raise ValueError('expected rational string')
    return Fraction(value)


def pairs(items):
    d=dict(items)
    if len(d)!=len(items):
        raise ValueError('duplicate JSON key')
    return d


def load(path):
    path=Path(path)
    data=path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix=='.gz' else data,object_pairs_hook=pairs)


@lru_cache(None)
def verifier(kind):
    sha=HEIGHT if kind=='height' else BASE
    entry={'height':'height_v1/checker.py','plane':'checker_v2.py','composite':'precontract_v1/contract.py'}[kind]
    with tempfile.TemporaryDirectory() as tmp:
        for name in {'core.py','checker_v2.py',entry}:
            path=Path(tmp)/name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(subprocess.check_output(['git','show',sha+':'+SRC+name],cwd=ROOT))
        spec=importlib.util.spec_from_file_location('a_integrity_'+kind,Path(tmp)/entry)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


def covering_radius(rectangles,xy):
    center=tuple(map(rational,xy))
    if len(center)!=2 or not rectangles:
        raise ValueError('expected XY and nonempty rectangles')
    r2=max(sum(max((rational(a)-v)**2,(rational(b)-v)**2)
               for (a,b),v in zip(row['box'],center,strict=True)) for row in rectangles)
    scale=10**30
    k=math.isqrt(r2.numerator*scale**2//r2.denominator)
    return Fraction(k+(Fraction(k,scale)**2<r2),scale)


def decide(public,original,certificate):
    fields='case seed car state_time estimate_xy decision_ready_time AL as_of deadline valid_until published_at input_hash frame mode'
    if set(public)!=set(fields.split()) or public['car'] not in ('p','s'):
        raise ValueError('publication schema or car')
    row=dict(public,PL=None,alarm=False,available=False,reason=None)
    def stop(reason):
        row['reason']=reason
        return row
    now,state,deadline,expiry,limit=map(rational,(public[k] for k in ('as_of','state_time','deadline','valid_until','AL')))
    if limit<0 or min(deadline,expiry)<state:
        raise ValueError('invalid policy limits')
    if public['estimate_xy'] is None or public['published_at'] is None:
        return stop('NO_PUBLISHED_POSITION')
    published=rational(public['published_at'])
    if published<state or now<max(state,published):
        return stop('NO_PUBLISHED_POSITION')
    if now>expiry:
        return stop('EXPIRED')
    ready=public['decision_ready_time']
    if ready is None or rational(ready)>now:
        return stop('NOT_READY')
    if rational(ready)<published:
        return stop('INVALID_CLOCK_ORDER')
    if rational(ready)>deadline:
        return stop('LATE')
    if certificate is None:
        return stop('MISSING_CERTIFICATE')
    try:
        if (original['input_hash']!=public['input_hash'] or original['case_id']!=public['case']
                or original['frame']!=public['frame']):
            return stop('INPUT_IDENTITY')
        if 'preprocessing' in certificate:
            result=verifier('composite').check_composite(original,certificate)
            tree=certificate['search_certificate']
            mode='4d'
        else:
            height=original['schema_version']=='DUAL-FIXED-HEIGHT-1'
            module=verifier('height' if height else 'plane')
            result=module.check(original,certificate)
            tree=certificate
            mode=tree['mode']
            if height and rational(original['source_times'][public['car']])!=state:
                return stop('STATE_TIME_MISMATCH')
        if mode!=public['mode'] or mode not in ('4d','no_peer'):
            return stop('MODE_MISMATCH')
        if tree is None or result['status']=='EVENT_ROOT_EMPTY':
            return stop('EMPTY_REGION')
        rectangles=tree['projections'][public['car']]['rectangles']
        if not rectangles:
            return stop('EMPTY_REGION')
        radius=covering_radius(rectangles,public['estimate_xy'])
    except (KeyError,TypeError,ValueError,IndexError,ArithmeticError):
        return stop('INVALID_CERTIFICATE_OR_INPUT')
    row.update(PL=str(radius),alarm=radius>limit,available=radius<=limit)
    return stop('PL_EXCEEDS_AL' if row['alarm'] else
                'WITHIN_AL_BUDGET_OUTER' if tree['status']=='BUDGET_OUTER' else 'WITHIN_AL')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ('publication','input','certificate'):
        parser.add_argument(key)
    args=parser.parse_args()
    publication=load(args.publication)
    try:
        original=load(args.input)
        certificate=load(args.certificate)
    except FileNotFoundError:
        original=certificate=None
    except (OSError,EOFError,ValueError):
        original=certificate={}
    print(json.dumps(decide(publication,original,certificate),indent=2))
