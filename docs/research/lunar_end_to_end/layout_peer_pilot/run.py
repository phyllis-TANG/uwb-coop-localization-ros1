"""Reproduce the frozen paired pilot; source inputs and protocol are beside this file."""
import csv
import gzip
import hashlib
import inspect
import itertools
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from pathlib import Path
from time import perf_counter

os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from scipy.optimize import minimize
import upstream_solver as solver

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'
Q=26
VAR=F(1,625)
RES=F(1,20)
CAR=['Car1','Car2']
MODES={'anchor_only':('N4',F(0)), 'peer_bounded':('P4',F(3,5)), 'peer_known_zero':('P4',F(0))}
# The published solver uses 24 for 8 observations and 26 for 9. Keep the
# unmodified original beside this file; change only this explicitly paired budget.
source=inspect.getsource(solver.search)
line="q={'P4':26,'N4':24}[method]"
assert source.count(line)==1
ns=dict(vars(solver)); exec(compile(source.replace(line,'q=26'),'<common_threshold_search>','exec'),ns)
paired_search=ns['search']


def save(name,value):
    path=OUT/name; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def strings(a):
    if isinstance(a,(tuple,list,np.ndarray)):
        return [strings(x) for x in a]
    return str(F(a))


def original(name):
    return json.loads((ROOT/'inputs'/(name+'.json')).read_text())


def slants(xy,h,a):
    pts=np.c_[np.array(xy,dtype=float).reshape((2,2)), h]
    return np.r_[np.linalg.norm(pts[:,None]-a[None,:],axis=2).ravel(), np.linalg.norm(pts[1]-pts[0])]


def published(a,heights,ranges):
    # Same arithmetic and ordering as archived moon_monitor/monitor.py:fix().
    anchors=a.tolist(); hh=heights.tolist(); rr=ranges.tolist(); xy=[]
    for car,h in enumerate(hh):
        w=[p[0]**2+p[1]**2+(h-p[2])**2-rr[4*car+i]**2 for i,p in enumerate(anchors)]
        rows=[(2*(p[0]-anchors[0][0]),2*(p[1]-anchors[0][1]),v-w[0]) for p,v in zip(anchors[1:],w[1:])]
        aa=sum(x*x for x,y,z in rows);bb=sum(y*y for x,y,z in rows);ab=sum(x*y for x,y,z in rows)
        ax=sum(x*z for x,y,z in rows);by=sum(y*z for x,y,z in rows);det=aa*bb-ab*ab
        if det<=0:raise ValueError('degenerate anchor geometry')
        xy.append([(bb*ax-ab*by)/det,(aa*by-ab*ax)/det])
    return xy


def make_inputs():
    first=original('main_start_normal')['original']
    tofloat=lambda arr: np.array([float(F(x)) for x in arr])
    original_anchors=np.array([tofloat(first['anchors']['a'+str(i)]) for i in range(4)])
    c=original_anchors[:,:2].mean(axis=0); half=math.sqrt(np.prod(np.ptp(original_anchors[:,:2],axis=0)))/2
    square=original_anchors.copy();square[:,:2]=c+np.sign(square[:,:2]-c)*half
    assert np.allclose(np.prod(np.ptp(original_anchors[:,:2],axis=0)),np.prod(np.ptp(square[:,:2],axis=0)))
    records=[]
    for name,t in [('main_start_normal',0),('main_mid_normal',11)]:
        obj=original(name); x=obj['original']; xy=tofloat(obj['truth']);h=tofloat([x['heights'][car] for car in 'ps']);noise=tofloat(obj['generated_noise']);records.append(('dev',t,xy,h,noise,obj))
    rng=np.random.Generator(np.random.PCG64(2026112307));noise_track=rng.standard_normal((23,9))*.04
    synthetic=[]
    for t in range(23):
        xy=np.array((4+.65*t,4+1.2*math.sin(t/6),6+.45*t,-1+1.1*math.cos(t/5)));h=np.array((.97,.95));synthetic.append(dict(t=t,xy4=xy.tolist(),z2=h.tolist(),noise=noise_track[t].tolist()))
        if t in (4,14):records.append(('holdout',t,xy,h,noise_track[t],None))
    save('holdout_route.json',synthetic)
    for split,t,xy,h,noise,obj in records:
        for layout,a in [('original',original_anchors),('equal_area_square',square)]:
            y=slants(xy,h,a)+noise;center=published(a,h,y)
            if obj and layout=='original':
                assert strings(y)==[v for v,w in obj['original']['observations']]
                assert strings(center)==obj['center']
            k=f'{split}_{t:02d}_{layout}'
            rec=dict(id=k,split=split,epoch=t,layout=layout,anchors=strings(a),heights=strings(h),observations=strings(y),center=strings(center),reference_xy=strings(xy),generated_noise=strings(noise),ids=first['measurement_ids'])
            save('observations/'+k+'.json',rec)
            yield rec


