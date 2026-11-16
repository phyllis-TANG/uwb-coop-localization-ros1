"""Noise covariance probes and exposed-seed pipeline regression; no new formal inputs."""
import argparse,copy,time
from pathlib import Path
import numpy as np
from io_utils import DOC,read,save
from noise_adapter import conditions,generate,transform
import run as engine
from noise_readback import base as readback
from analyze import analyze

def checks(out,fault_dev):
    out.mkdir(parents=True,exist_ok=False);c=read(DOC/'noise_exploration/CONFIG.json');probe=c['noise_generator_check'];rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([probe['development_seed'],probe['stream']])));z=rng.normal(size=(probe['independent_probe_blocks'],6,9));covs={}
    for name,model in c['range_noise_models'].items():
        noise=transform(z,model);sigma=model['actual_marginal_sigma_m'];rho=model.get('rho',0.);target=sigma*sigma*rho**np.abs(np.arange(6)[:,None]-np.arange(6)[None,:]);emp=np.cov(noise.transpose(0,2,1).reshape(-1,6),rowvar=False,ddof=0);cross=np.corrcoef(noise[:,0,:],rowvar=False)-np.eye(9);diff=float(np.max(abs(emp-target))/(sigma*sigma));corr=float(np.max(abs(cross)));assert diff<probe['covariance_max_abs_error_relative_to_variance'] and corr<probe['cross_link_correlation_max_abs']
        covs[name]=dict(empirical_covariance=emp.tolist(),theoretical_covariance=target.tolist(),maximum_covariance_error_relative_to_variance=diff,maximum_cross_link_correlation=corr,first_epoch_std=float(np.std(noise[:,0,:])),innovation_sigma=sigma*np.sqrt(1-rho*rho))
    begin=time.perf_counter();engine.run(out/'panel',c,'development',workers=2);units=0;maxdiff=0.
    for q in conditions(c):
        u=read(out/'panel/inputs'/f"{q['id']}-s26011601.json.gz");assert u['obs']['range_sigma']==.04;units+=1
        for m in c['methods']:
            if q['noise_model']=='iid_004':
                # Compare to saved first-batch DEVELOPMENT panel, never replay old formal seeds.
                found=None
                for p in (fault_dev/'inputs').glob('*.gz'):
                    old=read(p);oq=old['condition']
                    if all(oq[k]==q[k] for k in ['geometry','motion','candidate','injection']):found=old;break
                assert found is not None and found['obs']==u['obs']
                for stage in ['P0','P1']:
                    a=read(out/'panel/stages'/f"{q['id']}-s26011601"/f'{m}-{stage}.json.gz')['result'];b=read(fault_dev/'stages'/f"{found['condition']['id']}-s26011601"/f'{m}-{stage}.json.gz')['result'];maxdiff=max(maxdiff,float(np.max(abs(np.array(a['estimate'])-b['estimate']))))
    ck=readback.raw(out/'panel',out/'readback');readback.portable_check(out/'readback',out/'PORTABLE_CHECKS.json');analyze(out/'readback',out/'analysis');assert maxdiff==0.
    result=dict(passed=True,formal_runs=0,formal_observations_generated=0,covariance_probe=probe,covariances=covs,development_inputs=units,baseline_regression_max_endpoint_diff=maxdiff,readback=ck,elapsed_s=time.perf_counter()-begin,stage_bytes=sum(p.stat().st_size for p in (out/'panel/stages').rglob('*.gz')),failure_resume_contract='unchanged frozen engine; original failure/missing/resume checks retained')
    save(out/'CHECKS.json',result);print(result)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--fault-dev',type=Path,required=True);a=p.parse_args();checks(a.out,a.fault_dev)
