"""Development only: no CLI mode or seed override can launch formal evaluation."""
import argparse,csv,json,subprocess,hashlib,shutil
from pathlib import Path
import numpy as np
from prototype import ROOT,METHODS,generate,solve,problem,information,digest

def evaluate(result,truth,bias):
    if result['estimate'] is None:return []
    xy=np.array(result['estimate'][:24]).reshape(6,2,2)
    cov=result['posterior_information']['covariance'];cov=None if cov is None else np.array(cov)
    out=[]
    for car in range(2):
        mse=float(np.mean(np.sum((xy[:,car]-truth[:,car])**2,axis=1)))
        ids=np.array([[4*t+2*car,4*t+2*car+1] for t in range(6)])
        tr=None if cov is None else float(np.mean([np.trace(cov[np.ix_(i,i)]) for i in ids]))
        out.append(dict(car=f'car{car+1}',mse_m2=mse,rmse_m=float(np.sqrt(mse)),mean_position_cov_trace_m2=tr,
                        bias_error_m=float(result['estimate'][-1]-bias) if result['method']=='B2' else None))
    return out

def main(dest):
    dest.mkdir(parents=True,exist_ok=False)
    assert shutil.disk_usage(dest).free>100_000_000
    cfg=json.loads((ROOT/'docs/research/midterm_simulation_s2/CONFIG.json').read_text())
    assert cfg['formal_validation_enabled'] is False
    registry=json.loads((ROOT/'docs/research/midterm_simulation_s2/SEED_REGISTRY.json').read_text())
    assert cfg['development_seeds']==registry['development_seeds']
    for p,h in json.loads((ROOT/'docs/research/midterm_simulation_s2/SOURCE_LOCK.json').read_text()).items():
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
    provenance=dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    config_sha256=digest(cfg),code_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'tools/midterm_simulation_s2').glob('*.py')})
    jobs=[(p,0) for p in cfg['deterministic_profiles']]+[(p,s) for p in cfg['noisy_profiles'] for s in cfg['development_seeds']]
    rows=[];units=0
    with (dest/'UNITS.jsonl').open('x') as f:
        for profile,seed in jobs:
            for geom in cfg['geometries']:
                for motion in cfg['motions']:
                    for kind in cfg['links']:
                        for bias in cfg['biases_m']:
                            assert shutil.disk_usage(dest).free>100_000_000
                            obs,truth,oracle,noise=generate(geom,motion,kind,bias,profile,seed,cfg)
                            metadata=dict(profile=profile,seed=seed,geometry=geom,motion=motion,kind=kind,bias_m=bias)
                            results=[]
                            for method in METHODS:
                                result=solve(obs,method,cfg,oracle if method=='B3' else None)
                                result['metrics']=evaluate(result,truth,bias)
                                fun,_,_=problem(obs,method,oracle if method=='B3' else None)
                                reference=np.r_[truth.ravel(),bias] if method=='B2' else truth.ravel()
                                j=fun(reference)[1];data_j=j[:-4] if obs['prior_sigma'] is not None else j
                                refinfo=information(data_j,cfg['rank_relative_tol'])
                                result['reference_data_rank']=refinfo['rank']
                                for metric in result['metrics']:
                                    if method!='B0':
                                        base=next(x for x in results[0]['metrics'] if x['car']==metric['car'])
                                        metric['D_m2']=metric['mse_m2']-base['mse_m2']
                                    else:metric['D_m2']=0.
                                    rows.append(dict(**metadata,method=method,status=result['status'],success=result['success'],
                                                     data_rank=result['data_information']['rank'],posterior_rank=result['posterior_information']['rank'],
                                                     reference_data_rank=refinfo['rank'],nfev=result['nfev'],elapsed_s=result['elapsed_s'],
                                                     residual_rms=result['whitened_residual_rms'],**metric))
                                if not result['metrics']:
                                    for car in ['car1','car2']:rows.append(dict(**metadata,method=method,status=result['status'],success=False,car=car,elapsed_s=result['elapsed_s']))
                                results.append(result)
                            unit=dict(**metadata,observation_sha256=digest(obs),truth_sha256=digest(truth.tolist()),noise_sha256=digest(noise),
                                      oracle_sha256=digest(oracle.tolist()),results=results)
                            f.write(json.dumps(unit,allow_nan=False)+'\n');f.flush();units+=1
            print(profile,seed,'complete',flush=True)
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (dest/'PER_RUN.csv').open('x') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
    (dest/'PROVENANCE.json').write_text(json.dumps(dict(**provenance,units=units,method_runs=units*4,rows=len(rows)),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();main(a.output)
