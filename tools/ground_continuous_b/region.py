"""Integer micrometre enclosure for the projected nine-range consistency region."""
from math import isqrt
from fractions import Fraction

U=1_000_000
SIGMA=40000
LIMIT=26*SIGMA**2
CELL=50000

def enclosure(v):
    q=Fraction(float(v))*U
    return q.numerator//q.denominator,-(-q.numerator//q.denominator)

def sqrt_up(v):
    k=isqrt(v)
    return k+int(k*k<v)

def range_interval(box,other,z,h):
    low=high=0
    for (a,b),(c,d) in zip((*box,z),(*other,h)):
        l,u=a-d,b-c
        low+=max(0,l,-u)**2
        high+=max(abs(l),abs(u))**2
    return isqrt(low),sqrt_up(high)

def gap(a,b):
    return max(0,a[0]-b[1],b[0]-a[1])

def anchor_cells(anchors,height,ranges):
    # |horizontal offset| <= slant <= measured upper + ceil(sqrt(26)*sigma).
    radial=[r[1]+sqrt_up(LIMIT) for r in ranges]
    root=tuple((max(a[k][0]-d for a,d in zip(anchors,radial)),min(a[k][1]+d for a,d in zip(anchors,radial))) for k in (0,1))
    stack=[root];cells=[];visited=0
    while stack:
        box=stack.pop();visited+=1
        if any(a>b for a,b in box):continue
        lower=sum(gap(range_interval(box,a[:2],height,a[2]),y)**2 for a,y in zip(anchors,ranges))
        if lower>LIMIT:continue
        axis=max((0,1),key=lambda j:box[j][1]-box[j][0])
        l,u=box[axis]
        if u-l<=CELL:
            cells.append((box,lower));continue
        mid=(l+u)//2
        for interval in [(l,mid),(mid,u)]:stack.append(box[:axis]+(interval,)+box[axis+1:])
    return root,cells,visited

def solve(obs,published):
    anchors=[[enclosure(x) for x in xyz] for xyz in obs['anchors']]
    heights=list(map(enclosure,obs['heights']))
    ranges=list(map(enclosure,obs['ranges']))
    car=[anchor_cells(anchors,h,ranges[4*i:4*i+4]) for i,h in enumerate(heights)]
    target=(ranges[8][0]-600000,ranges[8][1]+600000)
    kept=[set(),set()];pairs=[]
    for i,(p,lp) in enumerate(car[0][1]):
        matched=[]
        for j,(s,ls) in enumerate(car[1][1]):
            if lp+ls>LIMIT:continue
            if lp+ls+gap(range_interval(p,s,*heights),target)**2<=LIMIT:
                kept[0].add(i);kept[1].add(j);matched.append(j)
        if matched:pairs.append([i,matched])
    pl=[]
    for i,indices in enumerate(kept):
        ref=list(map(enclosure,published[i]))
        corners=[sum(max(abs(l-b),abs(u-a))**2 for (l,u),(a,b) in zip(car[i][1][j][0],ref)) for j in indices]
        pl.append(sqrt_up(max(corners))/U if corners else None)
    return dict(unit='um',roots=[r[0] for r in car],cells=[r[1] for r in car],visited=[r[2] for r in car],joint=pairs,pl=pl)
