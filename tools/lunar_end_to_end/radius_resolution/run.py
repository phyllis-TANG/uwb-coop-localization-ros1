"""Frozen coarse/fine pairs. Resume from independently checked stored certificates."""
import ast
import copy
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import subprocess
import sys
import tempfile
from fractions import Fraction as F
from pathlib import Path
from time import perf_counter

from solver import search
ROOT=Path(__file__).resolve().parents[3]
D=ROOT/'docs/research/lunar_end_to_end/radius_resolution'
P=json.loads((D/'plan.json').read_text())
BASE='docs/research/lunar_end_to_end/moon_monitor/'
A_DIR='tools/midterm_dual_robot_contract_a/'


def blob(commit,path):
    return subprocess.check_output(['git','show',commit+':'+path],cwd=ROOT)


def old(path):
    raw=blob(P['archive'],BASE+path)
    return json.loads(gzip.decompress(raw) if path.endswith('.gz') else raw)


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def setup(cache):
    for sha,paths in [(P['height_checker'],[A_DIR+'height_v1/checker.py',A_DIR+'core.py',A_DIR+'checker_v2.py']),
                      (P['radius_definition'],[A_DIR+'integrity_v1/decision.py']),
                      (P['solver'],['tools/lunar_end_to_end/slant/'+f+'.py' for f in ('execute','freeze_inputs')])]:
        for path in paths:
            dest=cache/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob(sha,path))
    sys.path.append(str(cache/'tools/lunar_end_to_end/slant'))
    import execute
    return module('height',cache/A_DIR/'height_v1/checker.py'),module('policy',cache/A_DIR/'integrity_v1/decision.py'),execute


def widths(cert,res):
    pending=len(cert['queue'])
    width=max((max(F(b)-F(a) for a,b in n['box']) for n in cert['nodes'] if n['kind']=='UNDECIDED'),default=F(0))
    assert width<=res
    return not pending


def science(cert):
    return {k:v for k,v in cert.items() if k not in ('input_hash','cost')}


def attempt(name,label,x,res,nodes,seconds,A,E,verify_only):
    x=copy.deepcopy(x);x['budget'].update(position_resolution=str(res),max_nodes=nodes,max_seconds=str(seconds))
    del x['input_hash'];x['input_hash']=E.digest(x)
    path=D/'results'/name/(label+'.json.gz')
    start=perf_counter()
    new_run=not path.exists()
    if new_run:
        if verify_only:raise FileNotFoundError(path)
        path.parent.mkdir(exist_ok=True,parents=True)
        model=dict(anchors=list(x['anchors'].values()),heights=[x['heights'][c] for c in 'ps'],ranges=[lo for lo,hi in x['observations']],bias=x['bias_domain'],variance=x['variance'],measurement_ids=x['measurement_ids'])
        model['anchors']=[x['anchors']['a'+str(i)] for i in range(4)]
        root=A.event_root(x);r=search(model,'P4',root,nodes,seconds,res)
        c=E.certificate(x,r,'P4',root)
        tmp=path.with_suffix('.tmp');tmp.write_bytes(gzip.compress(json.dumps(dict(original=x,certificate=c),separators=(',',':')).encode(),3,mtime=0));tmp.replace(path)
    obj=json.loads(gzip.decompress(path.read_bytes()))
    assert obj['original']==x
    c=obj['certificate']
    assert A.check(x,c)['certificate_valid']
    valid=widths(c,res)
    receipt=path.with_suffix('.receipt.json')
    if not receipt.exists() and not new_run:
        raise RuntimeError(f'Existing certificate without original timing receipt: {path}. Preserve it for inspection.')
    if new_run:
        receipt.write_text(json.dumps(dict(run_and_verify_s=perf_counter()-start,archive_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),complete=valid,nodes=len(c['nodes']),pending=len(c['queue'])),indent=2)+'\n')
    log=json.loads(receipt.read_text())
    assert log['archive_sha256']==hashlib.sha256(path.read_bytes()).hexdigest() and log['complete']==valid
    return c,valid,log


