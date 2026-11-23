"""Independent exact replay of every compressed search tree, witness and result.

This verifier imports neither run.py nor its solver. It rebuilds global roots from
raw observations, reconstructs the complete partition, and independently checks
the bound authorizing every discard. Quantities for thresholds use fractions.
"""
import csv
import gzip
import json
import math
import hashlib
import sys
from collections import Counter,deque
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

D=Path(__file__).resolve().parent/'results'
MODES={'anchor_only':None,'peer_60':F(3,5),'peer_15':F(3,20),'peer_05':F(1,20)}

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
    peer_bias=MODES[mode]
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
    assert not queue
    tf=tuple(F(x) for x in rec['reference_xy']);truthscore=score(tuple((x,x) for x in tf));assert truthscore[1]<=26 or truthscore[0]>26
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

        key = (rec['id'],mode,car)
        row = TABLE[key]
        for k,v in c['row'].items():
            assert row[k]==('' if v is None else str(v))
        assert row['lower_cm']==str(float(100*sqrtr(l2)[0]))
        assert row['upper_cm']==str(float(100*sqrtr(radii[i])[1]))
        assert row['status_20cm']==('EXCLUDED' if l2>F(1,25) else 'CERTIFIED' if radii[i]<=F(1,25) else 'UNRESOLVED')
        assert row['truth_feasible']==str(truthscore[1]<=26)
        assert list(map(F,c['truth_profile_bounds']))==list(truthscore)
        assert int(row['pending'])==counts['P'] and int(row['nodes'])==len(tree)-counts['P']
        assert row['route']==rec['route'] and int(row['seed'])==rec['seed'] and int(row['t'])==rec['epoch']
        assert float(row['true_peer_m'])==rec['true_peer_m']
        assert row['input_hash']==hashlib.sha256((D/'observations'/(rec['id']+'.json')).read_bytes()).hexdigest()
    if mode!='anchor_only':
        return []
    proofs=[]
    candidates=load(D/'peer_witnesses'/(rec['id']+'.json'))
    for m,b in list(MODES.items())[1:]:
        status='未定'
        witness=''
        anchor_upper=joint_lower=''
        if dl>=r[-1]-b and du<=r[-1]+b:
            status='已证相同'
        for index,point in enumerate(candidates):
            box=tuple((F(x),F(x)) for x in point)
            lo,hi=score(box)
            d=cartesian_distance(box[:2],box[2:],h[0]-h[1])
            lower=lo+residual(d,(r[-1]-b,r[-1]+b))[0]/var
            if hi<=26<lower:
                assert status!='已证相同'
                status='已证缩小'
                witness=f"peer_witnesses/{rec['id']}.json#{index}"
                anchor_upper=str(hi)
                joint_lower=str(lower)
                break
        proofs.append(dict(seed=rec['seed'],t=rec['epoch'],layout=rec['layout'],mode=m,
                           true_peer_m=rec['true_peer_m'],status=status,anchor_slant_lo=str(dl),
                           anchor_slant_hi=str(du),peer_obs=str(r[-1]),bias_halfwidth=str(b),
                           witness=witness,anchor_score_upper=anchor_upper,peer_score_lower=joint_lower))
    return proofs


def compare_file(name,rows):
    import io
    buf=io.StringIO(newline='')
    w=csv.DictWriter(buf,fieldnames=rows[0])
    w.writeheader()
    w.writerows(rows)
    data=buf.getvalue().replace('\r\n','\n')
    path=D/name
    if '--write' in sys.argv:
        path.write_text(data)
    else:
        assert data==path.read_text(),name


def radius_comparisons(records):
    """Compare exact squared bounds. Report conservative integer hundredths of cm."""
    def bounds(row):
        key=f"{row['seed']}_{int(row['t']):02d}_{row['layout']}_{row['mode']}_{row['car']}"
        cert=load(D/'certificates'/(key+'.json'))
        return F(cert['any_lower_squared']),F(cert['outer_squared'])
    for row in records:
        key=(row['seed'],row['t'],row['car'])
        for other in records:
            if (other['seed'],other['t'],other['car'])!=key:
                continue
            layout_pair=(row['layout']=='original' and other['layout']=='equal_area_square' and row['mode']==other['mode'])
            peer_pair=(row['layout']==other['layout'] and row['mode']=='anchor_only' and other['mode']!='anchor_only')
            if not (layout_pair or peer_pair):
                continue
            lower,upper=bounds(row)
            other_lower,other_upper=bounds(other)
            delta=sqrtr(lower)[0]-sqrtr(other_upper)[1]
            status='已证缩小' if lower>other_upper else '未证缩小'
            yield dict(seed=key[0],t=key[1],car=key[2],old_layout=row['layout'],new_layout=other['layout'],
                       old_mode=row['mode'],new_mode=other['mode'],old_lower_squared_m2=str(lower),
                       new_upper_squared_m2=str(other_upper),status=status,
                       minimum_decrease_cm=f'{(delta*10000//1)/100:.2f}' if status=='已证缩小' else '')


def init_table(table):
    global TABLE
    TABLE=table


if __name__=='__main__':
    obs=[load(p) for p in sorted((D/'observations').glob('*.json'))]
    expected={f'{seed}_{t:02d}_{layout}' for seed in range(2026112311,2026112314)
              for t in (4,14) for layout in ('original','equal_area_square')}
    assert {r['id'] for r in obs}==expected and len(obs)==12
    with (D/'rows.csv').open() as f:
        rows=list(csv.DictReader(f))
    TABLE={(f"{r['seed']}_{int(r['t']):02d}_{r['layout']}",r['mode'],r['car']):r for r in rows}
    assert len(TABLE)==len(rows)==96
    with ProcessPoolExecutor(2,initializer=init_table,initargs=(TABLE,)) as pool:
        comparisons=[p for group in pool.map(verify_job,[(r,m) for r in obs for m in MODES]) for p in group]
    compare_file('sets.csv',comparisons)
    compare_file('radius_comparisons.csv',list(radius_comparisons(rows)))
    print('PASS 48 trees, 96 car rows, 192 joint witnesses, 36 peer comparisons',Counter(x['status'] for x in comparisons))
