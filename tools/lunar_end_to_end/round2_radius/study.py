"""Moon_1 independent one-factor radius contrasts and exact point certificates."""
import csv
import gzip
import json
import math
import sys
import tempfile
from fractions import Fraction as F
from pathlib import Path
from itertools import combinations, product
from functools import lru_cache

HERE=Path(__file__).resolve()
sys.path.insert(0,str(HERE.parents[1]/'radius_resolution'))
import run as prior
D=prior.D.parent/'round2_radius'
PLAN=json.loads((D/'plan.json').read_text())
BASE=prior.D
review=prior.module('review',prior.ROOT/'docs/research/midterm_sim_review/round1/moon/moon_certified_radius.py')


def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)


def digest(obj):
    import hashlib
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def write_csv(path,rows):
    with path.open('w') as f:
        writer=csv.DictWriter(f,rows[0],lineterminator='\n')
        writer.writeheader();writer.writerows(rows)


def slants(x,xy):
    from solver import distance,point
    fixed=[tuple(point(v) for v in xy[i:i+2]) for i in (0,2)]
    heights=[F(x['heights'][car]) for car in 'ps']
    ds=[]
    for i,pos in enumerate(fixed):
        for k in range(4):
            a,b,z=x['anchors']['a'+str(k)]
            ds.append(distance(pos,(point(a),point(b)),heights[i]-F(z)))
    return ds+[distance(*fixed,heights[0]-heights[1])]


def score(x,xy,profile=False):
    terms=[]
    for i,((lo,hi),(v,_),var) in enumerate(zip(slants(x,xy),x['observations'],x['variance'])):
        target=F(v)
        l=u=target
        if i==8 and profile:
            l-=F(x['bias_domain'][1]);u-=F(x['bias_domain'][0])
        low=max(0,l-hi,lo-u)
        high=max(0,l-lo,hi-u)
        terms.append([str(low**2/F(var)),str(high**2/F(var))])
    return terms


def upper(terms):return sum(F(hi) for _,hi in terms)


def immutable_inputs():
    import numpy as np
    ev={e['case']:e for e in prior.old('events.json')}
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp)/'tools/lunar_end_to_end/moon_monitor/monitor.py';p.parent.mkdir(parents=True);p.write_bytes(prior.blob(prior.P['archive'],'tools/lunar_end_to_end/moon_monitor/monitor.py'))
        fix=prior.module('published',p).fix
    for name,i in zip(PLAN['cases'],PLAN['source_indices']):
        source=read(BASE/'results'/name/'fine_matched.json.gz')['original']
        e=ev[name];assert e['i']==i
        folder='continuous' if name.startswith('main') else 'replication'
        rec=next(v for v in read(BASE.parent/folder/'INPUTS.json.gz') if v['reference']['seed']==PLAN['seed'] and v['reference']['condition']=='normal')
        ref=rec['reference'];o=rec['observation'];pts=np.asarray(ref['xyz'][i]);anc=np.asarray(o['anchors']);noise=np.asarray(ref['range_noise'][i])
        pure=np.r_[np.linalg.norm(pts[:,None]-anc[None,:],axis=2).ravel(),np.linalg.norm(pts[1]-pts[0])]
        assert np.array_equal(pure+noise,o['ranges'][i]) and ref['bias'][i]==0
        assert [F(t[0]) for t in source['observations']]==list(map(F,o['ranges'][i]))
        truth=[str(F(v)) for car in pts for v in car[:2]]
        for variant,params in PLAN['variants'].items():
            x=dict(source,bias_domain=params['bias'],variance=[params['variance']]*9)
            center=e['published_xy']
            if variant=='matched':
                y=(pure+noise/2).tolist()
                x['observations']=[[str(F(v))]*2 for v in y]
                center=fix(o['anchors'],o['heights'][i],y)
            del x['input_hash'];x['input_hash']=digest(x)
            write(D/'inputs'/variant/(name+'.json'),dict(original=x,center=center,truth=truth,generated_noise=[str(F(v)/(2 if variant=='matched' else 1)) for v in noise]))


