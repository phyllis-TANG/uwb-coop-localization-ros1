"""All saved final/stage checks and predeclared first-seed Hessian verification."""
from common import *
from model import CFG,validate_inputs
from adapter import V
import argparse,collections

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();p=a.results;inputs={r['id']:r for r in records(p/'INPUTS.jsonl.gz')};ends=list(records(p/'ENDPOINTS.jsonl.gz'));sels=read(p/'readback/SELECTION.json');by={(z['id'],z['method'],z['init']):z for z in ends};d=cached_npz(p/'readback/POINTS.npz');checks=validate_inputs(list(inputs.values()));maxr=maxj=maxgrad=maxfd=0.;fdn=0;stages=0
    assert len(inputs)==120 and len(by)==len(ends)==1200 and sum(z['optimizer_calls'] for z in ends)<=2400
    assert {(u,m,i) for u in inputs for m in CFG['methods'] for i in CFG['initializations']}==set(by)
    for z in ends:
        rec=inputs[z['id']];u=copy.deepcopy(rec['input']);u['obs']['start']=rec['initials'][z['init']];fun,start,receipt=V.objective(SOURCE,u['obs'],z['method'],np.array(u['oracle']) if z['method']=='B3' else None)
        assert z['stages']['P0']['solver_input_sha256']==V.digest(receipt);assert receipt['range_sigma']==u['obs']['range_sigma'] and receipt['motion_sigma']==u['obs']['motion_sigma']
        for stage in ['P0','P1']:
            s=z['stages'][stage];stages+=1
            if not s['endpoint_valid']:continue
            x=np.array(s['estimate']);r,j=objective(u,z['method'],x);rr,jj=fun(x);maxr=max(maxr,float(max(abs(r-rr))));maxj=max(maxj,float(np.max(abs(j-jj))));maxgrad=max(maxgrad,abs(float(max(abs(jj.T@rr)))-s['gradient_inf']));assert maxr<1e-10 and maxj<1e-10 and maxgrad<1e-8
    for s in sels:
        candidates=[(by[s['id'],s['method'],i]['stages']['P1']['cost'],i) for i in CFG['initializations'] if by[s['id'],s['method'],i]['stages']['P1']['accepted']]
        assert (min(candidates)[1] if candidates else None)==s['selected_init']
        if s['seed']!=CFG['seeds'][0]:continue
        u=inputs[s['id']]['input']
        for ini in ['I0',s['selected_init']]:
            if ini is None:continue
            z=by[s['id'],s['method'],ini]['stages']['P1'];x=np.array(z['estimate']);h=exact_hessian(u,s['method'],x);fd=np.empty_like(h)
            for k in range(len(x)):
                dx=np.zeros_like(x);dx[k]=5e-6;rp,jp=objective(u,s['method'],x+dx);rm,jm=objective(u,s['method'],x-dx);fd[:,k]=(jp.T@rp-jm.T@rm)/1e-5
            maxfd=max(maxfd,float(np.linalg.norm(fd-h)/np.linalg.norm(h)));fdn+=1
    assert maxfd<1e-6
    # Every legacy deliverable byte and all frozen solver bytes unchanged.
    for path,h in read(OLD/'SHA256SUMS.json')['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
    for path,h in read(p/'CONTRACT.json')['source'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==h
    coverage=list(csv.DictReader((p/'summary/COVERAGE.csv').open()))
    for row in coverage:
        plan=240 if row['aggregation']=='point_mean' else 40
        assert int(row['planned'])==plan and 0<=int(row['covered'])<=int(row['available'])<=plan
        assert int(row['unavailable'])==plan-int(row['available'])
        assert abs(float(row['planned_valid_and_covered'])-int(row['covered'])/plan)<1e-14
    failures=list(csv.DictReader((p/'summary/FAILURES.csv').open()))
    for cid in sorted({z['condition'] for z in failures}):
        for m in CFG['methods']:
            subset=[z for z in failures if z['condition']==cid and z['method']==m];assert sum(int(z['count']) for z in subset)==200 and all(int(z['planned_candidates'])==200 for z in subset)
    checks['coverage_denominator_rows_checked']=len(coverage)
    checks.update(configurations=1200,stage_records=stages,optimizer_calls_recorded=sum(z['optimizer_calls'] for z in ends),extra_optimizer_calls=0,max_residual_difference=maxr,max_jacobian_difference=maxj,max_gradient_difference=maxgrad,selected_identities_checked=len(sels),selected_unavailable=sum(s['selected_index'] is None for s in sels),first_seed_hessian_checks=fdn,max_hessian_difference=maxfd,categories=dict(collections.Counter(z['stages']['P1']['category'] for z in ends)),point_blocks=int(np.prod(d['q'].shape)),point_reasons=dict(collections.Counter(d['reason'].ravel())),legacy_hashes='UNCHANGED',execution_source_hashes='UNCHANGED',npz_loaded_once=True)
    save(a.output,checks);print(checks)
if __name__=='__main__':main()
