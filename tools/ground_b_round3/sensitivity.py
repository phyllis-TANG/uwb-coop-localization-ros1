"""Six fixed-input searches followed by certificate readback and truth evaluation."""
import argparse
import csv
import gzip
import hashlib
import itertools
import json
import math
import sys
import time
from fractions import Fraction as Q
from pathlib import Path

import check
import witness
from check import ROOT
sys.path.insert(0,str(ROOT/'tools/ground_continuous_b'))
import region
from audit import validate
from a_interface import check_radius

OLD=ROOT/'docs/research/ground_continuous_b/runs'
OUTPUT=check.OUT/'sensitivity'
CASES={'baseline':(40000,600000),'zero_bias':(40000,0),'tight_sigma':(20000,600000)}
SCENES=('nominal','peer_step')


def source(scene,name):
    return json.loads(gzip.decompress(check.pinned(OLD/f'101_{scene}'/name)))


def observation(scene):
    r=next(r for r in source(scene,'records.json.gz') if r['t']==30)
    return {'obs':r['obs'],'xy':r['xy']}


def input_hash(record):
    return hashlib.sha256(json.dumps(record,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def proofs(record,sigma,bias):
    variance=Q(sigma,10**6)**2
    bound=Q(bias,10**6)
    valid=list(witness.candidates(record,bias=float(bound),squared_limit=float(26*variance)*(1-1e-8)))
    pairs=[]
    for c in (0,1):
        projected={both[c]:both for both in valid}
        if len(projected)<2:
            pairs.append([])
            continue
        a,b=max(itertools.combinations(projected,2),key=lambda p:math.dist(*p))
        pairs.append([witness.evidence(projected[x],record['obs'],variance=variance,bound=bound) for x in (a,b)])
    return pairs


def run(out):
    for scene in SCENES:
        record=observation(scene)
        for name,(sigma,bias) in CASES.items():
            start=time.perf_counter()
            cert=region.solve(record['obs'],record['xy'],
                              sigma_um=sigma,bias_um=bias,cell_um=25000)
            elapsed=time.perf_counter()-start
            pairs=proofs(dict(record,region=cert),sigma,bias)
            packet=dict(seed=101,t=30,scene=scene,case=name,input_sha256=input_hash(record),
                        sigma_um=sigma,bias_um=bias,cell_um=25000,search_s=elapsed,
                        region=cert,witnesses=pairs)
            path=out/f'{scene}_{name}.json.gz'
            path.write_bytes(gzip.compress(json.dumps(packet,separators=(',',':')).encode(),mtime=0))


def truth_stat(xy,obs,variance,bound):
    """Enclose the original statistic minimized over the single allowed peer bias."""
    xyz=[(*p,h) for p,h in zip(xy,obs['heights'],strict=True)]
    links=[(p,a) for p in xyz for a in obs['anchors']]+[tuple(xyz)]
    lower=upper=Q(0)
    for i,((p,a),y) in enumerate(zip(links,obs['ranges'],strict=True)):
        dl,dh=check.bracket(check.norm2(p,a))
        lo,hi=Q(y)-dh,Q(y)-dl
        b=bound if i==8 else 0
        lower+=max(0,lo-b,-hi-b)**2
        upper+=max(0,abs(lo)-b,abs(hi)-b)**2
    return lower/variance,upper/variance


def rounded(q,scale,up=False):
    n=math.ceil(q*scale) if up else math.floor(q*scale)
    return n/scale


def evaluate(out):
    with (ROOT/'docs/research/ground_b_round2/evaluation/resolution.csv').open() as f:
        old={(r['scene'],int(r['car'])):r['radius_m'] for r in csv.DictReader(f) if r['resolution_m']=='0.025'}
    rows=[]
    for scene in SCENES:
        data=observation(scene)
        truth=source(scene,'truth.json.gz')[30*20]
        for name,(sigma,bias) in CASES.items():
            p=json.loads(gzip.decompress((out/f'{scene}_{name}.json.gz').read_bytes()))
            assert (p['scene'],p['case'],p['t'],p['seed'],p['cell_um'],p['sigma_um'],p['bias_um'],p['input_sha256'])==(scene,name,30,101,25000,sigma,bias,input_hash(data))
            cert=p['region']
            validate(dict(data,region=cert),sigma_um=sigma,bias_um=bias,cell_um=25000)
            check_radius(dict(data,region=cert))
            var,bound=Q(sigma,10**6)**2,Q(bias,10**6)
            low,high=truth_stat(truth,data['obs'],var,bound)
            compat='YES' if high<=26 else 'NO' if low>26 else 'UNKNOWN'
            if not cert['joint']:
                assert compat=='NO'
            for c in (0,1):
                pl=cert['pl'][c]
                base=Q(old[scene,c+1])
                if name=='baseline':
                    assert Q(str(pl))==base
                pair=[check.point(w,data['obs'],variance=var,bound=bound)[c] for w in p['witnesses'][c]]
                lb=None
                if pair:
                    assert len(pair)==2 and pl is not None
                    lb=rounded(check.bracket(check.norm2(*pair))[0]*50,10000)
                    assert lb<=pl*100
                decision=('PROVED_EMPTY' if not cert['joint'] else 'OUTER_WITHIN_10_CM' if pl<=.10 else
                          'ANY_CENTER_EXCEEDS_10_CM' if lb is not None and lb>10 else 'UNDETERMINED')
                rows.append(dict(scene=scene,case=name,car=c+1,sigma_cm=sigma/10000,bias_halfwidth_cm=bias/10000,
                    G1_outer_cm=None if pl is None else float(Q(str(pl))*100),
                    delta_from_baseline_cm=None if pl is None else float((Q(str(pl))-base)*100),
                    any_center_lower_cm=lb,truth_compatible=compat,truth_stat_low=rounded(low,10**6),
                    truth_stat_high=rounded(high,10**6,True),search_status='COMPLETE',joint_box_pairs=sum(len(js) for _,js in cert['joint']),
                    witness_status='VERIFIED_PAIR' if pair else 'EMPTY' if not cert['joint'] else 'NOT_FOUND',
                    radius_conclusion=decision,search_s=p['search_s'],input_sha256=p['input_sha256']))
    return rows


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--out',type=Path,default=OUTPUT)
    parser.add_argument('--readback',action='store_true')
    args=parser.parse_args()
    path=args.out/'results.csv'
    if not args.readback:
        args.out.mkdir(parents=True,exist_ok=True)
        if any(args.out.glob('*.json.gz')) or path.exists():
            parser.error('Use a fresh output directory or --readback')
        run(args.out)
    rows=evaluate(args.out)
    if args.readback:
        with path.open() as f:
            assert list(csv.DictReader(f))==[{k:'' if v is None else str(v) for k,v in r.items()} for r in rows]
    else:
        with path.open('w') as f:
            w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
            w.writeheader()
            w.writerows(rows)
    print('PASS: 6 completed joint searches, 12 car rows')
if __name__=='__main__':
    main()