def model_for(rec,mode):
    method,b=MODES[mode]
    return dict(anchors=rec['anchors'],heights=rec['heights'],ranges=rec['observations'],measurement_ids=rec['ids'],variance=[str(VAR)]*9,bias=[str(-b),str(b)])


def event_root(m):
    # Each nonnegative contribution is bounded by the total 26. Intersect the
    # per-anchor horizontal coordinate bounds, exactly as height_v1:event_root.
    slack=solver.sqrt_bounds(Q*VAR)[1]; out=[]
    for car,h in enumerate(map(F,m['heights'])):
        constraints=[[],[]]
        for i,anchor in enumerate(m['anchors']):
            x,y,z=map(F,anchor); cap=F(m['ranges'][4*car+i])+slack
            if cap<abs(h-z):return None
            radius=solver.sqrt_bounds(cap*cap-(h-z)**2)[1]
            for axis,v in enumerate((x,y)): constraints[axis].append((v-radius,v+radius))
        for rng in constraints:
            lo=max(x for x,y in rng);hi=min(y for x,y in rng)
            if hi<lo:return None
            out.append((lo,hi))
    return out


def float_model(m,method):
    arr=lambda ss: np.asarray([float(F(v)) for v in ss]);a=np.array([arr(p) for p in m['anchors']]); h=arr(m['heights']);y=arr(m['ranges']);b=float(F(m['bias'][1]));
    def evaluate(x):
        p=np.asarray(x).reshape(2,2); gap=p[:,None,:]-a[None,:,:2]
        anchor_d=np.sqrt(np.sum(gap**2,axis=2)+(h[:,None]-a[None,:,2])**2)
        resid=anchor_d-y[:8].reshape(2,4)
        value=np.sum(resid**2);grad=2*np.sum((resid/anchor_d)[:,:,None]*gap,axis=1)
        if method=='P4':
            v=p[0]-p[1];distance=math.sqrt(v@v+(h[0]-h[1])**2);r=distance-y[8];r=math.copysign(max(0,abs(r)-b),r)
            value+=r*r;dg=2*r*v/max(distance,1e-12);grad[0]+=dg;grad[1]-=dg
        return value/.04**2,grad.ravel()/.04**2
    return evaluate


def exact_pair(m,method,center):
    evaluate=float_model(m,method); exact=solver.evaluator(m,method)
    start=np.array([float(F(x)) for c in center for x in c]);opt=minimize(evaluate,start,jac=True,method='BFGS',options={'gtol':1e-8,'maxiter':100});x0=opt.x
    constraint={'type':'ineq','fun':lambda x:26-1e-5-evaluate(x)[0], 'jac':lambda x:-evaluate(x)[1]}
    out=[]
    for car in range(2):
        pts=[]
        for theta in np.arange(24)*2*np.pi/24:
            direction=np.zeros(4);direction[2*car:2*car+2]=[np.cos(theta),np.sin(theta)]
            p=minimize(lambda x:-direction@x,x0,jac=lambda x:-direction,constraints=[constraint],method='SLSQP',options={'ftol':1e-11,'maxiter':100})
            point=tuple(F(v) for v in p.x);_,score=exact(tuple((v,v) for v in point))
            if score<=26:pts.append((point,score))
        if len(pts)<2:raise RuntimeError('two valid witnesses not found')
        def sqdist(pair):return sum((pair[0][0][i]-pair[1][0][i])**2 for i in range(2*car,2*car+2))
        pair=max(itertools.combinations(pts,2),key=sqdist);l2=sqdist(pair)/4
        out.append((l2,[dict(xy4=strings(row[0]),score_upper=str(row[1])) for row in pair]))
    return out