def table(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)


def run(A,I,E,verify_only):
    events={e['case']:e for e in old('events.json')}
    services={(s['case'],s['method']):s for s in old('services.json')}
    truth=old('evaluation_xyz.json')
    available=list(csv.DictReader(io.StringIO(blob(P['archive'],BASE+'availability.csv').decode())))
    rows=[];logs=[]
    for name,index in P['cases']:
        e=events[name];assert e['i']==index and e['old'] and e['condition']=='normal'
        archived=old('certificates/'+name+'_P4.json.gz')
        x,c=archived['original'],archived['certificate'];s=services[name,'P4']
        assert x['case_id']==name and x['budget']==dict(position_resolution='1/20',max_seconds='30',max_nodes=50000)
        assert c['threshold_certificate']['tau']=='26' and A.check(x,c)['certificate_valid'] and widths(c,F(1,20))
        published=e['published_xy']
        for i,car in enumerate('ps'):
            a=next(v for v in available if (v['case'],v['method'],v['car'],v['AL'])==(name,'P4',car,'1/10'))
            assert int(a['seed'])==P['seed'] and a['input_hash']==x['input_hash'] and ast.literal_eval(a['estimate_xy'])==published[i]
            assert I.covering_radius(c['projections'][car]['rectangles'],published[i])==F(s['PL'][i])
        def one(tag,res,n,seconds):
            cert,ok,log=attempt(name,tag,x,F(res),n,seconds,A,E,verify_only)
            logs.append(dict(case=name,attempt=tag,status='COMPLETE' if ok else 'PARTIAL',**log))
            return cert,ok,log
        fine,ok,log=one('fine_original_budget','1/40',50000,30)
        coarse_time=None
        if not ok:
            coarse,matched,coarse_log=one('coarse_matched','1/20',300000,240)
            assert matched and science(coarse)==science(c)
            coarse_time=coarse_log['run_and_verify_s']
            fine,ok,log=one('fine_matched','1/40',300000,240)
        for i,car in enumerate('ps'):
            xy=published[i]
            coarsePL=F(s['PL'][i]);finePL=I.covering_radius(fine['projections'][car]['rectangles'],xy)
            err2=sum((F(z)-F(v))**2 for z,v in zip(xy,truth[name][i][:2]))
            assert finePL<=coarsePL
            leaves=lambda cert:sum(cert['counts'][k] for k in ('INSIDE','UNDECIDED','PENDING'))
            rows.append(dict(case=name,index=index,car=car,status='COMPLETE' if ok else 'PARTIAL',published_x=xy[0],published_y=xy[1],state_s=e['state_s'],coarse_PL_m=float(coarsePL),fine_PL_m=float(finePL),change_cm=float(100*(finePL-coarsePL)),error_m=math.sqrt(float(err2)),covered_coarse=err2<=coarsePL**2,covered_fine=err2<=finePL**2,coarse_leaves=leaves(c),fine_leaves=leaves(fine),historical_coarse_s=s['region_wall_s'],matched_coarse_s=coarse_time,fine_s=log['run_and_verify_s'],coarse_within_010=coarsePL<=F(1,10),fine_within_010=finePL<=F(1,10),coarse_within_020=coarsePL<=F(1,5),fine_within_020=finePL<=F(1,5),gap_010_cm=float(100*(finePL-F(1,10))),gap_020_cm=float(100*(finePL-F(1,5)))))
        if not verify_only:
            table(D/'paired.csv',rows);table(D/'attempts.csv',logs)
        print(name,'COMPLETE' if ok else 'PARTIAL',flush=True)
        if not ok and name==P['cases'][0][0]:break
    if verify_only:
        assert len(rows)==len(list(csv.DictReader((D/'paired.csv').open())))
        buf=io.StringIO();w=csv.DictWriter(buf,rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
        assert buf.getvalue()==(D/'paired.csv').read_text()


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:run(*setup(Path(tmp)),'--verify' in sys.argv)
