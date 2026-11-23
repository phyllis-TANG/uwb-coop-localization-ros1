"""Independent breadth-first replay. No search or optimization module is imported."""
import argparse
import csv
import gzip
import json
import sys
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from functools import lru_cache
from common import CFG,HERE,PILOT,check_source,files,obs,receipt
sys.path.insert(0,str(PILOT))
from verify import cartesian_distance,residual,sqrtr

VAR=F(1,625)


def split(box):
    i=max(range(4),key=lambda j:box[j][1]-box[j][0])
    a,b=box[i]
    mid=(a+b)/2
    return [box[:i]+(pair,)+box[i+1:] for pair in [(a,mid),(mid,b)]]


class Geometry:
    def __init__(self,r):
        self.y=list(map(F,r['observations']))
        self.anchors=[tuple(map(F,a)) for a in r['anchors']]
        self.h=list(map(F,r['heights']))
        self.center=[tuple(map(F,p)) for p in r['center']]
        axes=[]
        for car,z in enumerate(self.h):
            spans=[sqrtr((self.y[4*car+i]+sqrtr(26*VAR)[1])**2-(a[2]-z)**2)[1]
                   for i,a in enumerate(self.anchors)]
            for j in (0,1):
                axes.append((max(a[j]-v for a,v in zip(self.anchors,spans)),
                             min(a[j]+v for a,v in zip(self.anchors,spans))))
        self.root=tuple(axes)

    @lru_cache(maxsize=16384)
    def anchor(self,car,box):
        total=[0,0]
        for i,a in enumerate(self.anchors):
            d=cartesian_distance(box,tuple((x,x) for x in a[:2]),self.h[car]-a[2])
            y=self.y[4*car+i]
            lo,hi=residual(d,(y,y))
            total[0]+=lo; total[1]+=hi
        return total

    def peer(self,box):
        return cartesian_distance(box[:2],box[2:],self.h[0]-self.h[1])

    def score(self,box,cm):
        a,b=self.anchor(0,box[:2]);c,d=self.anchor(1,box[2:])
        e=f=0
        if cm is not None:
            bound=F(cm,100)
            e,f=residual(self.peer(box),(self.y[8]-bound,self.y[8]+bound))
        return (a+c+e)/VAR,(b+d+f)/VAR

    def point(self,xy,cm):
        return self.score(tuple((F(v),F(v)) for v in xy),cm)


def audit_tree(key,cm,g):
    path,certs=files(key,cm)
    queue=deque([g.root])
    kept=[]
    upper=[0,0]
    tags=gzip.decompress(path.read_bytes()).decode()
    for t in tags:
        box=queue.popleft()
        if t=='S':
            queue.extend(split(box))
            continue
        lo,hi=g.score(box,cm)
        if t=='O':
            assert lo>26
            continue
        assert t in ('I','U') and (hi<=26 if t=='I' else max(b-a for a,b in box)<=F(1,20))
        kept.append(box)
        for i in (0,1):
            d=sum(max((a-v)**2,(b-v)**2) for (a,b),v in zip(box[2*i:2*i+2],g.center[i]))
            upper[i]=max(upper[i],d)
    assert not queue
    lower=[]
    for i,path in enumerate(certs):
        c=json.loads(path.read_text())
        assert c['row']['pending']==0 and c['row']['nodes']==len(tags) and c['kept_boxes']==len(kept)
        assert tuple(tuple(map(F,p)) for p in c['root'])==g.root and F(c['outer_squared'])==upper[i]
        w,z=c['witnesses']
        for point in (w,z):
            assert g.point(point['xy4'],cm)[1]==F(point['score_upper'])<=26
        l=sum((F(w['xy4'][k])-F(z['xy4'][k]))**2 for k in (2*i,2*i+1))/4
        assert F(c['any_lower_squared'])==l<=upper[i]
        lower.append(l)
    return kept,lower,upper


def equal_proof(g,leaves,cm):
    # Every N4 feasible position is in these paired boxes. Subdivide only
    # where the raw slant still extends beyond the admissible bias band.
    b=F(cm,100)
    todo=list(leaves)
    n=0
    while todo and n<150000:
        box=todo.pop()
        n+=1
        l,u=g.peer(box)
        if l>=g.y[8]-b and u<=g.y[8]+b:
            continue
        _,high=g.score(box,cm)
        if high<=26 or g.score(box,None)[0]>26:
            continue
        todo.extend(split(box))
    return not todo,n


