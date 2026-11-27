"""Single-epoch horizontal radius bounds allowing a separate offset on each range."""
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path
import csv
import hashlib
import itertools
import json

import numpy as np
from scipy.optimize import minimize
from upstream_solver import sqrt_bounds, distance, gap, point

BASE = Path(__file__).resolve().parent
INPUT = BASE / "observation.json"
A = json.loads(INPUT.read_text())
ANCHORS = [tuple(map(F,a)) for a in A["anchors"]]
H = tuple(map(F,A["heights"]))
Y = tuple(map(F,A["observations"]))
C = tuple(F(v) for row in A["center"] for v in row)
Q = 26
SIGMA = F(1,25)
PEER = F(1,20)
RESOLUTION = F(1,20)
# Common slant-range data / published centres for all allowances.
def bounding_root(allow):
    out = []
    for j,h in enumerate(H):
        xy=[[],[]]
        for a,y in zip(ANCHORS,Y[4*j:4*j+4]):
            cap = y + allow + sqrt_bounds(Q*SIGMA**2)[1]
            radius = sqrt_bounds(cap**2-(h-a[2])**2)[1]
            for axis in range(2):
                xy[axis].append((a[axis]-radius,a[axis]+radius))
        out.extend((max(v[0] for v in spans),min(v[1] for v in spans)) for spans in xy)
    return tuple(out)

def evaluate_bounds(allow):
    @lru_cache(maxsize=65536)
    def anchors(box,j):
        lo=hi=0
        for k,(x,y,z) in enumerate(ANCHORS):
            obs=Y[4*j+k]
            dl=distance(box,(point(x),point(y)),H[j]-z)
            l,u=gap(dl,(obs-allow,obs+allow))
            lo+=l; hi+=u
        return lo,hi
    def cost(box):
        a,b=anchors(box[:2],0)
        c,d=anchors(box[2:],1)
        e,g=gap(distance(box[:2],box[2:],H[0]-H[1]),(Y[8]-PEER,Y[8]+PEER))
        return (a+c+e)/SIGMA**2,(b+d+g)/SIGMA**2
    return cost

def outer(allow,cost):
    stack=[bounding_root(allow)]
    extreme=[F(0),F(0)]
    visited=0
    while stack:
        box=stack.pop()
        visited+=1
        l,u=cost(box)
        if l>Q:
            continue
        widths=[b-a for a,b in box]
        ax=widths.index(max(widths))
        if u<=Q or widths[ax]<=RESOLUTION:
            for j in range(2):
                r2=sum(max(abs(a-C[k]),abs(b-C[k]))**2 for k,(a,b) in enumerate(box) if 2*j<=k<2*j+2)
                extreme[j]=max(extreme[j],r2)
            continue
        a,b=box[ax]; mid=(a+b)/2
        stack.extend(box[:ax]+(i,)+box[ax+1:] for i in ((a,mid),(mid,b)))
    return extreme, visited

def witnesses(allow,exact_cost):
    a=np.array(ANCHORS,dtype=float); heights=np.array(H,dtype=float)
    obs=np.array(Y,dtype=float); centre=np.array(C,dtype=float)
    tol=np.array([float(allow)]*8+[float(PEER)])
    def value_grad(x):
        p=x.reshape(2,2)
        v=p[:,None,:]-a[None,:,:2]
        sl=np.sqrt((v**2).sum(axis=2)+(heights[:,None]-a[None,:,2])**2)
        pd=p[0]-p[1]; d=np.sqrt(pd@pd+(heights[0]-heights[1])**2)
        raw=np.r_[sl.ravel(),d]-obs
        r=np.sign(raw)*np.maximum(0.,np.abs(raw)-tol)
        grad=2*np.sum((r[:8].reshape(2,4)/sl)[:,:,None]*v,axis=1)
        grad[0]+=2*r[8]*pd/d; grad[1]-=2*r[8]*pd/d
        return r@r/float(SIGMA)**2,grad.ravel()/float(SIGMA)**2
    start=minimize(value_grad,centre,jac=True,method="BFGS").x
    con={"type":"ineq","fun":lambda x:Q-1e-5-value_grad(x)[0],"jac":lambda x:-value_grad(x)[1]}
    out=[]
    for j in range(2):
        pts=[]
        for th in 2*np.pi*np.arange(24)/24:
            direction=np.zeros(4); direction[2*j:2*j+2]=[np.cos(th),np.sin(th)]
            opt=minimize(lambda x:-direction@x,start,jac=lambda x:-direction,constraints=[con],method="SLSQP",options={"ftol":1e-10,"maxiter":150})
            pos=tuple(F(v) for v in opt.x)
            _,hi=exact_cost(tuple((v,v) for v in pos))
            if hi<=Q:
                pts.append(pos)
        def d2(pair):
            u,v=pair
            return sum((u[k]-v[k])**2 for k in (2*j,2*j+1))
        pair=max(itertools.combinations(pts,2),key=d2)
        out.append((d2(pair)/4,max(d2((p,C)) for p in pts),pair))
    return out

def run():
    rows=[]; saved=[]
    for allow in (F(0),F(1,50),F(1,20)):
        cost=evaluate_bounds(allow)
        bound,vis=outer(allow,cost)
        for j,(lb,atc,pair) in enumerate(witnesses(allow,cost)):
            assert lb<=bound[j] and atc<=bound[j]
            verdict="excluded_all_centres" if lb>F(1,25) else "certified_reported_centre" if bound[j]<=F(1,25) else "unresolved"
            record=dict(anchor_allowance_cm=float(100*allow),robot=j+1,lower_cm=100*float(sqrt_bounds(lb)[0]),reported_centre_witness_cm=100*float(sqrt_bounds(atc)[0]),upper_cm=100*float(sqrt_bounds(bound[j])[1]),decision_20cm=verdict,processed_boxes=vis)
            rows.append(record)
            saved.append(dict(anchor_allowance=str(allow),robot=j+1,checked_squared_lower_m2=str(lb),enclosing_squared_upper_m2=str(bound[j]),witnesses=[[str(f) for f in p] for p in pair]))
    with (BASE/'bounds.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    (BASE/'certificates.json').write_text(json.dumps(saved,indent=2)+'\n')
    for r in rows: print(r)
if __name__=='__main__':run()
