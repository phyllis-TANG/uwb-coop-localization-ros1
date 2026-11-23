"""Independent exact replay of every compressed search tree, witness and result.

This verifier imports neither run.py nor its solver. It rebuilds global roots from
raw observations, reconstructs the complete partition, and independently checks
the bound authorizing every discard. Quantities for thresholds use fractions.
"""
import csv
import hashlib
import numpy as np
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
BIAS={'anchor_only':F(0),'peer60':F(3,5),'peer15':F(3,20),'peer05':F(1,20)}

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
    peer_bias=BIAS[mode]
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
    assert not queue and sum(counts.values())-counts['P']<=150000
    tf=tuple(F(x) for x in rec['reference_xy']);truthscore=score(tuple((x,x) for x in tf));assert truthscore[1]<=26
    names={'I':'INSIDE','O':'OUTSIDE','S':'SPLIT','U':'UNDECIDED','P':'PENDING'}
    rows=[]
    for i,car in enumerate(('Car1','Car2')):
        c=load(D/'certificates'/(job+'_'+car+'.json'));assert tuple(tuple(map(F,rng)) for rng in c['root'])==tuple(root)
        assert {names[k]:v for k,v in counts.items() if v}==c['kinds'];assert radii[i]==F(c['outer_squared'])
        p1,p2=c['witnesses']; points=[]
        for w in (p1,p2):
            pt=tuple(map(F,w['xy4'])); verified=score(tuple((v,v) for v in pt));assert verified[1]<=26 and verified[1]==F(w['score_upper']);points.append(pt[2*i:2*i+2])
        l2=sqsum(*points)/4;assert l2==F(c['any_lower_squared']) and l2<=radii[i]
        assert c['row']['status_10cm']==('EXCLUDED' if l2>F(1,100) else 'CERTIFIED' if radii[i]<=F(1,100) else 'UNRESOLVED')
        assert bool(c['row']['true_feasible'])==(truthscore[1]<=26)
        assert counts['P']==c['row']['pending'] and sum(counts.values())-counts['P']==c['row']['nodes']
        assert list(map(F,c['truth_profile_bounds']))==list(truthscore)
        def verdict(limit):
            return 'EXCLUDED' if l2>limit**2 else 'CERTIFIED' if radii[i]<=limit**2 else 'UNRESOLVED'
        rows.append(dict(route='parallel',seed=rec['seed'],t=rec['epoch'],layout=rec['layout'],mode=mode,car=car,lower_cm=float(100*sqrtr(l2)[0]),upper_cm=float(100*sqrtr(radii[i])[1]),status_10cm=verdict(F(1,10)),status_20cm=verdict(F(1,5)),truth_feasible=truthscore[1]<=26,pending=counts['P'],input_hash=input_hash(rec,mode)))
    relations=[]
    if mode=='anchor_only':
        for peer,bias in BIAS.items():
            if peer=='anchor_only':
                continue
            relation='UNRESOLVED'
            proof={}
            if r[-1]-bias<=dl and du<=r[-1]+bias:
                relation='EQUAL'
                proof=dict(slants=list(map(str,(dl,du))),observation=str(r[-1]),bias=str(bias))
            else:
                candidates=load(D/'slant_candidates'/(rec['id']+'.json'))
                for car in ('Car1','Car2'):
                    cert=load(D/'certificates'/(job+'_'+car+'.json'))
                    candidates.extend(w['xy4'] for w in cert['witnesses'])
                for point in candidates:
                    box=tuple((F(v),F(v)) for v in point)
                    alo,ahi=score(box)
                    dist=cartesian_distance(box[:2],box[2:],h[0]-h[1])
                    plo=alo+residual(dist,(r[-1]-bias,r[-1]+bias))[0]/var
                    if ahi<=26<plo:
                        relation='STRICT'
                        proof=dict(xy4=point,anchor_upper=str(ahi),peer_lower=str(plo))
                        break
            relations.append(dict(seed=rec['seed'],t=rec['epoch'],layout=rec['layout'],
                                  mode=peer,relation=relation,proof=json.dumps(proof)))
    return rows,relations