def th(l,u,cm):
    t=F(cm,100)**2
    return 'EXCLUDED' if l>t else 'GUARANTEED' if u<=t else 'UNDETERMINED'


def one(key):
    r=obs(key)
    g=Geometry(r)
    candidates=json.loads((HERE/'exclusion_candidates.json').read_text())[key]
    anchor,l0,u0=audit_tree(key,None,g)
    envelope=[g.peer(box) for box in anchor]
    worst=max(g.y[8]-min(a for a,b in envelope),max(b for a,b in envelope)-g.y[8])
    joint=[];cars=[]
    for cm in [None,60,50,30,15,5,0]:
        if cm in CFG['new_cm']:receipt(key,cm)
        method='anchor' if cm is None else cm
        detail=dict(id=key,width_cm=method)
        equal=cm is None or worst<=F(cm,100)
        witness=None
        n=0
        if not equal:
            for p in candidates:
                a=g.point(p,None)[1]
                b=g.point(p,cm)[0]
                if a<=26<b:
                    witness=dict(xy4=p,anchor_score_upper=str(a),profiled_peer_score_lower=str(b))
                    break
            if witness is None:
                equal,n=equal_proof(g,anchor,cm)
        relation='EQUAL' if equal else 'STRICT_SUBSET' if witness else 'UNDETERMINED'
        if cm in (None,50):
            assert equal
            lows,ups=l0,u0
        else:
            _,lows,ups=audit_tree(key,cm,g)
        lo,hi=g.point(r['reference_xy'],cm)
        assert hi<=26 or lo>26
        joint.append(dict(**detail,relation=relation,truth_compatible=hi<=26,truth_score_lower=str(lo),
                          truth_score_upper=str(hi),anchor_leaf_count=len(anchor),whole_leaf_abs_residual_upper_m=str(worst),
                          refinement_boxes=n,exclusion=json.dumps(witness,separators=(',',':')) if witness else ''))
        for i,(l,u) in enumerate(zip(lows,ups)):
            cars.append(dict(**detail,car=i+1,L_cm=float(sqrtr(l)[0]*100),U_cm=float(sqrtr(u)[1]*100),
                lower_squared_m2=str(l),upper_squared_m2=str(u),status10=th(l,u,10),status20=th(l,u,20),
                min_radius_relation='EQUAL' if equal else 'STRICTLY_SMALLER' if u<l0[i] else 'UNDETERMINED',
                outer_smaller=u<u0[i],outer_decrease_cm=float(100*(sqrtr(u0[i])[1]-sqrtr(u)[1]))))
    return joint,cars


def output(name,rows,verify):
    if verify:
        with (HERE/name).open() as f:
            actual=list(csv.DictReader(f))
        expected=[{k:'' if v is None else str(v) for k,v in row.items()} for row in rows]
        if actual!=expected:
            raise ValueError('Archived table mismatch: '+name)
        return
    with (HERE/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument("--verify",action="store_true",help="compare tables without rewriting them")
    verify=parser.parse_args().verify
    check_source()
    with ProcessPoolExecutor(CFG['workers']) as pool:
        results=list(pool.map(one,CFG['inputs']))
    inputs=[r for js,_ in results for r in js]
    output('by_input.csv',inputs,verify)
    output('by_car.csv',[r for _,cs in results for r in cs],verify)
    thresholds=[]
    for k in CFG['inputs']:
        rows=[r for r in inputs if r['id']==k and isinstance(r['width_cm'],int)]
        thresholds.append(dict(id=k,narrowest_proven_redundant_cm=min((r['width_cm'] for r in rows if r['relation']=='EQUAL'),default=None),
            widest_proven_excluding_cm=max((r['width_cm'] for r in rows if r['relation']=='STRICT_SUBSET'),default=None),
            undetermined_widths_cm=','.join(str(r['width_cm']) for r in rows if r['relation']=='UNDETERMINED')))
    output('thresholds.csv',thresholds,verify)
    print('PASS: 48 trees, 56 joint rows and 112 vehicle rows, including the derived 50 cm band')