def witness(name):
    import numpy as np
    x=read(D/'inputs/zero'/(name+'.json'))['original']
    tree=read(BASE/'results'/name/'fine_matched.json.gz')['certificate']
    nodes=[n for n in tree['nodes'] if n['kind']=='INSIDE']
    @lru_cache(None)
    def mid(a,b):return (F(a)+F(b))/2
    mids=[[mid(*ab) for ab in n['box']] for n in nodes]
    xy=np.asarray(mids,dtype=float).reshape(-1,2,2)
    h=np.array([float(F(x['heights'][c])) for c in 'ps'])
    xyz=np.concatenate((xy,np.broadcast_to(h,(len(xy),2))[:,:,None]),axis=2)
    anchors=np.array([[float(F(v)) for v in x['anchors'][f'a{k}']] for k in range(4)])
    ranges=np.c_[np.linalg.norm(xyz[:,:,None]-anchors,axis=3).reshape(-1,8),np.linalg.norm(xyz[:,0]-xyz[:,1],axis=1)]
    good=np.flatnonzero(np.sum((ranges-[float(F(a)) for a,b in x['observations']])**2,axis=1)<26*.04**2)
    out={}
    for j,car in enumerate('ps'):
        cloud=xy[good,j];indices=set()
        for angle in np.arange(96)*math.pi/96:
            proj=cloud@np.array([math.cos(angle),math.sin(angle)])
            indices.update((good[proj.argmin()],good[proj.argmax()]))
        verified={}
        for k in indices:
            pt=mids[k];terms=score(x,pt)
            if upper(terms)<=26:verified[k]=dict(leaf=nodes[k]['id'],xy4=list(map(str,pt)),terms=terms,upper=str(upper(terms)))
        dist=lambda k,l:sum((mids[k][a]-mids[l][a])**2 for a in (2*j,2*j+1))
        d,k,l=max((dist(k,l),k,l) for k,l in combinations(verified,2))
        assert d>F(1,25)
        out[car]=dict(points=[verified[k],verified[l]],distance2=str(d),min_radius2=str(d/4))
    write(D/'witnesses'/(name+'.json'),dict(input_hash=x['input_hash'],vehicles=out))


def verify_witness(name):
    x=read(D/'inputs/zero'/(name+'.json'))['original']
    data=read(D/'witnesses'/(name+'.json'));assert data['input_hash']==x['input_hash'] and x['bias_domain']==['0','0']
    for k,c in enumerate('ps'):
        w=data['vehicles'][c];ab=[]
        for p in w['points']:
            pt=list(map(F,p['xy4']))
            terms=score(x,pt)
            assert terms==p['terms'] and upper(terms)==F(p['upper'])<=26
            ab.append(pt[2*k:2*k+2])
        d=sum((a-b)**2 for a,b in zip(*ab))
        assert d==F(w['distance2']) and d/4==F(w['min_radius2'])>F(1,100)


def searches(variant,A,I,E,verify=False):
    prior.D=D/'runs'/variant
    for name in PLAN['cases']:
        obj=read(D/'inputs'/variant/(name+'.json'));x=obj['original']
        cert,ok,log=prior.attempt(name,'solution',x,F(1,40),300000,240,A,E,verify)
        assert ok
        print(variant,name,log['nodes'],flush=True)


if __name__=='__main__':
    action=sys.argv[1]
    if action=='prepare':immutable_inputs()
    elif action=='witness':
        for name in PLAN['cases']:witness(name);verify_witness(name);print(name,flush=True)
    elif action=='quick':
        for name in PLAN['cases']:verify_witness(name)
        print('8 independently recomputed point pairs pass')
    else:
        with tempfile.TemporaryDirectory() as tmp:
            searches(action,*prior.setup(Path(tmp)),'--verify' in sys.argv)
