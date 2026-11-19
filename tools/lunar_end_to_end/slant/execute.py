"""Run one frozen epoch at a time with the released A event root and certificate verifier."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import resource
import subprocess
import time
from fractions import Fraction as F
from pathlib import Path
from freeze_inputs import BASE,DOC,IDS,digest,write
from solver import search,sqrt_bounds

def read(path):
    return json.loads(path.read_bytes())

def adapter(m,meta,method,A):
    n=9 if method=='P4' else 8
    t=F(str(meta['car2_source_s']))
    x=dict(schema_version=A.VERSION,source_commit=BASE,case_id=meta['case'],frame='moon_map_z_up',units='m',source_times=dict(p=str(t+5),s=str(t)),heights=dict(zip('ps',m['heights'])),anchors=dict(zip(['a0','a1','a2','a3'],m['anchors'])),measurement_ids=IDS[:n],observations=[[v,v] for v in m['ranges'][:n]],variance=m['variance'][:n],bias_domain=m['bias'],arithmetic_policy=A.K.POLICY,domain_source='joint_event_26',budget=dict(max_nodes=50000,max_seconds='30',position_resolution='1/20'))
    x['input_hash']=digest(x)
    return x

def projection(keep,offset):
    rectangles=[dict(leaf=node['id'],box=node['box'][offset:offset+2]) for node in keep]
    if not rectangles:return dict(rectangles=[],center=None,radius=None,radius_squared=None,area_upper='0')
    boxes=[tuple(tuple(map(F,ab)) for ab in r['box']) for r in rectangles]
    low=[min(b[j][0] for b in boxes) for j in (0,1)]
    high=[max(b[j][1] for b in boxes) for j in (0,1)]
    center=[(a+b)/2 for a,b in zip(low,high)]
    radius2=max(sum(max(abs(v-center[j]) for v in b[j])**2 for j in (0,1)) for b in boxes)
    area=min((high[0]-low[0])*(high[1]-low[1]),sum((b-a)*(d-c) for ((a,b),(c,d)) in boxes))
    return dict(rectangles=rectangles,center=list(map(str,center)),radius=str(sqrt_bounds(radius2)[1]),radius_squared=str(radius2),area_upper=str(area))

def certificate(x,r,method,root):
    keep=[n for n in r['nodes'] if n['kind'] in ('INSIDE','UNDECIDED','PENDING')]
    n=len(x['measurement_ids'])
    threshold=dict(id=f'DUAL-A-V1-CHI2-{n}-CHERNOFF',dimension=n,tau=str(26 if n==9 else 24),alpha='1/20',method='mgf_t_1/4_squared_taylor_80',t='1/4',terms=80)
    status='BUDGET_OUTER' if r['queue'] else 'OUTER_CERTIFIED' if keep else 'EMPTY_IN_DECLARED_DOMAIN'
    start=time.monotonic()
    c=dict(schema_version=x['schema_version'],source_commit=BASE,input_hash=x['input_hash'],mode='4d' if n==9 else 'no_peer',measurement_ids=x['measurement_ids'],threshold_certificate=threshold,root=r['root'],nodes=r['nodes'],queue=r['queue'],projections={car:projection(keep,i) for car,i in [('p',0),('s',2)]},counts={k:r['counts'].get(k,0) for k in ['INSIDE','OUTSIDE','UNDECIDED','PENDING','SPLIT']},domain_contact=any(any(a==l or b==h for (a,b),(l,h) in zip(node['box'],root)) for node in keep),status=status,internal_semantics='forall_position_exists_bias_and_observation' if n==9 else 'forall_position_exists_observation',bias_recovery=[])
    c['cost']=dict(processed_nodes=r['processed'],search_seconds=str(r['search_seconds']),certificate_write_seconds=str(time.monotonic()-start),peak_rss_bytes=str(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),distance_evaluations=r['distance_evaluations'])
    return c

def verify_file(path,h):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==h,path

def run(meta,method,A,freeze):
    key=meta['case'];path=DOC/'results'/f'{key}_{method}'
    path.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    mpath=DOC/'inputs'/f'{key}.json';verify_file(mpath,meta['solver_sha256'])
    m=read(mpath);x=adapter(m,meta,method,A);write(path/'input.json',x)
    root=A.event_root(x);assert root is not None
    r=search(m,method,root);c=certificate(x,r,method,root)
    archive=path/'certificate.json.gz';archive.write_bytes(gzip.compress(json.dumps(c,separators=(',',':')).encode(),compresslevel=3,mtime=0))
    receipt=A.check(x,json.loads(gzip.decompress(archive.read_bytes())))
    assert receipt['certificate_valid'];write(path/'acceptance.json',receipt)
    epath=DOC/'evaluation'/f'{key}.json';verify_file(epath,meta['evaluation_sha256']);e=read(epath)
    pos=[F(v) for p in e['xyz'] for v in p[:2]]
    hits=[False,False];joint=False
    for node in c['nodes']:
        if node['kind'] not in ('INSIDE','UNDECIDED','PENDING'):continue
        inside=[F(a)<=v<=F(b) for (a,b),v in zip(node['box'],pos)]
        joint|=all(inside);hits[0]|=all(inside[:2]);hits[1]|=all(inside[2:])
    n=len(x['variance']);event=sum(F(v)**2/F(s) for v,s in zip(e['generated_noise'][:n],x['variance']))
    row=dict(case=key,method=method,status=c['status'],certificate='PASS',resolution_met=not bool(c['queue']),budget_stop=bool(c['queue']),original_event=event<=int(c['threshold_certificate']['tau']),joint_hit=joint,p_hit=hits[0],s_hit=hits[1],nodes=len(c['nodes']),wall_seconds=time.monotonic()-start)
    for car in 'ps':
        pr=c['projections'][car];row[car+'_area_upper']=float(F(pr['area_upper']));row[car+'_radius']=None if pr['radius'] is None else float(F(pr['radius']))
    write(path/'receipt.json',dict(row=row,noise_statistic=str(event),event_root=root,freeze=freeze,a_sha=read(DOC/'A_LOCK.json')['sha'],certificate_sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
    return row

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('index',type=int);p.add_argument('--source',type=Path,required=True);p.add_argument('--freeze',required=True);args=p.parse_args()
    lock=read(DOC/'A_LOCK.json')
    for name,h in lock['files'].items():verify_file(args.source/name,h)
    for name,h in read(DOC/'RUN_FREEZE.json').items():verify_file(DOC.parents[3]/name,h)
    assert subprocess.check_output(['git','show',args.freeze+':docs/research/lunar_end_to_end/slant/RUN_FREEZE.json'])==(DOC/'RUN_FREEZE.json').read_bytes()
    spec=importlib.util.spec_from_file_location('height_contract',args.source/'tools/midterm_dual_robot_contract_a/height_v1/checker.py')
    A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
    meta=read(DOC/'INPUT_MANIFEST.json')['records'][args.index//2]
    method=('P4','N4')[args.index%2];row=run(meta,method,A,args.freeze)
    ledger=DOC/'LEDGER.csv'
    with ledger.open() as f:rows=list(csv.DictReader(f))
    rows[args.index]=row;tmp=ledger.with_suffix('.tmp')
    with tmp.open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    tmp.replace(ledger)
    print(row,flush=True)
