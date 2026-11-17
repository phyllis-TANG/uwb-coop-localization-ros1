"""No optimizer imported/called: reconstruct all endpoints, covariance and pairing."""
from common import *
from model import CFG,validate_inputs
import argparse,collections,itertools
from scipy.stats import chi2

def inspect(u,m,s,checks):
    checks['stage_records']+=1
    if not s['endpoint_valid']:return None
    x=np.array(s['estimate']);r,j=objective(u,m,x);g=j.T@r;cost=float(r@r/2)
    checks['stages_checked']+=1;checks['max_cost_difference']=max(checks['max_cost_difference'],abs(cost-s['cost']));checks['max_gradient_difference']=max(checks['max_gradient_difference'],abs(float(max(abs(g)))-s['gradient_inf']))
    assert abs(cost-s['cost'])<1e-8 and abs(float(max(abs(g)))-s['gradient_inf'])<1e-8
    assert bool(s['scipy_success'] and max(abs(g))<=1e-5)==s['accepted']
    err=x[:24].reshape(6,2,2)-u['truth'];assert np.max(abs(np.mean(np.sum(err**2,axis=2),axis=0)-s['position_mse']))<1e-10
    return x,r,j,err

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--endpoints',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=False)
    newer={(z['id'],z['method'],z['init']):z for z in records(args.endpoints)};assert len(newer)==2400
    checks=dict(stage_records=0,optimizer_calls=0,stages_checked=0,max_cost_difference=0.,max_gradient_difference=0.);rows=[];pairrows=[];groupsrows=[];selection=[];qs=[];traces=[];areas=[];errors=[];reasons=[];biasqs=[];biasvars=[];states=[];gradients=[];scaled_gradients=[]
    inputs=list(records(args.inputs));input_checks=validate_inputs(inputs);weakrows=[];projected=[]
    assert len(inputs)==240
    for rec in inputs:
        u=rec['input'];cond=u['condition'];uid=rec['id']
        for m in CFG['methods']:
            candidates=[]
            for ini in CFG['initializations']:
                stages=newer[(uid,m,ini)]['stages'];s=stages['P1']
                for stage in ['P0','P1']:inspect(u,m,stages[stage],checks)
                result=inspect(u,m,s,dict(stage_records=0,stages_checked=0,max_cost_difference=0.,max_gradient_difference=0.))
                gradient=np.full(25,np.nan);scaled_gradient=gradient.copy();q=np.full((2,12),np.nan);tr=np.full((2,12),np.nan);ar=tr.copy();er=np.full((12,2),np.nan);reason=np.full((2,12),'NO_ESTIMATE',dtype='<U32');bq=np.full(2,np.nan);bv=bq.copy()
                row=dict(index=len(rows),id=uid,condition=cond['id'],geometry=cond['geometry'],mechanism=cond['mechanism'],sigma=cond['prior_sigma'],noise_scale=cond['noise_scale'],range_sigma=u['obs']['range_sigma'],motion_sigma=u['obs']['motion_sigma'],seed=u['seed'],method=m,init=ini,category=s['category'],accepted=s['accepted'],cost=s['cost'],gradient_inf=s['gradient_inf'],rank=None,condition_number=None,rank_1e6=None,rank_1e10=None,rank_1e12=None,rmse_car1=s['position_rmse'][0],rmse_car2=s['position_rmse'][1],bias_estimate=s.get('bias_estimate'),nfev=sum((stages[t]['nfev'] or 0) for t in ['P0','P1']),elapsed_s=sum(stages[t]['elapsed_s'] for t in ['P0','P1']))
                if result is not None:
                    x,r,j,err=result;wc,w,gp,ep=weak_curvature(u,m,x);weakrows.append(dict(index=len(rows),id=uid,condition=cond['id'],noise_scale=cond['noise_scale'],geometry=cond['geometry'],seed=u['seed'],method=m,init=ini,category=s['category'],**wc));projected.append(dict(index=len(rows),basis=w.tolist(),gn=gp.tolist(),exact=ep.tolist()));gradient[:len(x)]=j.T@r;scaled_gradient[:len(x)]=gradient[:len(x)]*(np.r_[np.ones(24),.1] if m=='B2' else np.ones(24));er=err.reshape(12,2);a=algebra(j,m,SOURCE,cond['mechanism']);sv=np.array(a['singular_values']);row.update(rank=a['rank'],condition_number=float(sv[0]/sv[-1]),residual_norm=float(np.linalg.norm(r)),rank_1e6=int(sum(sv>sv[0]*1e-6)),rank_1e10=int(sum(sv>sv[0]*1e-10)),rank_1e12=int(sum(sv>sv[0]*1e-12)))
                    for v,name in enumerate(['curvature','mechanism_noise']):
                        cov=a[name]
                        for k in range(12):
                            e=ellipse(None if cov is None else cov[2*k:2*k+2,2*k:2*k+2],er[k],SOURCE);reason[v,k]=e['reason'];q[v,k]=np.nan if e['q'] is None else e['q'];tr[v,k]=np.nan if e['trace'] is None else e['trace'];ar[v,k]=np.nan if e['area95'] is None else e['area95']
                        if m=='B2' and cov is not None and cov[-1,-1]>0:bv[v]=cov[-1,-1];bq[v]=(x[-1]-.3)**2/bv[v]
                gradients.append(gradient);scaled_gradients.append(scaled_gradient);rows.append(row);qs.append(q);traces.append(tr);areas.append(ar);errors.append(er);reasons.append(reason);biasqs.append(bq);biasvars.append(bv);states.append(s['estimate']);candidates.append(dict(init=ini,final=s,index=row['index']))
            accepted=[z for z in candidates if z['final']['accepted']];best=min(accepted,key=lambda z:(z['final']['cost'],z['init'])) if accepted else None
            ag=groups(candidates,m,True);fg=groups(candidates,m);sg=next((g for g in ag if best in g),[]) if best else [];near=0
            for l,r in itertools.combinations(candidates,2):
                if not l['final']['endpoint_valid'] or not r['final']['endpoint_valid']:continue
                sl,sr=l['final'],r['final'];dd=distance(sl['estimate'],sr['estimate']);dc=abs(sl['cost']-sr['cost']);flag=sl['accepted'] and sr['accepted'] and dd>legacy.CFG['distinct_position_m'] and dc<=legacy.CFG['near_cost_atol']+legacy.CFG['near_cost_rtol']*max(1,min(sl['cost'],sr['cost']));near+=int(flag)
                pairrows.append(dict(id=uid,condition=cond['id'],seed=u['seed'],method=m,left=l['init'],right=r['init'],both_accepted=sl['accepted'] and sr['accepted'],max_position_distance_m=dd,cost_difference=dc,bias_distance_m=abs(sl['estimate'][-1]-sr['estimate'][-1]) if m=='B2' else None,near_cost_distinct_position=flag))
            for kind,gg in [('finite',fg),('accepted',ag)]:
                for k,g in enumerate(gg):groupsrows.append(dict(id=uid,method=m,kind=kind,group=k,members=';'.join(z['init'] for z in g),indices=';'.join(str(z['index']) for z in g)))
            selection.append(dict(id=uid,condition=cond['id'],seed=u['seed'],method=m,original_index=candidates[0]['index'],selected_index=None if best is None else best['index'],selected_init=None if best is None else best['init'],accepted_candidates=len(accepted),finite_groups=len(fg),accepted_groups=len(ag),near_cost_distinct_pairs=near,selected_group_indices=[z['index'] for z in sg],stable_all_five=len(accepted)==5 and len(ag)==1))
    assert len(rows)==2400 and checks['stage_records']==4800
    csvsave(out/'WEAK_CURVATURE.csv',weakrows);write_records(out/'WEAK_SUBSPACES.jsonl.gz',projected);save(out/'INPUT_CHECKS.json',input_checks)
    np.savez_compressed(out/'POINTS.npz',gradient=np.array(gradients),scaled_gradient=np.array(scaled_gradients),q=np.array(qs),trace=np.array(traces),area95=np.array(areas),error=np.array(errors),reason=np.array(reasons),bias_q=np.array(biasqs),bias_variance=np.array(biasvars))
    csvsave(out/'ENDPOINT_METRICS.csv',rows);csvsave(out/'PAIRS.csv',pairrows);csvsave(out/'GROUPS.csv',groupsrows);save(out/'SELECTION.json',selection);save(out/'CHECKS.json',checks);print(checks)
if __name__=='__main__':main()
