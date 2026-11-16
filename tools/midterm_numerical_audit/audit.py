"""Read saved estimates first; run only the explicitly exposed development panel.
No optimizer consumes truth; no original source/result is modified.
"""
import argparse, csv, gzip, hashlib, importlib.util, itertools, json, subprocess, sys
from collections import Counter
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import least_squares
A_SHA = 'ed17e3ad177b5d52c1470e85da9f7a8645dbada9'
B_SHA = '8174445e3b8e473bef15a82d345b7a7e1d94ac05'
BASE = 'df323eccdffd375a2fb255ebbfd734b6c2be4aac'
ROOT = Path(__file__).resolve().parents[2]
D = np.r_[np.ones(24), .1]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, x):
    with p.open('x') as f: json.dump(x, f, indent=2, allow_nan=False)
def csvout(p, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with p.open('x', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
def module(name, p):
    s = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

def a_problem(a, obs, peer_only=False):
    # Use A's independent vectorized range model; exactly B's supplied inputs.
    def fun(z):
        v, j = a.model(z, np.array(obs['anchors']), obs['kind'], peer_only)
        r = [(v-np.array(obs['ranges']))/obs['range_sigma'],
             (a.MOTION@z-np.array(obs['movement']))/obs['motion_sigma']]
        js = [j/obs['range_sigma'], a.MOTION/obs['motion_sigma']]
        if obs['prior_sigma'] is not None:
            r.append((z[:4]-obs['prior_center'])/obs['prior_sigma'])
            js.append(a.PRIOR/obs['prior_sigma'])
        return np.concatenate(r), np.vstack(js)
    return fun

def diagnostics(fun, x):
    r, j = fun(np.array(x)); scales = D if j.shape[1]==25 else np.ones(24)
    g = j.T@r; s = np.linalg.svd(j*scales, compute_uv=False)
    gn = np.linalg.lstsq(j*scales, -r, rcond=1e-8)[0]
    denom = np.linalg.norm(j*scales, axis=0)*np.linalg.norm(r)
    return dict(finite=bool(np.isfinite(x).all() and np.isfinite(r).all() and np.isfinite(j).all()),
                cost=float(r@r/2), raw_grad_inf=float(np.max(abs(g))),
                scaled_grad_inf=float(np.max(abs(scales*g))),
                column_normalized_gradient=float(np.max(np.divide(abs(scales*g),denom,out=np.zeros_like(g),where=denom>0))),
                rank=int(sum(s>s[0]*1e-8)), dimension=j.shape[1],
                condition=float(s[0]/s[-1]) if s[-1]>s[0]*1e-8 else None,
                gn_step_scaled_inf=float(max(abs(gn))),
                roundoff_gradient_scale=float(np.finfo(float).eps*len(r)*np.linalg.norm(j*scales,2)*max(1,np.linalg.norm(r))))

def summary(rows):
    return dict(n=len(rows), scipy_status=dict(Counter(str(r['scipy_status']) for r in rows)),
                finite=sum(r['audit_finite'] for r in rows), scipy_success=sum(r['scipy_success'] for r in rows),
                optimality_gt_1e5=sum(r['audit_raw_grad_inf']>1e-5 for r in rows),
                saved_optimality_gt_1e5=sum(float(r['saved_optimality'])>1e-5 for r in rows),
                position_gt_05=sum(r['audit_position_gt_05'] for r in rows),
                bias_gt_01=sum(r.get('audit_bias_gt_01') is True for r in rows),
                endpoint_rank=dict(Counter(str(r['audit_rank']) for r in rows)),
                reference_data_rank=dict(Counter(str(r['reference_data_rank']) for r in rows)),
                max_optimality_readback_delta=max(abs(r['audit_raw_grad_inf']-float(r['saved_optimality'])) for r in rows))

def saved_a(a, rawdir, out):
    doc = ROOT/'docs/research/midterm_simulation_s1b/results'
    index = json.loads((doc/'EXTERNAL_INDEX.json').read_text())
    for name, entry in index['files'].items(): assert sha(rawdir/name)==entry['sha256'], name
    raw = [json.loads(l) for l in (rawdir/'RAW.jsonl').open()]
    observations = {(r['scene'],r['seed']):r for r in raw if 'variant' not in r}
    estimates = {(r['scene'],r['seed'],r['variant']):r for r in raw if 'variant' in r}
    infos = {(r['scene'],r['information']):r for r in json.loads((doc/'INFORMATION.json').read_text())}
    rows=[]
    for old in csv.DictReader((doc/'PER_RUN.csv').open()):
        o=observations[old['scene'],int(old['seed'])]; e=estimates[old['scene'],int(old['seed']),old['variant']]
        obs=dict(anchors=o['anchors'],kind=old['kind'], ranges=o['range_observed'],movement=o['motion_observed'],
                 range_sigma=.04,motion_sigma=.02,prior_sigma=float(old['prior_sigma_m']) if old['prior_sigma_m'] else None,prior_center=e['prior_center'])
        fun=a_problem(a,obs,old['peer_only']=='True'); d=diagnostics(fun,e['estimate'])
        err=np.array(e['estimate'])-o['truth']; pos=float(np.sqrt(np.mean(np.sum(err[:24].reshape(6,2,2)**2,axis=-1))))
        ref=infos[old['scene'],'data_motion']
        row={**old, 'saved_optimality':old['optimality'], 'scipy_status':int(old['status']), 'scipy_success':int(old['status'])>0,
             **{'audit_'+k:v for k,v in d.items()},'audit_position_gt_05':pos>.5,'audit_bias_gt_01':bool(abs(err[-1])>.1),
             'audit_position_rmse':pos,'audit_bias_error':float(err[-1]),'reference_data_rank':ref['rank'],
             'reference_bias_null_norm':ref['bias_null_norm_scaled'],'reference_bias_information':ref['bias_information_m_minus2'],
             'structural_bias_counterexample':old['peer_only']=='True'}
        assert abs(pos-float(old['position_rmse_2d_m']))<1e-12
        assert abs(d['cost']-float(old['cost']))<1e-9*max(1,d['cost'])
        assert (pos>.5)==(old['position_failed']=='True')
        assert (abs(err[-1])>.1)==(old['bias_failed']=='True')
        rows.append(row)
    csvout(out/'A_RECLASSIFIED.csv',rows)
    main=[r for r in rows if r['peer_only']=='False']
    return {name:summary(sub) for name,sub in [('all',rows),('main',main),('main_zero',[r for r in main if r['noise']=='zero']),('main_noisy',[r for r in main if r['noise']=='gaussian']),('negative_control',[r for r in rows if r['peer_only']=='True'])]}

def saved_b(b, cfg, broot, out):
    rows=[]
    with gzip.open(broot/'docs/research/midterm_simulation_s2/UNITS.jsonl.gz','rt') as f:
        for line in f:
            u=json.loads(line); meta={k:u[k] for k in ['profile','seed','geometry','motion','kind','bias_m']}
            obs,truth,oracle,noise=b.generate(u['geometry'],u['motion'],u['kind'],u['bias_m'],u['profile'],u['seed'],cfg)
            assert b.digest(obs)==u['observation_sha256']; assert b.digest(noise)==u['noise_sha256']
            for old in u['results']:
                fun,_,receipt=b.problem(obs,old['method'],oracle if old['method']=='B3' else None)
                assert b.digest(receipt)==old['input_sha256']
                d=diagnostics(fun,old['estimate'])
                err=np.array(old['estimate'][:24]).reshape(6,2,2)-truth
                pos=float(np.sqrt(np.mean(np.sum(err**2,axis=-1))))
                be=float(old['estimate'][-1]-u['bias_m']) if old['method']=='B2' else None
                assert abs(2*d['cost']-old['residual_sum_squares'])<1e-9
                row={**meta,'method':old['method'],'old_status':old['status'],'old_success':old['success'],
                     'scipy_status':old['scipy_status'],'scipy_success':old['scipy_success'],'saved_optimality':old['optimality'],
                     **{'audit_'+k:v for k,v in d.items()},'audit_position_rmse':pos,'audit_bias_error':be,
                     'audit_position_gt_05':pos>.5,'audit_bias_gt_01':None if be is None else abs(be)>.1,
                     'reference_data_rank':old['reference_data_rank'],'saved_data_rank':old['data_information']['rank']}
                assert old['success']==(old['scipy_success'] and d['finite'] and old['optimality']<=cfg['accepted_optimality'])
                rows.append(row)
    csvout(out/'B_RECLASSIFIED.csv',rows)
    return {name:summary(sub) for name,sub in [('all',rows)]+[(m,[r for r in rows if r['method']==m]) for m in b.METHODS]}

def panel(a,b,cfg,out,large):
    inputs=[]; rows=[]; parity=[]; continuation=[]
    full=large/'PANEL_DETAILS.jsonl'
    with full.open('x') as f:
        for i,(geom,motion,kind,bias,profile) in enumerate(itertools.product(['good','weak'],['static','turn'],['wall','peer'],[0.,.3],['noisy_unbiased_prior','noisy_biased_prior'])):
            obs,truth,oracle,noise=b.generate(geom,motion,kind,bias,profile,26011601,cfg)
            meta=dict(id=i,geometry=geom,motion=motion,kind=kind,bias=bias,profile=profile,seed=26011601)
            inp=dict(**meta,obs=obs,noise=noise,truth_offline_only=truth.tolist(),oracle_B3_only=oracle.tolist(),observation_sha256=b.digest(obs),noise_sha256=b.digest(noise))
            inputs.append(inp)
            for method in b.METHODS:
                original=b.solve(obs,method,cfg,oracle if method=='B3' else None)
                fun,start,receipt=b.problem(obs,method,oracle if method=='B3' else None)
                d=diagnostics(fun,original['estimate'])
                assert original['input_sha256']==b.digest(receipt)
                rows.append(dict(**meta,method=method,old_status=original['status'],scipy_status=original['scipy_status'],optimality=original['optimality'],input_sha256=original['input_sha256'],**d))
                # Diagnostic continuation only; never replaces the original returned solution.
                fit=least_squares(lambda x:fun(x)[0],np.array(original['estimate']),jac=lambda x:fun(x)[1],x_scale=D if method=='B2' else np.ones(24),max_nfev=1000,ftol=None,xtol=1e-14,gtol=1e-10)
                cd=diagnostics(fun,fit.x); delta=fit.x-np.array(original['estimate'])
                continuation.append(dict(**meta,method=method,status=int(fit.status),nfev=fit.nfev,**cd,
                                         cost_reduction=d['cost']-cd['cost'],position_change_max_m=float(max(abs(delta[:24]))),
                                         bias_change_m=float(delta[-1]) if method=='B2' else None))
                detail=dict(**meta,method=method,original=original,continuation=dict(estimate=fit.x.tolist(),status=int(fit.status),message=fit.message))
                if method=='B2':
                    af=a_problem(a,obs)
                    # Call fixed A solver directly, with B start/center/weights, not A survey.
                    assert obs['range_sigma']==a.C['range_sigma_m'] and obs['motion_sigma']==a.C['motion_sigma_m']
                    ax=a.solve(np.array(obs['anchors']),kind,False,np.array(obs['ranges']),np.array(obs['movement']),start.copy(),obs['prior_sigma'],np.array(obs['prior_center']))
                    detail['A_estimate']=ax.x.tolist(); detail['points']={}
                    for label,x in [('initial',start),('B_endpoint',np.array(original['estimate'])),('A_endpoint',ax.x)]:
                        ar,aj=af(x); br,bj=fun(x); ag=aj.T@ar; bg=bj.T@br
                        detail['points'][label]=dict(state=x.tolist(),A_residual=ar.tolist(),B_residual=br.tolist(),A_jacobian=aj.tolist(),B_jacobian=bj.tolist(),A_gradient=ag.tolist(),B_gradient=bg.tolist(),A_scaled_gradient=(D*ag).tolist(),B_scaled_gradient=(D*bg).tolist())
                        parity.append(dict(**meta,point=label,residual_max_delta=float(max(abs(ar-br))),jacobian_max_delta=float(np.max(abs(aj-bj))),cost_delta=float(abs(ar@ar-br@br)/2),gradient_max_delta=float(max(abs(ag-bg))),scaled_gradient_max_delta=float(max(abs(D*(ag-bg)))),**{'A_'+k:v for k,v in diagnostics(af,x).items()}))
                    delta=ax.x-np.array(original['estimate'])
                    detail['A_vs_B_position_max_m']=float(max(abs(delta[:24])));detail['A_vs_B_bias_m']=float(delta[-1])
                    detail['A_status']=int(ax.status)
                    # Offline evaluation is deliberately separate from solver and selection.
                    detail['offline_errors']={k:dict(position_rmse=float(np.sqrt(np.mean(np.sum((x[:24].reshape(6,2,2)-truth)**2,axis=-1)))),bias_error=float(x[-1]-bias)) for k,x in [('A',ax.x),('B',np.array(original['estimate']))]}
                f.write(json.dumps(detail,allow_nan=False)+'\n')
    with (out/'PANEL_INPUTS.jsonl').open('x') as f:
        for x in inputs:f.write(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
    csvout(out/'PANEL_ORIGINAL.csv',rows);csvout(out/'B2_PARITY.csv',parity);csvout(out/'CONTINUATION.csv',continuation)
    # Keep compact per-run endpoints in Git; matrices stay outside Git.
    compact=[]
    for line in full.open():
        x=json.loads(line)
        if x['method']=='B2':
            compact.append({k:v for k,v in x.items() if k not in ['original','points','continuation']}|{'B_estimate':x['original']['estimate'],'B_status':x['original']['scipy_status']})
    dump(out/'B2_ENDPOINTS.json',compact)
    return dict(original_runs=len(rows),A_B2_runs=32,continuation_runs=len(continuation),original_optimality_exceeds=sum(r['optimality']>1e-5 for r in rows),continuation_exceeds=sum(r['raw_grad_inf']>1e-5 for r in continuation),max_position_continuation=max(r['position_change_max_m'] for r in continuation),max_bias_continuation=max(abs(r['bias_change_m']) for r in continuation if r['bias_change_m'] is not None),max_cost_reduction=max(r['cost_reduction'] for r in continuation),max_A_B_position=max(r['A_vs_B_position_max_m'] for r in compact),max_A_B_bias=max(abs(r['A_vs_B_bias_m']) for r in compact),max_residual_delta=max(r['residual_max_delta'] for r in parity),max_jacobian_delta=max(r['jacobian_max_delta'] for r in parity),max_gradient_delta=max(r['gradient_max_delta'] for r in parity))

def main():
    p=argparse.ArgumentParser();p.add_argument('--b-root',type=Path,required=True);p.add_argument('--a-raw',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--large',type=Path,required=True);args=p.parse_args()
    # Fixed source blobs must be byte-identical even on later audit commits.
    sources={}
    for root,commit,paths in [(ROOT,A_SHA,['tools/midterm_simulation_s1b/analyze.py','docs/research/midterm_simulation_s1b/CONFIG.json','docs/research/midterm_simulation_s1b/results/PER_RUN.csv','docs/research/midterm_simulation_s1b/results/INFORMATION.json','docs/research/midterm_simulation_s1b/results/EXTERNAL_INDEX.json']), (args.b_root,B_SHA,['tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py','docs/research/midterm_simulation_s2/CONFIG.json','docs/research/midterm_simulation_s2/UNITS.jsonl.gz'])]:
        for path in paths:
            expected=subprocess.check_output(['git','show',commit+':'+path],cwd=root)
            assert (root/path).read_bytes()==expected,path
            sources[commit+':'+path]=sha(root/path)
    a=module('fixed_A',ROOT/'tools/midterm_simulation_s1b/analyze.py');b=module('fixed_B',args.b_root/'tools/midterm_simulation_s2/prototype.py')
    cfg=json.loads((args.b_root/'docs/research/midterm_simulation_s2/CONFIG.json').read_text())
    args.out.mkdir(parents=True,exist_ok=False);args.large.mkdir(parents=True,exist_ok=False)
    dump(args.out/'SOURCES.json',sources)
    dump(args.out/'ENVIRONMENT.json',dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,executable=sys.executable,source_A=A_SHA,source_B=B_SHA,base=BASE))
    dump(args.out/'PANEL_CONFIG.json',dict(B_original_config=cfg,geometry=['good','weak'],motion=['static','turn'],kind=['wall','peer'],bias=[0,.3],profile=['noisy_unbiased_prior','noisy_biased_prior'],seed=26011601,purpose='DEVELOPMENT_NUMERICAL_DIAGNOSTICS_ONLY',continuation=dict(max_nfev=1000,ftol=None,xtol=1e-14,gtol=1e-10),script_sha256=sha(Path(__file__))))
    result=dict(A=saved_a(a,args.a_raw,args.out),B=saved_b(b,cfg,args.b_root,args.out))
    dump(args.out/'SAVED_AUDIT.json',result);print(json.dumps(result,indent=2),flush=True)
    result['panel']=panel(a,b,cfg,args.out,args.large)
    dump(args.out/'SUMMARY.json',result)
    dump(args.out/'EXTERNAL_INDEX.json',dict(directory=str(args.large),files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in args.large.iterdir()}))
    dump(args.out/'SHA256SUMS.json',{p.name:sha(p) for p in args.out.iterdir() if p.is_file()})
    print(json.dumps(result['panel'],indent=2),flush=True)
if __name__=='__main__':main()
