"""Transverse conditional/effective information; no covariance via pseudoinverse."""
from common import *
from model import reference_geometry
import argparse

def analyze(u,m,x):
    _,j=objective(u,m,x);n=len(x);_,axis,normal=reference_geometry();t=np.zeros((n,12));other=np.zeros((n,12+(m=='B2')))
    for k in range(12):t[2*k:2*k+2,k]=normal;other[2*k:2*k+2,k]=axis
    d=np.r_[np.ones(24),.1] if m=='B2' else np.ones(24)
    if m=='B2':other[-1,-1]=.1
    rows=[];mat=[]
    for name,stop in [('range',54),('range_motion',74),('total',78)]:
        a=j[:stop];sv=np.linalg.svd(a*d,compute_uv=False);threshold=sv[0]*1e-8;y=a@t;l=a@other;uu,ss,_=np.linalg.svd(l,full_matrices=False);basis=uu[:,ss>threshold];res=y-basis@(basis.T@y);q=y.T@y;eff=res.T@res;sy=np.linalg.svd(y,compute_uv=False);se=np.linalg.svd(res,compute_uv=False)
        rows.append(dict(component=name,dimension=n,full_rank=int(sum(sv>threshold)),threshold=float(threshold),full_singular_min=float(sv[-1]),full_singular_max=float(sv[0]),transverse_conditional_rank=int(sum(sy>threshold)),transverse_effective_rank=int(sum(se>threshold)),conditional_trace=float(np.trace(q)),effective_trace=float(np.trace(eff)),conditional_min=float(np.linalg.eigvalsh(q)[0]),effective_min=float(np.linalg.eigvalsh(eff)[0]),effective_max=float(np.linalg.eigvalsh(eff)[-1]),nuisance_rank=int(sum(ss>threshold))))
        mat.append(dict(component=name,full_singular_values=sv.tolist(),conditional=q.tolist(),effective=eff.tolist()))
    return rows,mat

def main():
    p=argparse.ArgumentParser();p.add_argument('--results',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);inp={r['id']:r for r in records(a.results/'INPUTS.jsonl.gz')};table=[];matrices=[];truthrows=[];seen=set()
    for index,z in enumerate(records(a.results/'ENDPOINTS.jsonl.gz')):
        u=inp[z['id']]['input'];s=z['stages']['P1'];base=dict(index=index,id=z['id'],condition=u['condition']['id'],perturbation_m=u['condition']['perturbation_m'],seed=u['seed'],method=z['method'],init=z['init'],category=s['category'])
        if s['endpoint_valid']:
            rows,mat=analyze(u,z['method'],np.array(s['estimate']));table.extend(dict(**base,**r) for r in rows);matrices.append(dict(index=index,matrices=mat))
        key=(u['condition']['id'],z['method'])
        if key not in seen:
            seen.add(key);x=np.r_[np.array(u['truth']).ravel(),u['condition']['bias_m']] if z['method']=='B2' else np.array(u['truth']).ravel();rows,mat=analyze(u,z['method'],x);truthrows.extend(dict(condition=key[0],method=key[1],perturbation_m=u['condition']['perturbation_m'],**r) for r in rows)
    csvsave(out/'ENDPOINT_INFORMATION.csv',table);csvsave(out/'TRUTH_DESIGN_INFORMATION.csv',truthrows);write_records(out/'MATRICES.jsonl.gz',matrices)
    save(out/'CHECKS.json',dict(endpoint_components=len(table),truth_design_components=len(truthrows),optimizer_calls=0,transverse_units='m^-2',conditional_not_marginal=True))
if __name__=='__main__':main()
