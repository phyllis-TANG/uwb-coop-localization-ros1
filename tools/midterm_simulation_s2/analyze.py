"""Read-only development audit and plots; never launches estimator runs."""
import argparse,collections,csv,gzip,json,math,shutil
from pathlib import Path
import numpy as np
from prototype import ROOT,generate,problem,information,digest

def writecsv(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)

def main(src,dest):
    cfg=json.loads((dest/'CONFIG.json').read_text())
    units=[json.loads(x) for x in (src/'UNITS.jsonl').open()]
    expected=len(cfg['geometries'])*len(cfg['motions'])*len(cfg['links'])*len(cfg['biases_m'])*(len(cfg['deterministic_profiles'])+len(cfg['noisy_profiles'])*len(cfg['development_seeds']))
    assert len(units)==expected==192
    keys=lambda u:(u['profile'],u['seed'],u['geometry'],u['motion'],u['kind'],u['bias_m'])
    index={keys(u):u for u in units};assert len(index)==len(units)
    max_metric=0.;max_residual=0.;fairness=0;null_cov=0;rank_reference=0;rows=[];independent_b0_checks=0
    for u in units:
        obs,truth,oracle,noise=generate(u['geometry'],u['motion'],u['kind'],u['bias_m'],u['profile'],u['seed'],cfg)
        assert digest(obs)==u['observation_sha256'] and digest(noise)==u['noise_sha256']
        refnoise=index[(*keys(u)[:-1],0.)]['noise_sha256'];assert refnoise==u['noise_sha256']
        b0=u['results'][0];base=np.array(b0['estimate'][:24]).reshape(6,2,2) if b0['estimate'] else None
        if u['kind']=='peer':
            paired=index[(*keys(u)[:-1],0.)]['results'][0]
            assert b0['input_sha256']==paired['input_sha256'] and b0['estimate']==paired['estimate'];independent_b0_checks+=1
        consumed=[]
        for r in u['results']:
            fun,start,receipt=problem(obs,r['method'],oracle if r['method']=='B3' else None)
            assert digest(receipt)==r['input_sha256']
            consumed.append(receipt)
            if r['estimate'] is None:continue
            q=np.array(r['estimate']);res,j=fun(q)
            max_residual=max(max_residual,abs(float(res@res)-r['residual_sum_squares']))
            cov=r['posterior_information']['covariance']
            if r['posterior_information']['rank']<len(q):assert cov is None;null_cov+=1
            if r['reference_data_rank']<len(q):rank_reference+=1
            if cov is not None:
                # Independent inverse consistency in physical units, scaled relative residual.
                c=np.array(cov);normal=j.T@j
                backward=np.linalg.norm(normal@c-np.eye(len(q)),ord=np.inf)/(np.linalg.norm(normal,ord=np.inf)*np.linalg.norm(c,ord=np.inf)+1)
                assert backward<1e-10
            for metric in r['metrics']:
                car=int(metric['car'][-1])-1
                err=[sum((q[4*t+2*car+k]-truth[t,car,k])**2 for k in range(2)) for t in range(6)]
                mse=sum(err)/6
                bm=sum(sum((base[t,car,k]-truth[t,car,k])**2 for k in range(2)) for t in range(6))/6
                max_metric=max(max_metric,abs(mse-metric['mse_m2']),abs(mse-bm-metric['D_m2']))
                rows.append(dict(**{k:u[k] for k in ['profile','seed','geometry','motion','kind','bias_m']},method=r['method'],**metric,
                                 success=r['success'],status=r['status'],scipy_success=r['scipy_success'],optimality=r['optimality'],elapsed_s=r['elapsed_s']))
        # B1/B2 share range target, starts, motion, prior; B3 changes only ranges.
        for field in ['anchors','movement','prior_center','prior_sigma','range_sigma','motion_sigma']:
            assert all(x[field]==consumed[0][field] for x in consumed)
        assert consumed[1]['ranges']==consumed[2]['ranges']
        assert consumed[0]['start']==consumed[1]['start']==consumed[2]['start'][:24]==consumed[3]['start']
        for c in [consumed[1],consumed[2],consumed[3]]:
            assert np.allclose(np.delete(c['ranges'],np.arange(8,54,9)),consumed[0]['ranges'],atol=1e-14,rtol=0) or (u['kind']=='wall' and c is consumed[3])
        fairness+=1
    assert max_metric<1e-12 and max_residual<1e-10
    groups=collections.defaultdict(list)
    for r in rows:groups[tuple(r[k] for k in ['profile','geometry','motion','kind','bias_m','method','car'])].append(r)
    summary=[]
    for key,rr in groups.items():
        out=dict(zip(['profile','geometry','motion','kind','bias_m','method','car'],key));out.update(n_runs=len(rr),n_success=sum(x['success'] for x in rr),failure_rate=sum(not x['success'] for x in rr)/len(rr),denominator='all finite last iterates; includes NOT_CONVERGED')
        for field in ['rmse_m','D_m2','bias_error_m','mean_position_cov_trace_m2','elapsed_s']:
            vals=[x[field] for x in rr if x[field] is not None]
            out[field+'_mean']=float(np.mean(vals)) if vals else None
            out[field+'_min']=min(vals) if vals else None;out[field+'_max']=max(vals) if vals else None
        valid=[x['rmse_m'] for x in rr if x['success']]
        out['successful_only_rmse_mean']=float(np.mean(valid)) if valid else None
        summary.append(out)
    writecsv(dest/'SUMMARY.csv',summary)
    costs=[]
    for u in units:
        if u['bias_m']!=0:continue
        b1,b2=u['results'][1:3]
        for a,b in zip(b1['metrics'],b2['metrics']):
            ca,cb=a['mean_position_cov_trace_m2'],b['mean_position_cov_trace_m2']
            costs.append(dict(**{k:u[k] for k in ['profile','seed','geometry','motion','kind']},car=a['car'],
                              B2_minus_B1_mse_m2=b['mse_m2']-a['mse_m2'],B2_minus_B1_rmse_m=b['rmse_m']-a['rmse_m'],
                              covariance_trace_ratio=cb/ca if ca is not None and cb is not None and ca>0 else None,
                              both_success=b1['success'] and b2['success'],
                              B1_covariance_interpretation='local at final iterate, not validated uncertainty',B2_covariance_interpretation='local at final iterate, not validated uncertainty'))
    writecsv(dest/'ZERO_BIAS_COST.csv',costs)
    failure=[]
    for p in cfg['deterministic_profiles']+cfg['noisy_profiles']:
        for geom in cfg['geometries']:
            for method in ['B0','B1','B2','B3']:
                rr=[r for u in units if u['profile']==p and u['geometry']==geom for r in u['results'] if r['method']==method]
                failure.append(dict(profile=p,geometry=geom,method=method,n=len(rr),success=sum(r['success'] for r in rr),scipy_success=sum(r.get('scipy_success',False) for r in rr),failures=sum(not r['success'] for r in rr),max_nfev=sum(r.get('scipy_status')==0 for r in rr),rank_deficient=sum(r.get('posterior_information',{}).get('rank',25)<(25 if method=='B2' else 24) for r in rr)))
    writecsv(dest/'FAILURE_SUMMARY.csv',failure)
    out=dict(status='PASS',units=len(units),method_runs=4*len(units),fairness_checks=fairness,B0_peer_identity_checks=independent_b0_checks,
             max_metric_recompute_error=max_metric,max_residual_recompute_error=max_residual,rank_deficient_final_iterates=null_cov,
             rank_deficient_reference_data_cases=rank_reference,formal_runs=0)
    with (dest/'INDEPENDENT_CHECKS.json').open('x') as f:json.dump(out,f,indent=2)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(2,2,figsize=(11,8),sharex=True)
    # One representative motion only; do not pool movements into n.
    for ci,car in enumerate(['car1','car2']):
        for ki,kind in enumerate(['wall','peer']):
            ax=axs[ci,ki]
            for method in ['B0','B1','B2','B3']:
                rr=[s for s in summary if s['profile']=='noisy_unbiased_prior' and s['geometry']=='good' and s['motion']=='turn' and s['kind']==kind and s['car']==car and s['method']==method]
                rr.sort(key=lambda s:s['bias_m']);x=[s['bias_m'] for s in rr];y=[s['rmse_m_mean'] for s in rr]
                ax.errorbar(x,y,yerr=[[s['rmse_m_mean']-s['rmse_m_min'] for s in rr],[s['rmse_m_max']-s['rmse_m_mean'] for s in rr]],marker='o',capsize=3,label=method)
            ax.set_title(f'{car}, {kind}, good/turn');ax.set_ylabel('XY RMSE (m)');ax.set_xlabel('injected constant bias (m)');ax.legend()
    fig.suptitle('Development n=3; mean/range of final iterates INCLUDING nonconvergence')
    fig.tight_layout();fig.savefig(dest/'DEVELOPMENT_RMSE.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(11,4))
    for idx,geom in enumerate(['good','weak']):
        rr=[r for r in failure if r['geometry']==geom and r['profile'].startswith('noisy')]
        for off,p in enumerate(cfg['noisy_profiles']):
            ss=[r for r in rr if r['profile']==p];axs[idx].bar(np.arange(4)+off*.35,[r['failures']/r['n'] for r in ss],width=.35,label=p)
        axs[idx].set_xticks(np.arange(4)+.175,['B0','B1','B2','B3']);axs[idx].set_ylim(0,1);axs[idx].set_title(geom);axs[idx].set_ylabel('nonconvergence fraction');axs[idx].legend(fontsize=7)
    fig.tight_layout();fig.savefig(dest/'FAILURES.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for idx,car in enumerate(['car1','car2']):
        for ki,kind in enumerate(['wall','peer']):
            rr=[r for r in costs if r['car']==car and r['profile']=='noisy_unbiased_prior' and r['geometry']=='good' and r['kind']==kind]
            axs[idx].scatter([ki]*len(rr),[r['covariance_trace_ratio'] for r in rr],label=kind,alpha=.65)
        axs[idx].axhline(1,color='k',ls='--');axs[idx].set_xticks([0,1],['wall candidate','peer candidate']);axs[idx].set_title(car);axs[idx].set_ylabel('B2/B1 local covariance trace')
    fig.suptitle('Zero bias; 3 motions x 3 seeds (not 9 independent seeds); final iterates')
    fig.tight_layout();fig.savefig(dest/'ZERO_BIAS_COVARIANCE.png',dpi=160);plt.close(fig)
    # Lossless audit bundle retains every estimate, rank, covariance and failure.
    with (src/'UNITS.jsonl').open('rb') as f, (dest/'UNITS.jsonl.gz').open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as z:shutil.copyfileobj(f,z)
    for name in ['PER_RUN.csv','PROVENANCE.json']:
        with (src/name).open('rb') as f,(dest/name).open('xb') as o:shutil.copyfileobj(f,o)
    print(json.dumps(out,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();main(a.source,a.output)