def input_hash(rec,mode):
    # Includes the method alongside the complete observation record.
    return hashlib.sha256(json.dumps([rec,mode,str(BIAS[mode]),26,'1/625','1/20',150000,240],
                                     sort_keys=True,separators=(',',':')).encode()).hexdigest()


def observations():
    records=[]
    for seed in (2026112311,2026112312,2026112313):
        path=D/f'noise_{seed}.npy'
        noise=np.load(path,allow_pickle=False)
        np.testing.assert_array_equal(noise,np.random.Generator(np.random.PCG64(seed)).standard_normal((23,9))*.04)
        sha=hashlib.sha256(path.read_bytes()).hexdigest()
        base=load(D.parent.parent/'layout_peer_pilot/inputs/main_start_normal.json')['original']
        original=np.array([[float(F(v)) for v in base['anchors'][f'a{i}']] for i in range(4)])
        center=original[:,:2].mean(axis=0)
        square=original.copy()
        square[:,:2]=center+np.sign(original[:,:2]-center)*math.sqrt(np.ptp(original[:,:2],axis=0).prod())/2
        for t in (4,14):
            wave=.8*math.sin(t/6)
            xyz=np.array([[4+.65*t,3+wave,.97],[7+.60*t,-1+wave,.95]])
            for layout,a in [('original',original),('equal_area_square',square)]:
                key=f'parallel_{seed}_{t}_{layout}'
                r=load(D/'observations'/f'{key}.json')
                assert (r['id'],r['seed'],r['epoch'],r['layout'],r['split'])==(key,seed,t,layout,'parallel')
                assert r['noise_sha256']==sha and r['ids']==base['measurement_ids']
                def floats(values):
                    return np.vectorize(lambda v:float(F(v)))(values)
                np.testing.assert_array_equal(floats(r['generated_noise']),noise[t])
                np.testing.assert_array_equal(floats(r['anchors']),a)
                np.testing.assert_array_equal(floats(r['heights']),xyz[:,2])
                np.testing.assert_array_equal(floats(r['reference_xy']),xyz[:,:2].ravel())
                y=np.r_[np.linalg.norm(xyz[:,None]-a[None,:],axis=2).ravel(),np.linalg.norm(xyz[1]-xyz[0])]+noise[t]
                np.testing.assert_array_equal(floats(r['observations']),y)
                for i in range(2):
                    w=(a[:,:2]**2).sum(axis=1)+(xyz[i,2]-a[:,2])**2-y[4*i:4*i+4]**2
                    xy=np.linalg.lstsq(2*(a[1:,:2]-a[0,:2]),w[1:]-w[0],rcond=None)[0]
                    np.testing.assert_allclose(floats(r['center'][i]),xy,atol=1e-12,rtol=0)
                records.append(r)
    return records


def table(name,rows):
    import io
    stream=io.StringIO(newline='')
    w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader();w.writerows(rows)
    path=D/name
    if '--write' in sys.argv:
        path.write_text(stream.getvalue())
    else:
        assert path.read_text()==stream.getvalue(),name


if __name__=='__main__':
    if not __debug__:raise RuntimeError('run without -O')
    jobs=[(r,m) for r in observations() for m in BIAS]
    with ProcessPoolExecutor(2) as pool:
        audited=list(pool.map(verify_job,jobs))
    rows=[row for rr,_ in audited for row in rr]
    relations=[row for _,rr in audited for row in rr]
    assert len(rows)==96 and len(relations)==36
    table('rows.csv',rows)
    table('relations.csv',relations)
    print('PASS',len(jobs),'trees',len(rows),'vehicle bounds',Counter(r['relation'] for r in relations))
