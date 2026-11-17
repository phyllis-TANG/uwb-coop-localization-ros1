"""Read-only PR112 diagnostic and cached-array equivalence, before new fitting."""
from common import *
import argparse,time,collections
from scipy.stats import chi2

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False);begin=time.perf_counter()
    hashes=read(OLD/'SHA256SUMS.json')['files']
    for p,h in hashes.items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
    inputs={z['id']:z for z in records(OLD/'INPUTS.jsonl.gz')};ends={(z['id'],z['method'],z['init']):z for z in records(OLD/'results/ENDPOINTS.jsonl.gz')};sel=read(OLD/'results/readback/SELECTION.json');rows=list(csv.DictReader((OLD/'results/readback/ENDPOINT_METRICS.csv').open()))
    d=cached_npz(OLD/'results/readback/POINTS.npz');load_s=time.perf_counter()-begin;counts=0;maxmetric=0.
    lookup={(r['id'],r['method']):r for r in sel}
    def endpoint(uid,m,i):return inputs[uid]['original'][m]['P1'] if i=='I0' else ends[(uid,m,i)]['stages']['P1']
    for s in sel:
        cand=[(endpoint(s['id'],s['method'],i)['cost'],i) for i in ['I0','I1','I2','I3','I4'] if endpoint(s['id'],s['method'],i)['accepted']];assert min(cand)[1]==s['selected_init']
    cats=collections.Counter(r['category'] for r in rows);assert cats=={'ACCEPTED':3592,'NOT_STATIONARY':8}
    for i,r in enumerate(rows):
        mse=np.mean(np.sum(d['error'][i].reshape(6,2,2)**2,axis=-1),axis=0);maxmetric=max(maxmetric,abs(np.sqrt(mse[0])-float(r['rmse_car1'])),abs(np.sqrt(mse[1])-float(r['rmse_car2'])));assert maxmetric<1e-12
    thresholds={level:float(chi2.ppf(level,2)) for level in [.95,.99]}
    for row in csv.DictReader((OLD/'results/summary/COVERAGE.csv').open()):
        ss=[s for s in sel if s['condition']==row['condition'] and s['method']==row['method']];av=hit=0;mode=row['mode'];v=0 if row['view']=='curvature' else 1;keys=np.arange(int(row['car'])-1,12,2);agg=row['aggregation']
        for s in ss:
            i=s['original_index'] if mode=='original' or mode=='original_accepted' and rows[s['original_index']]['accepted']=='True' else s['selected_index'] if mode=='selected' or mode=='stable_selected' and s['stable_all_five'] else None
            if i is None:continue
            q=d['q'][i,v,keys];valid=np.isfinite(q);covered=valid&(q<=thresholds[float(row['level'])])
            if agg=='point_mean':av+=int(valid.sum());hit+=int(covered.sum())
            elif agg=='trajectory_all':av+=int(valid.all());hit+=int(covered.all())
            else:t=int(agg[1:]);av+=int(valid[t]);hit+=int(covered[t])
        assert av==int(row['available']) and hit==int(row['covered']) and int(row['unavailable'])==int(row['planned'])-av;counts+=1
    representatives=[];matrices=[];maxold=0.
    for z in csv.DictReader((OLD/'results/diagnostics/HESSIAN.csv').open()):
        u=inputs[z['id']]['input'];m=z['method'];x=np.array(endpoint(z['id'],m,z['init'])['estimate']);r,w,g,e=weak_curvature(u,m,x);maxold=max(maxold,abs(r['overall_relative_frobenius']-float(z['second_order_relative_norm'])));assert maxold<1e-10
        representatives.append(dict(id=z['id'],method=m,mode=z['mode'],init=z['init'],geometry=u['condition']['geometry'],mechanism=u['condition']['mechanism'],prior_sigma=u['obs']['prior_sigma'],**r));matrices.append(dict(id=z['id'],method=m,mode=z['mode'],scaled_weak_basis=w.tolist(),projected_gn=g.tolist(),projected_exact=e.tolist()))
    assert len(representatives)==48
    # Subspace invariance under a rotation in an exactly repeated weakest eigenspace.
    g=np.diag([1.,1.,9.]);e=g+np.array([[.3,.2,0],[.2,-.1,0],[0,0,.01]]);r,w,gp,ep=project_weak(g,e);assert r['weak_dimension']==2
    angle=.43;rot=np.array([[np.cos(angle),-np.sin(angle)],[np.sin(angle),np.cos(angle)]]);assert np.allclose(np.linalg.eigvalsh(ep-gp),np.linalg.eigvalsh(rot.T@(ep-gp)@rot))
    csvsave(out/'WEAK_DIRECTIONS.csv',representatives);save(out/'PROJECTED_MATRICES.json',matrices);save(out/'CHECKS.json',dict(source_files_verified=len(hashes),npz_open_count=1,npz_members_decompressed_once=len(d),coverage_rows_checked=counts,selection_identities_checked=len(sel),planned_candidates=3600,categories=dict(cats),max_rmse_difference=maxmetric,max_previous_hessian_norm_difference=maxold,representative_endpoints=48,subspace_rotation_check='PASS',optimizer_calls=0,load_and_hash_seconds=load_s,total_seconds=time.perf_counter()-begin));print(read(out/'CHECKS.json'))
if __name__=='__main__':main()
