"""A-side independent checks on exposed development inputs only."""
import argparse,ast,copy,gzip,hashlib,json,re,subprocess,sys,tarfile
from pathlib import Path
import numpy as np

def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def residual(u,m,x):
    o=u['obs'];p=np.array(x[:24]).reshape(6,2,2);a=np.array(o['anchors'])
    walls=np.sqrt(np.sum((p[:,:,None,:]-a[None,None,:,:])**2,axis=-1))
    peer=np.sqrt(np.sum((p[:,1]-p[:,0])**2,axis=-1));pred=np.column_stack([walls.reshape(6,8),peer])
    if m=='B2':pred[:,0 if o['kind']=='wall' else 8]+=x[-1]
    y=np.array(o['ranges']).reshape(6,9)
    if m=='B3':y=y-np.array(u['oracle']).reshape(6,9)
    rr=((pred-y)/o['range_sigma'])[:,:8 if m=='B0' else 9].ravel()
    rr=np.r_[rr,(np.diff(p.reshape(6,4),axis=0).ravel()-o['movement'])/o['motion_sigma']]
    if o['prior_sigma'] is not None:rr=np.r_[rr,(x[:4]-o['prior_center'])/o['prior_sigma']]
    return rr

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--fixtures',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);z=ap.parse_args()
    sys.path.insert(0,str(z.root/'tools/midterm_simulation_validation'))
    import core as c,pipeline as p
    cfg=c.load_config();manifest=p.verify_freeze();plan=p.plan(cfg,'formal');assert len(plan)==1800
    assert c.digest(plan)==manifest['formal_plan_identity_sha256']
    assert len(c.conditions(cfg))==36 and len(set(cfg['seeds']['formal']))==50
    assert cfg['seeds']['formal']==read(c.DOC/'SEED_REGISTRY.json')['formal_seeds']
    result=dict(formal_runs=0,formal_inputs_generated=0,plan_identity_count=len(plan),config_sha256=c.digest(cfg),source_sha256=p.source_hashes())
    # Vectorized independently coded residual; central differences check B's derivative.
    maximum=0.;fdmax=0.;count=0
    for cond in c.conditions(cfg):
        u=c.generate(cfg,cond,26011601)
        for m in cfg['methods']:
            fun,x,receipt=c.objective(cfg,u['obs'],m,np.array(u['oracle']) if m=='B3' else None)
            rr=residual(u,m,x);r,j=fun(x);maximum=max(maximum,float(max(abs(rr-r))))
            fd=np.column_stack([(residual(u,m,x+e*1e-6)-residual(u,m,x-e*1e-6))/2e-6 for e in np.eye(len(x))])
            fdmax=max(fdmax,float(np.max(abs(fd-j))));count+=1
    assert maximum<1e-10 and fdmax<2e-7
    result['independent_objective']=dict(cases=count,max_residual_error=maximum,max_whitened_jacobian_fd_error=fdmax)
    # Read original B evidence archive directly without extracting or executing its contents.
    archive=c.DOC/'TARGETED_CHECKS.tar.gz'
    with tarfile.open(archive) as t:
        saved={m.name:json.load(t.extractfile(m)) for m in t.getmembers() if m.isfile() and m.name.endswith('CHECKS.json')}
        assert saved
    result['B_archived_checks_count']=len(saved)
    # Actual repeated failures, not just their passed flags: independently reconstruct metrics and D.
    fixtures={};nm=0
    for directory in sorted(z.fixtures.iterdir()):
        if not (directory/'RUN.json').exists():continue
        summary=p.summarize(directory);rows=summary['rows'];by={r['method']:r for r in rows}
        assert len(rows)==4 and all(r['completed'] for r in rows)
        for r in rows:
            u=read(directory/'inputs'/(r['unit']+'.json.gz'));s=r['stages']['P1']
            if s['usable_estimate']:
                err=np.array(s['estimate'][:24]).reshape(6,2,2)-u['truth'];mse=np.mean(np.sum(err*err,axis=2),axis=0)
                assert np.allclose(mse,r['position_mse'],rtol=0,atol=1e-14)
                if by['B0']['usable_estimate']:assert np.allclose(mse-np.array(by['B0']['position_mse']),r['D'],rtol=0,atol=1e-14)
                else:assert r['D']==[None,None]
            else:assert r['position_mse']==[None,None] and r['D']==[None,None]
            if not r['stages']['P0']['endpoint_valid']:
                assert s['category']=='SKIPPED_INVALID_P0' and s['residual_calls']==s['jacobian_calls']==0
            if r['method']=='B2' and r['usable_estimate'] and by['B1']['usable_estimate']:
                assert np.allclose(np.array(r['position_mse'])-by['B1']['position_mse'],r['B2_minus_B1'],rtol=0,atol=1e-14)
            nm+=1
        fixtures[directory.name]=dict(planned=summary['planned_methods'],completed=summary['completed_methods'],valid=sum(r['usable_estimate'] for r in rows),accepted=sum(r['accepted'] for r in rows),P0=[r['P0_category'] for r in rows],P1=[r['category'] for r in rows])
    result['fixtures_independent_readback']=fixtures
    # Capture all solver controls, including scaling, and confirm acceptance independent of truth.
    from types import SimpleNamespace
    captured={}
    def spy(fun,start,**kw):
        captured.update(kw);return SimpleNamespace(x=start,status=2,success=True,message='A_CAPTURE_ONLY',nfev=1,njev=1)
    q=copy.deepcopy(cfg);q['solver']['P0'].update(max_nfev=7,ftol=2e-10,xtol=3e-10,gtol=4e-10)
    q['solver'].update(position_scale_m=2,bias_scale_m=.2)
    u=c.generate(cfg,c.conditions(cfg)[0],26011601);r=c.solve_stage(q,u,'B2','P0',solver=spy)
    assert all(captured[k]==v for k,v in q['solver']['P0'].items())
    assert np.array_equal(captured['x_scale'],np.r_[np.full(24,2),.2]) and captured['loss']=='linear'
    u2=copy.deepcopy(u);u2['truth']=(np.array(u['truth'])+100).tolist()
    r2=c.solve_stage(q,u2,'B2','P0',solver=spy)
    assert r['estimate']==r2['estimate'] and r['accepted']==r2['accepted'] and r['position_mse']!=r2['position_mse']
    result['solver_configuration_and_truth_separation']=True
    # Independent bootstrap from whole paired seed differences; artificial numbers, no new observations.
    vals=[float(i*i-3*i) for i in range(50)]
    rng=np.random.Generator(np.random.PCG64(cfg['statistics']['bootstrap_seed']))
    indices=rng.integers(0,50,(cfg['statistics']['bootstrap_repetitions'],50))
    ci=np.quantile(np.mean(np.array(vals)[indices],axis=1),[.025,.975])
    assert np.allclose(p.bootstrap(vals,50,cfg)['ci95'],ci,rtol=0,atol=1e-12)
    for v,n,state in [([],50,'INSUFFICIENT_VALID_SEEDS'),(vals[:44],50,'MISSING_EXCEEDS_LIMIT')]:assert p.bootstrap(v,n,cfg)['ci_status']==state
    assert p.bootstrap(vals,50,cfg,False)['ci95'] is None
    result['independent_paired_bootstrap']=dict(repetitions=10000,seed_count=50,ci=ci.tolist())
    # Independently rescan every archived historical blob using its immutable object identity.
    audit=read(c.DOC/'SEED_AUDIT.json.gz');seeds=cfg['seeds']['formal'];pat=re.compile(rb'(?<![\d.])(?:'+b'|'.join(str(s).encode() for s in seeds)+rb')(?!\d)')
    proc=subprocess.Popen(['git','cat-file','--batch'],cwd=z.root,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    matches=[];ranges=[];size=0
    for rec in audit['scanned_records']:
        proc.stdin.write((rec['oid']+'\n').encode());proc.stdin.flush()
        hdr=proc.stdout.readline().split();assert len(hdr)==3 and hdr[1]==b'blob'
        data=proc.stdout.read(int(hdr[2]));assert proc.stdout.read(1)==b'\n'
        if data.startswith(b'\x1f\x8b'):data=gzip.decompress(data)
        assert hashlib.sha256(data).hexdigest()==rec['sha256'];size+=len(data)
        if pat.search(data):matches.append(rec['oid'])
        if rec['path'].endswith('.py'):
            try:tree=ast.parse(data.decode())
            except (SyntaxError,UnicodeError):continue
            for node in ast.walk(tree):
                if isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id=='range') or (isinstance(node.func,ast.Attribute) and node.func.attr=='arange')):
                    try:rr=range(*[ast.literal_eval(v) for v in node.args])
                    except (ValueError,TypeError):continue
                    if any(s in rr for s in seeds):ranges.append(rec['oid'])
    proc.stdin.close();proc.wait();assert not matches and not ranges
    assert not audit['missing_commits'] and not audit['missing_blobs']
    result['seed_evidence_rescan']=dict(blobs=len(audit['scanned_records']),bytes=size,exact_matches=matches,literal_range_overlaps=ranges,scope='same archived immutable scope; not a claim about unrecorded external runs')
    result['passed']=True
    z.out.parent.mkdir(parents=True,exist_ok=True)
    with z.out.open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
