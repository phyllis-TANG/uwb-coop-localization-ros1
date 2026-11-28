"""Independent exact replay of every compressed search tree, witness and result.

This verifier imports neither run.py nor its solver. It rebuilds global roots from
raw observations, reconstructs the complete partition, and independently checks
the bound authorizing every discard. Quantities for thresholds use fractions.
"""
import csv
import gzip
import json
import math
import os
import sys
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

D=Path(__file__).resolve().parent/'results'
MODES=('anchor_only','peer_bounded','peer_known_zero')

def load(path):return json.loads(path.read_text())

def sqsum(p,q):return sum((x-y)**2 for x,y in zip(p,q))

@lru_cache(maxsize=65536)
def sqrtr(v):
    # Integer floor sqrt(v * 10^60) via an equivalent rational identity.
    p,q=v.as_integer_ratio();s=10**30
    n=math.isqrt((p*q)*s*s)//q
    a=F(n,s);b=a if a*a==v else F(n+1,s)
    assert a*a<=v<=b*b
    return a,b


def cartesian_distance(a,b,z):
    low=high=z*z
    for u,v in zip(a,b):
        ds=[u[0]-v[0],u[0]-v[1],u[1]-v[0],u[1]-v[1]]
        low+=(min(x*x for x in ds) if max(ds)<0 or min(ds)>0 else 0)
        high+=max(x*x for x in ds)
    return sqrtr(low)[0],sqrtr(high)[1]


def residual(d,y):
    dl,du=d;yl,yu=y
    # An ignored peer bias is profiled out at each candidate, so the largest
    # score uses distance to the observation interval, not max endpoint pairing.
    def gap(value):return max(F(0),yl-value,value-yu)
    return max(F(0),yl-du,dl-yu)**2,max(gap(dl),gap(du))**2


