"""Readback verification only: never invokes a solver or selects an estimate."""
import argparse,csv,gzip,json
from pathlib import Path
import numpy as np
from audit import ROOT,D,module,sha,dump,csvout,a_problem,diagnostics

def main():
    p=argparse.ArgumentParser();p.add_argument('--b-root',type=Path,required=True);p.add_argument('--a-raw',type=Path,required=True);p.add_argument('--results',type=Path,required=True);p.add_argument('--large',type=Path,required=True);p.add_argument('--out',type=Path,required=True);z=p.parse_args()
    z.out.mkdir(parents=True,exist_ok=False)
    a=module('A_verify',ROOT/'tools/midterm_simulation_s1b/analyze.py');b=module('B_verify',z.b_root/'tools/midterm_simulation_s2/prototype.py')
    cfg=json.loads((z.b_root/'docs/research/midterm_simulation_s2/CONFIG.json').read_text())
    for name,h in json.loads((z.results/'SHA256SUMS.json').read_text()).items():assert sha(z.results/name)==h,name
    for name,v in json.loads((z.results/'EXTERNAL_INDEX.json').read_text())['files'].items():assert sha(z.large/name)==v['sha256']
    inputs=[json.loads(l) for l in (z.results/'PANEL_INPUTS.jsonl').open()]
    old={}
    for line in gzip.open(z.b_root/'docs/research/midterm_simulation_s2/UNITS.jsonl.gz','rt'):
        u=json.loads(line);old[(u['geometry'],u['motion'],u['kind'],u['bias_m'],u['profile'],u['seed'])]=u
    for u in inputs:
        obs,truth,oracle,noise=b.generate(u['geometry'],u['motion'],u['kind'],u['bias'],u['profile'],u['seed'],cfg)
        assert obs==u['obs'] and noise==u['noise'] and truth.tolist()==u['truth_offline_only'] and oracle.tolist()==u['oracle_B3_only']
        assert b.digest(obs)==u['observation_sha256'] and b.digest(noise)==u['noise_sha256']
    rows=[];fdrows=[];max_endpoint_delta=0
    for line in (z.large/'PANEL_DETAILS.jsonl').open():
        x=json.loads(line);u=inputs[x['id']];obs=u['obs'];truth=np.array(u['truth_offline_only'])
        prev=old[x['geometry'],x['motion'],x['kind'],x['bias'],x['profile'],x['seed']]
        prev=next(v for v in prev['results'] if v['method']==x['method'])
        delta=float(np.max(abs(np.array(prev['estimate'])-x['original']['estimate'])))
        max_endpoint_delta=max(max_endpoint_delta,delta)
        assert delta==0 and prev['optimality']==x['original']['optimality']
        row={k:x[k] for k in ['id','geometry','motion','kind','bias','profile','seed','method']}
        for name,est in [('original',x['original']['estimate']),('continued',x['continuation']['estimate'])]:
            err=np.array(est[:24]).reshape(6,2,2)-truth
            for car in range(2):row[f'{name}_car{car+1}_rmse']=float(np.sqrt(np.mean(np.sum(err[:,car]**2,axis=-1))))
            row[name+'_bias_error']=float(est[-1]-u['bias']) if x['method']=='B2' else None
        rows.append(row)
        if x['method']=='B2':
            fun=a_problem(a,obs)
            for point,v in x['points'].items():
                q=np.array(v['state']);r,j=fun(q)
                assert np.array_equal(r,v['A_residual']) and np.array_equal(j,v['A_jacobian'])
                assert np.array_equal(j.T@r,v['A_gradient'])
                for h in [1e-5,1e-6]:
                    fd=np.column_stack([(fun(q+e*h)[0]-fun(q-e*h)[0])/(2*h) for e in np.eye(25)])
                    err=float(np.max(abs(fd-j)));assert err<2e-7
                    fdrows.append(dict(id=x['id'],point=point,h=h,whitened_jacobian_max_error=err))
    csvout(z.out/'OFFLINE_PANEL_ERRORS.csv',rows);csvout(z.out/'FINITE_DIFFERENCES.csv',fdrows)
    # Recompute reference and endpoint data ranks separately, including rank tolerance sensitivity.
    raw=[json.loads(l) for l in (z.a_raw/'RAW.jsonl').open()]
    obs={(r['scene'],r['seed']):r for r in raw if 'variant' not in r}
    ranks=[]
    for r in raw:
        if 'variant' not in r:continue
        o=obs[r['scene'],r['seed']];po=r['scene'].endswith('/peer_only');kind=r['scene'].split('/')[2]
        item=dict(scene=r['scene'],seed=r['seed'],variant=r['variant'])
        for label,q in [('reference',o['truth']),('endpoint',r['estimate'])]:
            j=a.model(np.array(q),np.array(o['anchors']),kind,po)[1]/.04
            data=np.vstack([j,a.MOTION/.02]);inf=a.information(data)
            for key in ['rank','bias_null_norm_scaled','bias_information_m_minus2']:item[label+'_'+key]=inf[key]
            for tol,rank in inf['ranks_by_rtol'].items():item[label+'_rank_'+tol]=rank
        ranks.append(item)
    csvout(z.out/'A_DATA_RANKS.csv',ranks)
    dump(z.out/'CHECKS.json',dict(input_reproductions=len(inputs),original_runs_matching_B_saved=128,max_B_saved_endpoint_delta=max_endpoint_delta,
                                B2_fd_checks=len(fdrows),max_whitened_fd_error=max(r['whitened_jacobian_max_error'] for r in fdrows),
                                A_data_rank_readbacks=len(ranks),optimizer_calls=0,truth_usage='offline evaluation and reference information only'))
    print((z.out/'CHECKS.json').read_text())
if __name__=='__main__':main()
