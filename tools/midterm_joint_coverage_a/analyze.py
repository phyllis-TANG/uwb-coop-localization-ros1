"""Shard-wise saved endpoint audit and A/B/C covariance reconstruction, never fit."""
import argparse,collections,os,subprocess,time
from common import *
import adapter

def verify_noise(u,c,batch):
    rb.check_input(u,c)
    seed=u['seed'];rng=np.random.default_rng(np.random.SeedSequence([seed,c['noise']['range_stream']]))
    z=rng.normal(size=(6,9));model=u['condition'].get('noise_model','iid_004')
    if model=='iid_004':expected=.04*z
    elif model=='iid_008':expected=.08*z
    else:
        expected=np.empty((6,9))
        for t in range(6):expected[t]=.04*.7**t*z[0]+sum((.04*np.sqrt(1-.7**2)*.7**(t-j)*z[j] for j in range(1,t+1)),start=np.zeros(9))
    assert np.max(abs(expected.ravel()-u['noise']['range']))<1e-14
    motion=np.random.default_rng(np.random.SeedSequence([seed,c['noise']['motion_stream']])).normal(0,.02,20)
    assert np.array_equal(motion,u['noise']['motion'])

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--batch',choices=list(CFG['batches']),required=True);ap.add_argument('--source-checks',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--resume',action='store_true');args=ap.parse_args()
    source=json.loads(args.source_checks.read_text());assert source['passed'] and source['base']==CFG['source_sha'];spec=CFG['batches'][args.batch]
    fingerprint={p.name:sha(p) for p in [Path(__file__),Path(__file__).with_name('common.py'),DOC/'CONFIG.json']}
    if args.out.exists():assert args.resume
    else:args.out.mkdir(parents=True)
    for number,p in enumerate(sorted((ROOT/spec['directory']/'results').glob('EVIDENCE-*.jsonl.gz'))):
        assert sha(p)==source['batches'][args.batch]['shards'][p.name]
        target=args.out/f'shard-{number:03d}';done=target/'DONE.json'
        if done.exists():
            old=json.loads(done.read_text());assert old['code']==fingerprint and old['source']==sha(p)
            for name,h in old['outputs'].items():assert sha(target/name)==h
            print('resume verified',target.name,flush=True);continue
        if target.exists():target.rename(args.out/(target.name+'.incomplete-'+str(time.time_ns())))
        target.mkdir();meta,units,recs=read_shard(p);c=meta['config'];n=len(recs)
        for u in units.values():verify_noise(u,c,args.batch)
        cov=np.full((n,3,12,3),np.nan);q=np.full((n,3,12),np.nan);errors=np.full((n,12,2),np.nan);reasons=np.full((n,3,12),4,np.uint8)
        bv=np.full((n,3),np.nan);bq=np.full((n,3),np.nan);be=np.full(n,np.nan);spectra=np.full((n,2,25),np.nan);eligible=np.zeros(n,bool)
        rows=[];infos=[];checks=rb.newchecks();checks['inputs']=len(units);max_cross=0.;max_cov=0.;cross_n=0
        for i,rec in enumerate(recs):
            u=units[rec['unit']];m=rec['method'];s=rec['stages']['P1'];obs=u['obs'];assert obs['range_sigma']==.04 and obs['motion_sigma']==.02 and obs['prior_sigma']==.5
            for ss in rec['stages'].values():
                rb.audit_stage(u,m,ss,c,checks,False)
                if ss['endpoint_valid']:
                    cat='ACCEPTED' if ss['accepted'] else 'BUDGET_EXHAUSTED' if ss['hit_budget'] else 'NOT_STATIONARY' if ss['gradient_inf']>1e-5 else 'SOLVER_STOP_FAILURE'
                    assert ss['category']==cat and ss['hit_budget']==(ss['scipy_status']==0)
            base=dict(index=i,shard=number,batch=args.batch,unit=rec['unit'],**u['condition'],seed=u['seed'],method=m,accepted=s['accepted'],category=s['category'],usable=s['usable_estimate'],gradient_inf=s['gradient_inf'],cost=s['cost'])
            base['noise_model']=u['condition'].get('noise_model','iid_004')
            if not s['usable_estimate']:
                rows.append(dict(base,data_residual_rms=None,total_residual_rms=None,mse1=None,mse2=None,bias_eligible=False,bias_error=None));continue
            x=np.asarray(s['estimate']);nstate=25 if m=='B2' else 24;assert x.shape==(nstate,)
            r,j=rb.objective(u,m,x);nr=len(data_indices(m));assert j.shape==(nr+24,nstate)
            a=j[:nr+20];l=j[nr+20:];scale=np.r_[np.ones(24),.1] if m=='B2' else np.ones(24)
            errors[i]=(x[:24]-np.array(u['truth']).ravel()).reshape(12,2);rms=np.mean(np.sum(errors[i].reshape(6,2,2)**2,axis=-1),axis=0)
            eligible[i]=m=='B2' and u['condition']['injection'] in ['zero','constant']
            if eligible[i]:
                mask=np.zeros(54);ids=c['links'][u['condition']['candidate']]['indices'];mask[ids]=1;trueb=0. if u['condition']['injection']=='zero' else .3
                assert np.allclose(u['injection'],mask*trueb,atol=0,rtol=0);be[i]=x[-1]-trueb
            base.update(data_residual_rms=float(np.sqrt(np.mean(r[:len(a)]**2))),total_residual_rms=float(np.sqrt(np.mean(r**2))),mse1=float(rms[0]),mse2=float(rms[1]),bias_eligible=bool(eligible[i]),bias_error=float(be[i]) if eligible[i] else None)
            rows.append(base)
            d=information(a,scale,CFG['rank_rtol']);t=information(j,scale,CFG['rank_rtol'])
            for k,(name,inf) in enumerate([('data',d),('total',t)]):
                sv=inf['singular_values'];spectra[i,k,:nstate]=sv
                infos.append(dict(index=i,shard=number,unit=rec['unit'],method=m,matrix=name,rank=inf['rank'],dimension=nstate,reason=inf['reason'],condition=inf['condition'],smax=float(sv[0]),smin=float(sv[-1]),**{'rank_'+str(v):inf['rank_sensitivity'][str(v)] for v in CFG['rank_sensitivity']}))
            cc=t['covariance'];o=omega(m,base['noise_model']);matrices=[None]*3
            if cc is not None:
                gain=cc@a.T;ii=gain@gain.T;tt=gain@o@gain.T;matrices=[cc,(ii+ii.T)/2,(tt+tt.T)/2]
                if base['noise_model']=='iid_004':assert np.allclose(ii,tt,rtol=1e-12,atol=1e-12)
            for v,cm in enumerate(matrices):
                if cm is None:reasons[i,v,:]=1;continue
                for block in range(12):
                    xy=[2*block,2*block+1];b=block_metrics(cm,xy,errors[i,block],CFG['levels'])
                    if b['available']:
                        cc2=b['covariance'];cov[i,v,block]=[cc2[0,0],cc2[0,1],cc2[1,1]];q[i,v,block]=b['q'];reasons[i,v,block]=0
                    else:reasons[i,v,block]=3 if b['reason']=='NONPOSITIVE_MARGINAL' else 2
                if m=='B2':
                    bv[i,v]=cm[-1,-1]
                    if eligible[i] and np.isfinite(bv[i,v]) and bv[i,v]>0:bq[i,v]=be[i]**2/bv[i,v]
            if u['seed']==min(c['seeds']['formal']):
                fun,_,_=adapter.solver_problem(c,obs,m,np.array(u['injection']) if m=='B3_full_oracle' else None);rr,jj=fun(x)
                diff=max(float(np.max(abs(rr-r))),float(np.max(abs(jj-j))));assert diff<1e-10;max_cross=max(max_cross,diff)
                if matrices[0] is not None:
                    direct=np.linalg.solve(jj.T@jj,np.eye(nstate));g=np.linalg.solve(jj.T@jj,jj[:len(a)].T)
                    for calc,reference in zip(matrices,[direct,g@g.T,g@o@g.T]):
                        delta=float(np.linalg.norm(calc-reference)/max(1,np.linalg.norm(reference)));assert delta<1e-8;max_cov=max(max_cov,delta)
                cross_n+=1
        rb.finishchecks(checks,c);checks.update(crosscheck_cases=cross_n,max_objective_crosscheck=max_cross,max_covariance_crosscheck=max_cov,methods=n,eligible_bias=int(eligible.sum()),category_counts=dict(collections.Counter(r['category'] for r in rows)),unavailable_point_blocks=int(np.sum(reasons!=0)),analysis_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip())
        np.savez_compressed(target/'POINTS.npz',covariance=cov,q=q,error=errors,reason=reasons,bias_variance=bv,bias_q=bq,bias_error=be,bias_eligible=eligible)
        np.savez_compressed(target/'SPECTRA.npz',singular_values=spectra)
        csvwrite(target/'RUNS.csv.gz',rows);csvwrite(target/'INFORMATION.csv.gz',infos);write_json(target/'CHECKS.json',checks)
        write_json(done,dict(source=sha(p),code=fingerprint,outputs={p.name:sha(p) for p in target.iterdir() if p.is_file()}));print(args.batch,target.name,n,'done',flush=True)
if __name__=='__main__':main()
