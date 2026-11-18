"""Fixed-height, causal Moon_1 epoch replay; oracle values only used in evaluation."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from pathlib import Path
from time import perf_counter

ROOT=Path(__file__).resolve().parents[3]
D=ROOT/'docs/research/lunar_end_to_end/moon_monitor'
CACHE=Path(os.environ.get('MOON_MONITOR_CACHE','/tmp/moon-monitor-pinned'))
OLD='af844589dc41d38f50b329b6baee3efb25eca208'
HEIGHT='da852740689113529b38815e1eb81f949ff5a8c6'
INTEGRITY='f823013b4d96579b5c2ec622fb6ed30848721514'
SLANT='docs/research/lunar_end_to_end/slant'
SRC='tools/midterm_dual_robot_contract_a'
AL=['1/20','1/10','1/5']

def dump(path,obj):
    path.parent.mkdir(exist_ok=True,parents=True)
    data=json.dumps(obj,separators=(',',':'),allow_nan=False).encode()
    path.write_bytes(gzip.compress(data,compresslevel=3,mtime=0) if path.suffix=='.gz' else data)

def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes())

def install():
    for sha,paths in [(OLD,['tools/lunar_end_to_end/slant',SLANT]),(HEIGHT,[SRC]),(INTEGRITY,[SRC+'/integrity_v1/decision.py'])]:
        target=CACHE/sha
        target.mkdir(exist_ok=True,parents=True)
        stream=subprocess.Popen(['git','archive',sha,*paths],cwd=ROOT,stdout=subprocess.PIPE)
        subprocess.run(['tar','x','-C',target],stdin=stream.stdout,check=True)
        assert stream.wait()==0

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def modules():
    sys.path.insert(0,str(CACHE/OLD/'tools/lunar_end_to_end/slant'))
    import execute as E
    A=load('height_contract',CACHE/HEIGHT/SRC/'height_v1/checker.py')
    I=load('decision',CACHE/INTEGRITY/SRC/'integrity_v1/decision.py')
    I.ROOT=ROOT  # resolve pinned Git dependencies in the actual checkout
    return E,A,I

def fix(anchors,heights,ranges):
    # Squared slant differences eliminate x^2+y^2. Solve the 3x2 LS system.
    xy=[]
    for car,h in enumerate(heights):
        w=[a[0]**2+a[1]**2+(h-a[2])**2-ranges[4*car+i]**2 for i,a in enumerate(anchors)]
        rows=[(2*(a[0]-anchors[0][0]),2*(a[1]-anchors[0][1]),v-w[0]) for a,v in zip(anchors[1:],w[1:])]
        aa=sum(x*x for x,y,z in rows);bb=sum(y*y for x,y,z in rows);ab=sum(x*y for x,y,z in rows)
        ax=sum(x*z for x,y,z in rows);by=sum(y*z for x,y,z in rows);det=aa*bb-ab*ab
        if det<=0:raise ValueError('degenerate anchor geometry')
        xy.append([str(F((bb*ax-ab*by)/det)),str(F((aa*by-ab*ax)/det))])
    return xy

def inputs():
    jobs=[]; events=[]; oracle={}
    manifest=read(CACHE/OLD/SLANT/'INPUT_MANIFEST.json')['records']
    for segment,folder in [('main','continuous'),('second','replication')]:
        base=D.parent/folder
        route=read(base/'ROUTE.json')
        for condition in ['normal','ramp_only']:
            entry=next(e for e in manifest if e['case']==segment+'_start_'+condition)
            path=base/'INPUTS.json.gz'
            assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['source_sha256']
            rec=next(r for r in read(path) if r['observation']['id']==entry['source_observation_id'])
            o=rec['observation']
            for i,t in enumerate(o['times_s']):
                start=perf_counter()
                xy=fix(o['anchors'],o['heights'][i],o['ranges'][i])
                latency=perf_counter()-start
                old=next((e for e in manifest if e['case'].startswith(segment+'_') and e['condition']==condition and e['index']==i),None)
                key=old['case'] if old else f'{segment}_i{i:02}_{condition}'
                src=route['source_times_car2_s'][0]+t
                meta=dict(case=key,car2_source_s=src)
                exact=lambda a:[exact(v) for v in a] if isinstance(a,list) else str(F(a))
                m=dict(anchors=exact(o['anchors']),heights=exact(o['heights'][i]),ranges=exact(o['ranges'][i]),variance=['1/625']*9,bias=['-3/5','3/5'],measurement_ids=[f't0/{c}/a{k}' for c in 'ps' for k in range(4)]+['t0/p/s/peer'])
                if old:assert m==read(CACHE/OLD/SLANT/'inputs'/(key+'.json'))
                event=dict(case=key,route=segment,condition=condition,i=i,state_s=t,source_p_s=src+5,source_s_s=src,observations_ready_s=t,fix_latency_s=latency,published_xy=xy,old=bool(old),dt=route['sampling_dt_s'])
                events.append(event);oracle[key]=rec['reference']['xyz'][i]
                for method in ('P4','N4'):jobs.append((meta,m,method,event))
    dump(D/'events.json',events)
    return jobs,oracle

def region(job):
    meta,m,method,event=job
    E,A,I=modules()
    dest=D/'certificates'/(meta['case']+'_'+method+'.json.gz')
    if dest.exists():raise FileExistsError(dest)
    start=perf_counter()
    x=E.adapter(m,meta,method,A)
    root=A.event_root(x);r=E.search(m,method,root)
    cert=E.certificate(x,r,method,root)
    dump(dest,dict(original=x,certificate=cert))
    saved=read(dest)
    assert A.check(saved['original'],saved['certificate'])['certificate_valid']
    resolution=not r['queue'] and all(all(F(b)-F(a)<=F(1,20) for a,b in n['box']) for n in r['nodes'] if n['kind']=='UNDECIDED')
    radii=[str(I.covering_radius(cert['projections'][c]['rectangles'],event['published_xy'][k])) for k,c in enumerate('ps')]
    elapsed=perf_counter()-start
    if event['old']:
        old=read(CACHE/OLD/SLANT/'results'/dest.name.removesuffix('.json.gz')/'certificate.json.gz')
        assert {k:v for k,v in cert.items() if k!='cost'}=={k:v for k,v in old.items() if k!='cost'}
    return dict(case=meta['case'],method=method,region_wall_s=elapsed,PL=radii,resolution=resolution)

def run():
    install();jobs,oracle=inputs()
    priority=[j for j in jobs if j[-1]['old']]
    with ProcessPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(region,priority))
        assert len(results)==24 and all(r['resolution'] for r in results)
        dump(D/'reproduced.json',results)
        results.extend(pool.map(region,[j for j in jobs if not j[-1]['old']]))
    dump(D/'services.json',results)
    dump(D/'evaluation_xyz.json',oracle)

if __name__=='__main__':run()
