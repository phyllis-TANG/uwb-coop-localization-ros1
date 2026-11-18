"""Small exact-rational candidate producer, separate from the independent verifier.

Enumerates one/two nonnegative affine-row multipliers in 2D; no localization search,
no floating optimizer, no claim of optimal SOCP bounds. Deadline -> original endpoint.
"""
import argparse
import importlib.util
import itertools
import json
import math
from fractions import Fraction as F
from pathlib import Path
from time import perf_counter

_spec=importlib.util.spec_from_file_location('p4_precontract_checker',Path(__file__).with_name('contract.py'))
C=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(C)

def _root_upper(x):
    scale=10**30;n=math.isqrt(x.numerator*scale*scale//x.denominator)
    return F(n,scale) if F(n,scale)**2==x else F(n+1,scale)

def _rows_and_ranges(x):
    anchors=[list(map(F,x['anchor_map']['a'+str(i)])) for i in range(4)]
    out={};ranges={}
    for car,offset in [('p',0),('s',4)]:
        rr=[];rows=[]
        for i in range(4):
            l,u=map(F,x['observation_intervals'][offset+i]);radius=_root_upper(F(26)*F(x['noise_model']['variance'][offset+i]))
            rr.append({'measurement_id':x['measurement_ids'][offset+i],'rho_upper':str(radius),'lower':str(max(F(0),l-radius)),'upper':str(max(F(0),u+radius))})
        for i,j in itertools.permutations(range(4),2):
            ci=[2*(anchors[j][k]-anchors[i][k]) for k in range(2)]
            rhs=F(rr[i]['upper'])**2-F(rr[j]['lower'])**2+sum(v*v for v in anchors[j])-sum(v*v for v in anchors[i])
            rows.append((f'{car}:pair:a{i}:a{j}',ci,rhs))
        for axis,sign in itertools.product((0,1),(-1,1)):
            c=[F(sign if k==axis else 0) for k in (0,1)];tag='-' if sign==-1 else '+'
            d=x['domains'][(0 if car=='p' else 2)+axis]
            rows.append((f'{car}:domain:{axis}:{tag}',c,sign*F(d[0 if sign==-1 else 1])))
            for i,anchor in enumerate(anchors):rows.append((f'{car}:ball_axis:a{i}:{axis}:{tag}',c,sign*anchor[axis]+F(rr[i]['upper'])))
        out[car]=rows;ranges[car]=rr
    return out,ranges

def _solutions(rows,target):
    for rid,c,b in rows:
        axis=0 if c[0] else 1
        if not c[axis]:continue
        w=target[axis]/c[axis]
        if w>=0 and all(w*c[k]==target[k] for k in (0,1)):
            yield [(rid,w)],w*b
    for (ri,a,ba),(rj,b,bb) in itertools.combinations(rows,2):
        determinant=a[0]*b[1]-a[1]*b[0]
        if not determinant:continue
        u=(target[0]*b[1]-target[1]*b[0])/determinant
        v=(a[0]*target[1]-a[1]*target[0])/determinant
        if u>=0 and v>=0:yield [(ri,u),(rj,v)],u*ba+v*bb

def propose(x,skip=None,clock=perf_counter):
    """skip maps direction ID to a documented FALLBACK_* reason, for controlled fallback."""
    start=clock();C.K.validate(x);rows,ranges=_rows_and_ranges(x)
    directions=[];box=[list(map(F,v)) for v in x['domains'][:4]]
    for car,axis,sign in C.DIRECTIONS:
        begin=clock();did=C.direction_id(car,axis,sign);idx=(0 if car=='p' else 2)+axis;side=0 if sign<0 else 1
        original=F(x['domains'][idx][side]);best=None;terms=None;status='CERTIFIED';reason='exact nonnegative affine certificate'
        if skip and did in skip:
            status=skip[did];C.require(status in C.FALLBACKS,'INVALID_SKIP_STATUS');reason='caller supplied no usable direction certificate; original endpoint retained'
        elif begin-start>=4:
            status='FALLBACK_TIMEOUT';reason='total preprocessing budget exhausted'
        else:
            target=[F(sign if k==axis else 0) for k in (0,1)]
            # Iterate every candidate in a fixed order; never use truth or search outcomes.
            for candidate_terms,bound in _solutions(rows[car],target):
                now=clock()
                if now-begin>0.5 or now-start>4:
                    status='FALLBACK_TIMEOUT';reason='direction/total deadline exceeded; partial candidate discarded';break
                if best is None or bound<best:best=bound;terms=candidate_terms
            if clock()-begin>0.5 or clock()-start>4:
                status='FALLBACK_TIMEOUT';reason='deadline checked after enumeration; candidate discarded'
            if status=='CERTIFIED' and best is None:
                status='FALLBACK_UNCERTIFIED';reason='no finite nonnegative combination found'
        elapsed=clock()-begin
        if elapsed>0.5 and status=='CERTIFIED':status='FALLBACK_TIMEOUT';reason='deadline checked before adoption; candidate discarded'
        candidate=None if best is None else sign*best
        if status=='CERTIFIED':
            endpoint=max(original,candidate) if sign<0 else min(original,candidate)
            proof={'kind':'rational_support_v1','linear':[{'row_id':rid,'weight':str(w)} for rid,w in terms if w!=0],
                   'balls':[],'residual':['0','0'],'support_upper':str(best)}
        else:endpoint=original;proof=None
        box[idx][side]=endpoint
        directions.append({'id':did,'car':car,'axis':axis,'sign':sign,'status':status,'original_endpoint':str(original),
                           'candidate_endpoint':None if candidate is None else str(candidate),'adopted_endpoint':str(endpoint),
                           'proof':proof,'reason':reason,'elapsed_seconds':str(max(0.0,elapsed))})
    empty=any(a>b for a,b in box)
    return {'schema_version':C.VERSION,'source_contract_commit':C.A_START,'original_input_hash':x['input_hash'],
            'measurement_ids':x['measurement_ids'][:],'original_domain':[v[:] for v in x['domains'][:4]],'range_enclosures':ranges,
            'directions':directions,'contracted_domain':None if empty else [[str(a),str(b)] for a,b in box],
            'status':'EMPTY_PROVED' if empty else 'BOX_CERTIFIED','budget':C.BUDGET.copy(),
            'cost':{'preprocess_seconds':str(max(0.0,clock()-start))}}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('output');a=p.parse_args()
    result=propose(C.load_json(a.input));Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'directions':{s:sum(r['status']==s for r in result['directions']) for s in ['CERTIFIED']+sorted(C.FALLBACKS)}}))
