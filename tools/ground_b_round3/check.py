"""Independent standard-library verifier: exact rationals, no search or generator imports."""
import csv
import gzip
import hashlib
import json
import math
import subprocess
from fractions import Fraction as Q
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/research/ground_b_round3'
BASE='c7d53da2bb989f73514a6ce540813c379d698897'
V=Q(1,625)
B=Q(3,5)


def require(ok,reason):
    if not ok:
        raise ValueError(reason)


def pinned(path):
    blob=subprocess.check_output(['git','show',BASE+':'+str(path.relative_to(ROOT))],cwd=ROOT)
    require(blob==path.read_bytes(),'source identity')
    return blob


def norm2(a,b):
    return sum((Q(x)-Q(y))**2 for x,y in zip(a,b,strict=True))


def bracket(q):
    # Refine by exact rational bisection, independently of the producer's isqrt.
    require(q>=0,'negative radicand')
    left,right=Q(0),max(Q(1),q)
    for _ in range(120):
        mid=(left+right)/2
        if mid**2==q:
            return mid,mid
        if mid**2<q:
            left=mid
        else:
            right=mid
    return left,right


def point(w,obs,*,variance=V,bound=B):
    xy=[tuple(map(Q,v)) for v in w['xy_m']]
    require(len(xy)==2 and all(len(v)==2 for v in xy),'paired XY')
    a,b=[(*v,Q(h)) for v,h in zip(xy,obs['heights'],strict=True)]
    links=[(p,anchor) for p in (a,b) for anchor in obs['anchors']]+[(a,b)]
    residual=[tuple(map(Q,v)) for v in w['residual_intervals_m']]
    bias=Q(w['bias_m'])
    il,ih=map(Q,w['feasible_bias_inner_m'])
    ol,oh=map(Q,w['feasible_bias_outer_m'])
    require(-bound<=ol<=il<=bias<=ih<=oh<=bound,'bias domain')
    raw=[]
    for k,((p,s),y,(lo,hi)) in enumerate(zip(links,obs['ranges'],residual,strict=True)):
        d2=norm2(p,s)
        y=Q(y)
        center=y-(bias if k==8 else 0)
        # Validate both ends of the claimed distance interval by squaring.
        require(lo<=hi and center-lo>=0 and center-lo>=center-hi and
                max(0,center-hi)**2<=d2<=(center-lo)**2,'residual enclosure')
        low,high=bracket(d2)
        raw.append((y-high,y-low))
    stat=sum(max(lo**2,hi**2) for lo,hi in residual)/variance
    require(stat<Q(w['weighted_stat_strict_upper'])<26,'strict joint statistic')
    anchor_upper=sum(max(l*l,h*h) for l,h in raw[:8])
    anchor_lower=sum(max(l,-h,0)**2 for l,h in raw[:8])
    pl,ph=raw[8]
    for btest in (il,ih):
        require(anchor_upper+max((pl-btest)**2,(ph-btest)**2)<=26*variance,'bias endpoint')
    # Convexity covers the entire inner interval. Outer endpoints may clip at ±B.
    maxwidth=bracket(26*variance-anchor_lower)[1]
    require(ol<=max(-bound,pl-maxwidth) and oh>=min(bound,ph+maxwidth),'bias outer enclosure')
    return xy


def main():
    with (OUT/'radius_bounds.csv').open() as f:
        rows={(r['scene'],int(r['car'])):r for r in csv.DictReader(f)}
    source=ROOT/'docs/research/ground_b_round2/evaluation/resolution.csv'
    for r in csv.DictReader(pinned(source).decode().splitlines()):
        k=(r['scene'],int(r['car']))
        col={'0.025':'outer_025_m','0.05':'outer_05_m'}[r['resolution_m']]
        require(rows[k][col]==r['radius_m'],'registered outer bound')
    entries=json.loads((OUT/'witnesses.json').read_text())
    expected={(s,c) for s in ('nominal','peer_step') for c in (1,2)}
    require(len(entries)==4 and {(e['scene'],e['car']) for e in entries}==expected,'coverage')
    for e in entries:
        scene,car=e['scene'],e['car']
        require(e['seed']==101 and e['state_s']==30,'epoch')
        blob=pinned(ROOT/f'docs/research/ground_continuous_b/runs/101_{scene}/records.json.gz')
        require(hashlib.sha256(blob).hexdigest()==e['records_sha256'],'archive hash')
        rec=next(r for r in json.loads(gzip.decompress(blob)) if r['t']==30)
        p,s=[point(w,rec['obs'])[car-1] for w in e['witnesses']]
        d2=norm2(p,s)
        row=rows[scene,car]
        require(d2>Q(1,25) and row['status']=='PROVED','20 cm separation')
        require(Q(row['pair_distance_lower_m'])**2<=d2 and Q(1,10)<Q(row['any_center_lower_m']) and
                (2*Q(row['any_center_lower_m']))**2<=d2,'any-center bound')
        fixed=max(norm2(x,rec['xy'][car-1]) for x in (p,s))
        require(0<Q(row['G1_lower_m'])**2<=fixed<=Q(row['outer_025_m'])**2,'published-center bound')
    print('PASS: four projections, eight joint witnesses, 72 raw residual enclosures')

if __name__=='__main__':
    main()
