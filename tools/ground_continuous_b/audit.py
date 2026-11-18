"""Offline replay of the ground enclosures using independent integer expressions."""
import csv
import gzip
import json
import math
import sys
from fractions import Fraction
from timeline import DOC,load,csvout
from a_interface import identity,module

def ends(x):
    v=Fraction(x)*10**6
    return math.floor(v),math.ceil(v)

def sqbounds(a,b):
    lo=hi=0
    for (l,u),(v,w) in zip(a,b):
        lo+=max(l-w,v-u,0)**2
        hi+=max((l-w)**2,(u-v)**2)
    return math.isqrt(lo),1+math.isqrt(hi-1) if hi else 0

def penalty(box,other,y):
    lo,hi=sqbounds(box,other)
    return max(y[0]-hi,lo-y[1],0)**2

def validate(r,*,sigma_um=40000,bias_um=600000,cell_um=50000):
    obs=r['obs']; cert=r['region']; limit=26*sigma_um**2
    anchors=[[ends(x) for x in a] for a in obs['anchors']]
    heights=list(map(ends,obs['heights']));meas=list(map(ends,obs['ranges']))
    losses=[]
    for c in (0,1):
        samples=meas[c*4:c*4+4]
        roots=[]
        for axis in (0,1):
            lows=[];highs=[]
            for a,y in zip(anchors,samples):
                radius=y[1]+math.isqrt(limit-1)+1
                lows.append(a[axis][0]-radius);highs.append(a[axis][1]+radius)
            roots.append([max(lows),min(highs)])
        assert cert['roots'][c]==roots
        leaves={};queue=[roots]
        while queue:
            b=queue.pop()
            if any(l>u for l,u in b):continue
            loss=sum(penalty(b+[heights[c]],a,y) for a,y in zip(anchors,samples))
            if loss>limit:continue
            widths=[u-l for l,u in b]
            if max(widths)<=cell_um:
                leaves[tuple(map(tuple,b))]=loss
            else:
                k=widths.index(max(widths));l,u=b[k];mid=(l+u)//2
                for half in ([l,mid],[mid,u]):queue.append(b[:k]+[half]+b[k+1:])
        stored=cert['cells'][c]
        assert len(stored)==len(leaves) and {tuple(map(tuple,b)):v for b,v in stored}==leaves
        losses.append(stored)
    peer=[meas[-1][0]-bias_um,meas[-1][1]+bias_um]
    expected={}
    for i,(p,lp) in enumerate(losses[0]):
        ok=[j for j,(s,ls) in enumerate(losses[1]) if lp+ls<=limit and lp+ls+penalty(p+[heights[0]],s+[heights[1]],peer)<=limit]
        if ok:expected[i]=ok
    assert cert['joint']==[[i,v] for i,v in expected.items()]

def audit(seed,scene):
    path=DOC/'runs'/f'{seed}_{scene}'
    records=load(path/'records.json.gz');truth=load(path/'truth.json.gz')
    old={}
    if seed==101 and scene in ('nominal','wall'):
        oldpath=DOC.parent/'cooperative_integrity_baselines_20261029/results/declarations.csv.gz'
        with gzip.open(oldpath,'rt') as f:
            for v in csv.DictReader(f):
                if v['profile']=='B2_local|scale=1.0|a=0.01' and v['scenario']==('nominal' if scene=='nominal' else 'car1_common_wall_bias'):
                    old[(int(float(v['t_s'])),v['car'])]=v
        assert len(old)==126
    report=[]
    for r in records:
        validate(r)
        t=r['t'];obs=r['obs'];reg=r['region']
        xyz=[[*p,h] for p,h in zip(truth[20*t],obs['heights'])]
        expected=[math.dist(p,a) for p in xyz for a in obs['anchors']]+[math.dist(*xyz)]
        bias=min(.6,max(-.6,obs['ranges'][-1]-expected[-1]))
        stat=sum(((v-y-b)/.04)**2 for v,y,b in zip(obs['ranges'],expected,[0]*8+[bias]))
        contains=[]
        for c,xy in enumerate(truth[20*t]):
            contains.append({i for i,(b,_) in enumerate(reg['cells'][c]) if all(l<=Fraction(x)*10**6<=u for (l,u),x in zip(b,xy))})
            if old:
                base=old[t,'car'+str(c+1)]
                for k in ('computable','alarm','available'):assert str(r['b2'][c][k])==base[k]
                assert abs(math.dist(xy,r['xy'][c])-float(base['xy_error_m']))<1e-7
        joint=any(i in contains[0] and contains[1].intersection(js) for i,js in reg['joint'])
        assert stat>26 or joint
        report.append(dict(state_s=t,hash=identity(obs),joint_profile_stat=stat,reference_exact_event=stat<=26,reference_joint_outer=joint,ground_certificate_readback='PASS',old_baseline_matches_cars=2 if old else ''))
    csvout(path/'audit.csv',report)
if __name__=='__main__':audit(int(sys.argv[1]),sys.argv[2])