def verify_job(item):
    rec,mode=item;job=rec['id']+'_'+mode
    r=list(map(F,rec['observations']));h=list(map(F,rec['heights']));anchors=[tuple(map(F,a)) for a in rec['anchors']];center=[tuple(map(F,c)) for c in rec['center']]
    var=F(1,625); root=[]
    for car,z in enumerate(h):
        extent=[]
        for k,(x,y,za) in enumerate(anchors):
            d=r[4*car+k]+sqrtr(26*var)[1]; extent.append(sqrtr(d*d-(z-za)**2)[1]);
        root.extend((max(a[dim]-v for a,v in zip(anchors,extent)),min(a[dim]+v for a,v in zip(anchors,extent))) for dim in range(2))
    @lru_cache(maxsize=8192)
    def anchor_score(box,i):
        lo=hi=0
        for j,a in enumerate(anchors):
            y=r[i*4+j];p=tuple((x,x) for x in a[:2]);du=cartesian_distance(box,p,h[i]-a[2]);v,w=residual(du,(y,y));lo+=v;hi+=w
        return lo/var,hi/var
    peer_bias=F(3,5) if mode=='peer_bounded' else 0
    def score(box):
        lo1,hi1=anchor_score(box[:2],0);lo2,hi2=anchor_score(box[2:],1)
        if mode=='anchor_only':return lo1+lo2,hi1+hi2
        d=cartesian_distance(box[:2],box[2:],h[0]-h[1]);p,q=residual(d,(r[-1]-peer_bias,r[-1]+peer_bias));return lo1+lo2+p/var,hi1+hi2+q/var
    tree=gzip.decompress((D/'trees'/(job+'.gz')).read_bytes());queue=deque([tuple(root)]);radii=[F(0),F(0)];dl=du=None; lookup=[{},{}];counts=Counter()
    for tag in tree.decode():
        box=queue.popleft();counts[tag]+=1
        if tag=='S':
            widths=[y-x for x,y in box];i=widths.index(max(widths));x,y=box[i];mid=(x+y)/2;assert x<mid<y
            queue.extend((box[:i]+((x,mid),)+box[i+1:],box[:i]+((mid,y),)+box[i+1:]))
            continue
        lo,hi=score(box)
        if tag=='O':assert lo>26;continue
        if tag=='I':assert hi<=26
        elif tag=='U':assert max(y-x for x,y in box)<=F(1,20)
        else:assert tag=='P'
        for i,sub in enumerate((box[:2],box[2:])):
            if sub not in lookup[i]:lookup[i][sub]=sum(max((x-u)**2,(y-u)**2) for u,(x,y) in zip(center[i],sub))
            radii[i]=max(radii[i],lookup[i][sub])
        if mode=='anchor_only':
            low,high=cartesian_distance(box[:2],box[2:],h[0]-h[1]); dl=low if dl is None else min(dl,low);du=high if du is None else max(du,high)
    assert not queue and counts['P']==0
    tf=tuple(F(x) for x in rec['reference_xy']);truthscore=score(tuple((x,x) for x in tf));assert truthscore[1]<=26
    names={'I':'INSIDE','O':'OUTSIDE','S':'SPLIT','U':'UNDECIDED','P':'PENDING'}
    for i,car in enumerate(('Car1','Car2')):
        c=load(D/'certificates'/(job+'_'+car+'.json'));assert tuple(tuple(map(F,rng)) for rng in c['root'])==tuple(root)
        assert {names[k]:v for k,v in counts.items() if v}==c['kinds'];assert radii[i]==F(c['outer_squared'])
        p1,p2=c['witnesses']; points=[]
        for w in (p1,p2):
            pt=tuple(map(F,w['xy4'])); verified=score(tuple((v,v) for v in pt));assert verified[1]<=26 and verified[1]==F(w['score_upper']);points.append(pt[2*i:2*i+2])
        l2=sqsum(*points)/4;assert l2==F(c['any_lower_squared']) and l2<=radii[i]
        assert c['row']['status_10cm']==('EXCLUDED' if l2>F(1,100) else 'CERTIFIED' if radii[i]<=F(1,100) else 'UNRESOLVED')
        assert bool(c['row']['true_feasible'])==(truthscore[1]<=26)
    if mode=='anchor_only':
        yr=r[-1]; verified=bool(dl>=yr-F(3,5) and du<=yr+F(3,5));return dict(split=rec['split'],epoch=rec['epoch'],layout=rec['layout'],peer_obs_m=float(yr),no_peer_slant_lower_m=float(dl),no_peer_slant_upper_m=float(du),min_slack_m=float(min(dl-yr+F(3,5),yr+F(3,5)-du)),set_equality_proved=verified)


def main():
    obs=[load(p) for p in sorted((D/'observations').glob('*.json'))];assert len(obs)==8
    for rec in obs:
        partner=next(x for x in obs if x['split']==rec['split'] and x['epoch']==rec['epoch'] and x['layout']!=rec['layout']);assert partner['observations'][-1]==rec['observations'][-1] and partner['generated_noise']==rec['generated_noise'] and partner['reference_xy']==rec['reference_xy']
    items=[(r,m) for r in obs for m in MODES]
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv)>1 else 4) as pool: equal=[v for v in pool.map(verify_job,items) if v]
    with (D/'redundancy.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=equal[0].keys());w.writeheader();w.writerows(equal)
    table=list(csv.DictReader((D/'rows.csv').open()));assert len(table)==48
    for row in table:
        key=f"{row['split']}_{int(row['epoch']):02d}_{row['layout']}_{row['mode']}_{row['car']}";c=load(D/'certificates'/(key+'.json'))['row'];
        for k,v in row.items():assert v==('' if c[k] is None else str(c[k]))
    print(f'PASS {len(items)} full four-dimensional partitions, {len(table)} upper bounds, {2*len(table)} strictly feasible candidate positions, all truth scores <=26; {sum(r["set_equality_proved"] for r in equal)}/8 set equalities proved.')


if __name__=='__main__':main()
