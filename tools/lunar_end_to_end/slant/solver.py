"""Single-epoch search with exact rational boxes and outward integer square roots."""
import time
from collections import Counter, deque
from fractions import Fraction as F
from functools import lru_cache
from math import isqrt

SCALE=10**30

def sqrt_bounds(x):
    k=isqrt(x.numerator*SCALE*SCALE//x.denominator)
    lo=F(k,SCALE)
    return lo,lo if lo*lo==x else F(k+1,SCALE)

def point(x):
    x=F(x)
    return x,x

def distance(left,right,dz):
    low=high=dz*dz
    for (a,b),(c,d) in zip(left,right):
        l,u=a-d,b-c
        low+=max(0,l,-u)**2
        high+=max(abs(l),abs(u))**2
    return sqrt_bounds(low)[0],sqrt_bounds(high)[1]

def gap(distance_bounds,observation):
    l,u=distance_bounds
    a,b=observation
    return max(0,a-u,l-b)**2,max(0,a-l,u-b)**2

def evaluator(model,method):
    if method not in ('P4','N4'):raise ValueError(method)
    if set(model)!={'anchors','heights','ranges','measurement_ids','variance','bias'}:raise ValueError('invalid solver fields')
    anchors=[[F(x) for x in a] for a in model['anchors']]
    heights=list(map(F,model['heights']))
    ranges=list(map(F,model['ranges'][:8 if method=='N4' else 9]))
    variances=list(map(F,model['variance'][:len(ranges)]))
    @lru_cache(maxsize=8192)
    def anchor_sum(box,c):
        bounds.distance_evaluations+=4
        lo=hi=0
        for k,(x,y,z) in enumerate(anchors):
            i=4*c+k
            a,b=gap(distance(box,(point(x),point(y)),heights[c]-z),point(ranges[i]))
            lo+=a/variances[i];hi+=b/variances[i]
        return lo,hi
    def bounds(box):
        a,b=anchor_sum(box[:2],0);c,d=anchor_sum(box[2:],1)
        if method=='N4':return a+c,b+d
        bounds.distance_evaluations+=1
        beta0,beta1=map(F,model['bias'])
        l,u=gap(distance(box[:2],box[2:],heights[0]-heights[1]),(ranges[8]-beta1,ranges[8]-beta0))
        return a+c+l/variances[8],b+d+u/variances[8]
    bounds.distance_evaluations=0
    return bounds

def search(model,method,domain,max_boxes=50000,max_seconds=30):
    bounds=evaluator(model,method)
    q={'P4':26,'N4':24}[method]
    queue=deque([('',tuple(tuple(map(F,v)) for v in domain))])
    start=time.monotonic();nodes=[];processed=0
    while queue and processed<max_boxes and time.monotonic()-start<max_seconds:
        path,box=queue.popleft();processed+=1
        lo,hi=bounds(box)
        widths=[b-a for a,b in box];axis=widths.index(max(widths))
        node=dict(id=path,box=[[str(a),str(b)] for a,b in box])
        if lo>q:kind='OUTSIDE'
        elif hi<=q:kind='INSIDE'
        elif widths[axis]<=F(1,20):kind='UNDECIDED'
        else:
            kind='SPLIT';a,b=box[axis];mid=(a+b)/2
            node.update(axis=axis,cut=str(mid),children=[path+'0',path+'1'])
            for suffix,pair in [('0',(a,mid)),('1',(mid,b))]:
                queue.append((path+suffix,box[:axis]+(pair,)+box[axis+1:]))
        node['kind']=kind;nodes.append(node)
    pending=[path for path,_ in queue]
    nodes.extend(dict(id=path,kind='PENDING',box=[[str(a),str(b)] for a,b in box]) for path,box in queue)
    return dict(root='',nodes=nodes,queue=pending,processed=processed,counts=dict(Counter(n['kind'] for n in nodes)),distance_evaluations=bounds.distance_evaluations,search_seconds=time.monotonic()-start)