def run_job(args):
    rec,mode=args; job=rec['id']+'_'+mode;start=perf_counter(); m=model_for(rec,mode);method,_=MODES[mode]
    root=event_root(m); center=[[F(z) for z in c] for c in rec['center']]; ev=solver.evaluator(m,method)
    truth=tuple(F(z) for z in rec['reference_xy']); truth_score=ev(tuple((v,v) for v in truth)); assert root is not None
    tree=paired_search(m,method,root,150000,240,RES)
    nodes=tree['nodes']; kept=[n for n in nodes if n['kind'] in ('INSIDE','UNDECIDED','PENDING')];assert kept
    def rects(car):return {tuple((F(x),F(y)) for x,y in n['box'][2*car:2*car+2]) for n in kept}
    rectangles=[rects(0),rects(1)];bounds=[]
    for c,rr in zip(center,rectangles):
        radial_squared=lambda intervals: sum(max((l-v)**2,(u-v)**2) for v,(l,u) in zip(c,intervals))
        top=max(rr,key=radial_squared);bounds.append(radial_squared(top))
    dist_enclosure=None;redundant=None
    if mode=='anchor_only':
        # Dropping the pairings (Cartesian product of the two coordinate AABBs)
        # gives a conservative superset of all included joint leaf boxes.
        boxes=[tuple((min(b[i][0] for b in rr),max(b[i][1] for b in rr)) for i in range(2)) for rr in rectangles]
        dlo,dhi=solver.distance(boxes[0],boxes[1],F(rec['heights'][0])-F(rec['heights'][1]));dist_enclosure=strings([dlo,dhi]); yr=F(rec['observations'][8]);redundant=bool(dlo>=yr-F(3,5) and dhi<=yr+F(3,5))
    proof=exact_pair(m,method,rec['center']);rows=[]
    for car,(lower2,pts) in enumerate(proof):
        upper2=bounds[car];assert lower2<=upper2
        low=solver.sqrt_bounds(lower2)[0];high=solver.sqrt_bounds(upper2)[1]
        state='EXCLUDED' if lower2>F(1,100) else ('CERTIFIED' if upper2<=F(1,100) else 'UNRESOLVED')
        p=dict(split=rec['split'],epoch=rec['epoch'],layout=rec['layout'],mode=mode,car=CAR[car],lower_cm=float(low*100),upper_cm=float(high*100),status_10cm=state,true_feasible=truth_score[1]<=26,true_score=float(truth_score[1]),pending=len(tree['queue']),nodes=tree['processed'],redundant_60cm=redundant)
        rows.append(p);save('certificates/'+job+'_'+CAR[car]+'.json',dict(row=p,any_lower_squared=str(lower2),outer_squared=str(upper2),witnesses=pts,truth_profile_bounds=strings(truth_score),anchor_only_peer_distance_interval=dist_enclosure,kept_boxes=len(kept),kinds=tree['counts'],root=strings(root)))
    # Compact full binary-tree decisions; exact boxes can be reconstructed from
    # the root and deterministic maximum-width split, by breadth-first replay.
    path=OUT/'trees'/(job+'.gz');path.parent.mkdir(exist_ok=True);tags={'SPLIT':b'S','OUTSIDE':b'O','INSIDE':b'I','UNDECIDED':b'U','PENDING':b'P'}
    path.write_bytes(gzip.compress(b''.join(tags[x['kind']] for x in nodes),mtime=0))
    print(job,'nodes',tree['processed'],'pending',len(tree['queue']),'seconds',round(perf_counter()-start,2),flush=True)
    return rows


def main():
    inputs=list(make_inputs());jobs=[(r,mode) for r in inputs for mode in MODES];workers=min(int(sys.argv[1]) if len(sys.argv)>1 else 4,len(jobs));print('paired pilot jobs',len(jobs),'workers',workers,flush=True)
    with ProcessPoolExecutor(workers) as pool: nested=list(pool.map(run_job,jobs,chunksize=1))
    rows=[row for pair in nested for row in pair];
    with (OUT/'rows.csv').open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=rows[0].keys());wr.writeheader();wr.writerows(rows)
    print('complete',len(rows),flush=True)


if __name__=='__main__':main()
