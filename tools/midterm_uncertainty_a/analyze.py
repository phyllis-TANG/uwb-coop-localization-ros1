"""Read only portable frozen states; optimizer calls are forbidden."""
import argparse,csv,gzip,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
import numpy as np
import scipy,scipy.optimize
from diagnostics import Layout,Noise,diagnose,information
ROOT=Path(__file__).resolve().parents[2]
BASE='fba539052f3ce2ed7d2ed35e79ac03198200c680'
VIEWS=['total_curvature','fixed_prior_noise','data_only']
def forbidden(*a,**k):raise RuntimeError('Optimizer forbidden in saved-state uncertainty analysis')
scipy.optimize.least_squares=forbidden

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    return x
def dump(p,x):
    with p.open('x') as f:json.dump(clean(x),f,indent=2,allow_nan=False)
def csvout(p,rows):
    with p.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)),lineterminator='\n');w.writeheader();w.writerows(clean(rows))
def spectrum(info):return {k:v for k,v in info.items() if k not in ['covariance','nullspace']}
def layout(method,prior_rows):
    names=tuple(f't{t}.car{c}.{axis}' for t in range(6) for c in [1,2] for axis in ['x','y'])
    if method=='B2':names+=('b',)
    return Layout(names,('m',)*len(names),tuple((c,t,4*t+2*c,4*t+2*c+1) for t in range(6) for c in range(2)),24 if method=='B2' else None,tuple([1.]*24+([.1] if method=='B2' else [])),68 if method=='B0' else 74,prior_rows,'range/0.04m, global displacement/0.02m, t0 prior/obs.prior_sigma m')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);z=ap.parse_args();z.out.mkdir(parents=True,exist_ok=False)
    confirmation=ROOT/'docs/research/midterm_simulation_confirmation';source=confirmation/'results/ESTIMATES.jsonl.gz'
    try:
        manifest=json.loads((confirmation/'SHA256SUMS.json').read_text())
        for name,h in manifest.items():assert sha(confirmation/name)==h,name
        frozen=json.loads((ROOT/'docs/research/midterm_simulation_validation/FREEZE_MANIFEST.json').read_text())
        for name,h in frozen['files'].items():assert sha(ROOT/name)==h,name
        rb=module('readonly_independent_readback',confirmation/'readback.py')
        b=module('readonly_prototype',ROOT/'tools/midterm_simulation_s2/prototype.py')
        inputs={};records=[]
        for line in gzip.open(source,'rt'):
            rec=json.loads(line);v=rec['value']
            if rec['type']=='RUN':run=v;assert rb.digest(run['config'])==run['config_sha256'] and rb.digest(run['plan'])==run['plan_sha256']
            elif rec['type']=='INPUT':
                key=v['condition']['id']+'-s'+str(v['seed']);assert key not in inputs;inputs[key]=v;assert rb.digest(v['obs'])==v['input_sha256']
            else:records.append(v)
        assert len(inputs)==1800 and len(records)==7200 and len({(r['unit'],r['method']) for r in records})==7200
        assert sum(r['stages']['P1']['accepted'] for r in records)==7175
        assert sum(r['stages']['P1']['category']=='NOT_STATIONARY' for r in records)==25
        assert all(rb.digest(inputs[r['unit']])==r['input_record_sha256'] for r in records)
        observed={(r['unit'],r['method']) for r in records};expected={(p['id'],m) for p in run['plan'] for m in run['config']['methods']};assert observed==expected
        dump(z.out/'RECOVERY.json',dict(passed=True,base=BASE,inputs=1800,methods=7200,accepted=7175,not_stationary=25,portable_sha256=sha(source),frozen_source_sha256=run['source_sha256'],config_sha256=run['config_sha256']))
    except Exception as e:
        dump(z.out/'DIAGNOSTIC_FAILURE.json',dict(stage='source_recovery',error=repr(e)));raise
    n=len(records);marg=np.full((n,3,12,3),np.nan);q=np.full((n,3,12),np.nan);q_b=np.full((n,3),np.nan);var_b=np.full((n,3),np.nan);err=np.zeros((n,12,2));berr=np.full(n,np.nan)
    coupling=np.full((n,3,12),np.nan);corr=np.full((n,3,24),np.nan);reasons=np.full((n,3,12),'',dtype='<U40');b_reasons=np.full((n,3),'NOT_A_BIAS_METHOD',dtype='<U40')
    meta=[];info_rows=[];refrows=[];seen=set();maxcost=0.;maxgrad=0.;maxschur=0.;maxparity=0.;maxorder=0.
    with gzip.open(z.out/'SPECTRA.jsonl.gz','xt') as sf:
        for k,rec in enumerate(records):
            u=inputs[rec['unit']];s=rec['stages']['P1'];method=rec['method'];x=np.array(s['estimate']);r,j=rb.objective(u,method,x);np_rows=4 if u['obs']['prior_sigma'] is not None else 0
            a=j[:-4] if np_rows else j;l=j[-4:] if np_rows else np.empty((0,len(x)))
            maxcost=max(maxcost,abs(float(r@r/2)-s['cost']));maxgrad=max(maxgrad,abs(float(max(abs(j.T@r)))-s['gradient_inf']))
            assert maxcost<1e-10 and maxgrad<1e-9
            assert s['accepted']==(s['scipy_success'] and np.isfinite(x).all() and max(abs(j.T@r))<=1e-5)
            truth=np.r_[np.array(u['truth']).ravel(),u['condition']['bias_m']] if method=='B2' else np.array(u['truth']).ravel()
            e=x-truth;err[k]=e[:24].reshape(12,2)
            assert np.allclose(np.mean(np.sum(e[:24].reshape(6,2,2)**2,axis=2),axis=0),s['position_mse'],atol=1e-12,rtol=0)
            if method=='B2':berr[k]=e[-1];assert abs(berr[k]-s['bias_error'])<1e-12
            spec=layout(method,np_rows)
            d=diagnose(state=x,error=e,j_data=a,j_prior=l,layout=spec,actual_noise=Noise('identity',spec.data_rows),numerical_status={'accepted':s['accepted'],'category':s['category'],'gradient_inf':s['gradient_inf']})
            base=dict(index=k,unit=rec['unit'],**u['condition'],seed=u['seed'],method=method,accepted=s['accepted'],category=s['category'],gradient_inf=s['gradient_inf'],cost=s['cost'],data_residual_rms=float(np.sqrt(np.mean(r[:len(a)]**2))),total_residual_rms=float(np.sqrt(np.mean(r**2))),position_rmse=float(np.sqrt(np.mean(np.sum(err[k]**2,axis=1)))))
            meta.append(base)
            for name in ['data','total']:
                inf=d[name];row=dict(**base,matrix=name,rank=inf['rank'],dimension=len(x),condition=inf['condition'],smax=inf['singular_values'][0],smin=inf['singular_values'][-1],reason=inf['reason'],**{'rank_'+t:v for t,v in inf['rank_sensitivity'].items()})
                if method=='B2':row['bias_null_component_norm']=float(np.linalg.norm(inf['nullspace'][-1]))
                info_rows.append(row)
                sf.write(json.dumps(clean(dict(index=k,matrix=name,**spectrum(inf))))+'\n')
            for v,name in enumerate(VIEWS):
                for p,block in enumerate(d['positions'][name]):
                    reasons[k,v,p]=block['reason'] if block['available'] or d['matrices'][name] is not None else (d['data']['reason'] if name=='data_only' else d['total']['reason'])
                    if block['available']:
                        c=block['covariance'];marg[k,v,p]=[c[0,0],c[0,1],c[1,1]];q[k,v,p]=block['q']
                if method=='B2':
                    bb=d['bias'][name];b_reasons[k,v]=bb['reason'] if d['matrices'][name] is not None else (d['data']['reason'] if name=='data_only' else d['total']['reason'])
                    if bb['available']:q_b[k,v]=bb['q'];var_b[k,v]=bb['trace']
                    vals=d['coupling'][name]
                    if vals['coordinate_correlations']:corr[k,v]=vals['coordinate_correlations'];coupling[k,v]=vals['position_multiple_R2']
            # Same-point Schur check and variance-order check; avoid normal-equation test in ill-conditioning.
            cov=d['matrices']['total_curvature'];noise=d['matrices']['fixed_prior_noise']
            if cov is not None:
                mine=float(np.linalg.eigvalsh(cov-noise)[0]);maxorder=max(maxorder,max(0.,-mine)/max(1,np.linalg.norm(cov,2)))
                assert mine>=-1e-8*max(1,np.linalg.norm(cov,2))
                if method=='B2' and d['total']['condition']<1e4:
                    h=j.T@j;schur=h[:24,:24]-h[:24,24:25]@h[24:25,:24]/h[24,24]
                    relative=float(np.linalg.norm(np.linalg.inv(schur)-cov[:24,:24])/max(1,np.linalg.norm(cov[:24,:24])));maxschur=max(maxschur,relative);assert relative<1e-7
            key=(u['condition']['id'],method)
            if key not in seen:
                fun,_,_=b.problem(u['obs'],method,np.array(u['oracle']) if method=='B3' else None);rr,jj=fun(x)
                maxparity=max(maxparity,float(max(abs(rr-r))),float(np.max(abs(jj-j))));assert maxparity<1e-10
                _,jr=rb.objective(u,method,truth)
                for label,jref in [('data',jr[:-4] if np_rows else jr),('total',jr)]:
                    ir=information(jref,spec.scales)
                    refrow=dict(condition_id=key[0],method=method,geometry=u['condition']['geometry'],motion=u['condition']['motion'],panel=u['condition']['panel'],kind=u['condition']['kind'],bias_m=u['condition']['bias_m'],matrix=label,**spectrum(ir))
                    if method=='B2':
                        ppos=jref[:,:24];qb=jref[:,24];uu,ss,_=np.linalg.svd(ppos,full_matrices=False);rank=int(sum(ss>ss[0]*1e-8));proj=qb-uu[:,:rank]@(uu[:,:rank].T@qb)
                        refrow.update(bias_null_norm=float(np.linalg.norm(ir['nullspace'][-1])),bias_effective_information=float(proj@proj))
                    refrows.append(refrow)
                seen.add(key)
            if (k+1)%1200==0:print('readback',k+1,'/7200',flush=True)
    np.savez_compressed(z.out/'MARGINALS.npz',covariance_components=marg,position_q=q,bias_q=q_b,bias_variance=var_b,position_error=err,bias_error=berr,position_bias_multiple_R2=coupling,coordinate_bias_correlations=corr,reasons=reasons,bias_reasons=b_reasons)
    csvout(z.out/'RUNS.csv',meta);csvout(z.out/'INFORMATION.csv',info_rows);dump(z.out/'REFERENCE_INFORMATION.json',refrows)
    dump(z.out/'CHECKS.json',dict(passed=True,methods=n,accepted=sum(r['accepted'] for r in meta),not_stationary=25,optimizer_calls=0,new_localization_observations=0,max_cost_difference=maxcost,max_gradient_norm_difference=maxgrad,prototype_crosscheck_cases=len(seen),max_prototype_difference=maxparity,max_schur_relative_difference=maxschur,max_noise_order_violation_relative=maxorder,position_block_order='t0.car1,t0.car2,...,t5.car2',covariance_component_order=['xx','xy','yy'],views=VIEWS))
    dump(z.out/'PROVENANCE.json',dict(base=BASE,analysis_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),python=sys.version,numpy=np.__version__,scipy=scipy.__version__,protocol_sha256=sha(ROOT/'docs/research/midterm_uncertainty_a/ANALYSIS_PROTOCOL.md'),code_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},input_sha256=sha(source)))
if __name__=='__main__':main()
