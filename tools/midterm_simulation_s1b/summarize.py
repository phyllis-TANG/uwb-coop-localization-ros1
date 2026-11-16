"""Read saved states/observations independently; publish compact evidence, no refits."""
import argparse,collections,csv,gzip,hashlib,json,shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analyze import C, DOC, write_csv


def mean(v): return float(np.mean(v))
def rms(v): return float(np.sqrt(np.mean(np.square(v))))

def direct_measurements(z,a,kind,peer_only):
    x=np.array(z[:24]).reshape(6,2,2);vals=[]
    for t in range(6):
        if not peer_only:
            for car in range(2):
                for k,anchor in enumerate(a):
                    vals.append(float(np.linalg.norm(x[t,car]-anchor))+(z[-1] if car==0 and k==0 and kind=='wall' else 0))
        vals.append(float(np.linalg.norm(x[t,1]-x[t,0]))+(z[-1] if kind=='peer' else 0))
    return np.array(vals)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);out=args.out
    rows=list(csv.DictReader((args.run/'PER_RUN.csv').open()))
    infos=json.loads((args.run/'INFORMATION.json').read_text())
    raw=[json.loads(s) for s in (args.run/'RAW.jsonl').read_text().splitlines()]
    obs={(r['scene'],r['seed']):r for r in raw if 'range_observed' in r}
    fits={(r['scene'],r['seed'],r['variant']):r for r in raw if 'estimate' in r}
    assert len(rows)==2717 and len(fits)==len(rows) and len(obs)==247
    max_errors=collections.defaultdict(float);noise_r=[];noise_m=[]
    for key,o in obs.items():
        geom,motion,kind,*extra=key[0].split('/')
        noise_r.extend(o['range_noise'] if key[1] else []);noise_m.extend(o['motion_noise'] if key[1] else [])
        if key[1]:
            rng=np.random.default_rng(np.random.SeedSequence([key[1],C['geometries'].index(geom),C['motions'].index(motion),C['kinds'].index(kind)]))
            assert np.array_equal(rng.normal(0,.04,len(o['range_noise'])),o['range_noise'])
            assert np.array_equal(rng.normal(0,.02,20),o['motion_noise'])
            assert np.any(np.array(o['range_noise'])!=0) and np.any(np.array(o['motion_noise'])!=0)
        assert np.max(abs(np.array(o['range_observed'])-direct_measurements(o['truth'],o['anchors'],kind,bool(extra))-o['range_noise']))<2e-15
    for r in rows:
        key=(r['scene'],int(r['seed']));f=fits[(*key,r['variant'])];o=obs[key]
        z=np.array(f['estimate']);truth=np.array(o['truth']);e=(z[:24]-truth[:24]).reshape(6,2,2)
        b=z[-1]-truth[-1];pos=np.sqrt(np.mean(np.sum(e**2,axis=-1)))
        expected=dict(position_rmse_2d_m=pos,position_rmse_coordinate_m=np.sqrt(np.mean(e**2)),car1_rmse_2d_m=np.sqrt(np.mean(np.sum(e[:,0]**2,axis=-1))),car2_rmse_2d_m=np.sqrt(np.mean(np.sum(e[:,1]**2,axis=-1))),bias_error_m=b,bias_estimate_m=z[-1])
        residual=np.r_[(direct_measurements(z,o['anchors'],r['kind'],r['peer_only']=='True')-o['range_observed'])/.04,(np.diff(z[:24].reshape(6,4),axis=0).ravel()-o['motion_observed'])/.02]
        if r['prior_sigma_m']: residual=np.r_[residual,(z[:4]-f['prior_center'])/float(r['prior_sigma_m'])]
        expected['cost']=float(residual@residual/2)
        for k,v in expected.items():
            err=abs(v-float(r[k]));max_errors[k]=max(max_errors[k],err)
            assert err<1e-7*max(1,abs(v)),(key,k,err)
        sf=int(r['status'])<=0 or not np.isfinite(z).all()
        pf=pos>.5;bf=abs(b)>.1
        for k,v in [('solver_failed',sf),('position_failed',pf),('bias_failed',bf),('any_failed',sf or pf or bf)]: assert (r[k]=='True')==v
        if r['variant'] in ['center_plus','center_minus','strong','weak_prior','ideal_truth_center']:
            assert f['initial_state']==fits[(*key,'nominal_base')]['initial_state']
    groups=collections.defaultdict(list)
    for r in rows: groups[(r['scene'],r['noise'],r['variant'])].append(r)
    summaries=[]
    for (scene,noise,variant),rr in groups.items():
        be=[float(r['bias_error_m']) for r in rr]
        summaries.append(dict(scene=scene,noise=noise,variant=variant,n=len(rr),bias_error_mean_m=mean(be),bias_mae_m=mean(np.abs(be)),bias_rmse_m=rms(be),position_rmse_2d_mean_m=mean([float(r['position_rmse_2d_m']) for r in rr]),car1_rmse_2d_mean_m=mean([float(r['car1_rmse_2d_m']) for r in rr]),car2_rmse_2d_mean_m=mean([float(r['car2_rmse_2d_m']) for r in rr]),**{k+'_count':sum(r[k]=='True' for r in rr) for k in ['solver_failed','position_failed','bias_failed','any_failed']},**{k+'_rate':mean([r[k]=='True' for r in rr]) for k in ['solver_failed','position_failed','bias_failed','any_failed']}))
    write_csv(out/'SUMMARY.csv',summaries)
    paired=[]
    for key in obs:
        for factor,v1,v2 in [('center','center_plus','center_minus'),('strength','strong','weak_prior'),('add_nominal_prior','nominal_base','no_prior_base'),('init_no_prior','no_prior_plus','no_prior_minus'),('init_with_prior','nominal_plus','nominal_minus')]:
            a=np.array(fits[(*key,v1)]['estimate']);b=np.array(fits[(*key,v2)]['estimate'])
            paired.append(dict(scene=key[0],seed=key[1],noise='zero' if key[1]==0 else 'gaussian',factor=factor,first=v1,second=v2,bias_delta_m=float(a[-1]-b[-1]),absolute_bias_delta_m=float(abs(a[-1]-b[-1])),position_estimate_shift_2d_m=float(np.sqrt(np.mean(np.sum((a[:24]-b[:24]).reshape(6,2,2)**2,axis=-1))))))
    write_csv(out/'PAIRED.csv',paired)
    pg=collections.defaultdict(list)
    for r in paired: pg[(r['scene'],r['noise'],r['factor'])].append(r)
    ps=[dict(scene=k[0],noise=k[1],factor=k[2],n=len(v),mean_absolute_bias_delta_m=mean([r['absolute_bias_delta_m'] for r in v]),max_absolute_bias_delta_m=max(r['absolute_bias_delta_m'] for r in v),mean_position_estimate_shift_2d_m=mean([r['position_estimate_shift_2d_m'] for r in v])) for k,v in pg.items()]
    write_csv(out/'PAIRED_SUMMARY.csv',ps)
    fields=['scene','information','rank','nullity','rank_absolute_threshold','bias_null_norm_scaled','position_rank','bias_information_m_minus2','bias_local_sigma_m']
    write_csv(out/'INFORMATION_SUMMARY.csv',[{k:r[k] for k in fields} for r in infos])
    for name in ['PER_RUN.csv','INFORMATION.json','CHECKS.json','RUN.json']:shutil.copyfile(args.run/name,out/name)
    # Small exact observation record: estimates remain in external RAW, reproducible by analyze.
    with gzip.GzipFile(filename=str(out/'OBSERVATIONS.jsonl.gz'),mode='wb',mtime=0) as f:
        for r in obs.values():f.write((json.dumps(r)+'\n').encode())
    report=dict(status='PASS',rows_readback=len(rows),observations=len(obs),paired_rows=len(paired),maximum_absolute_readback_errors=dict(max_errors),range_noise_empirical_std_m=float(np.std(noise_r)),motion_noise_empirical_std_m=float(np.std(noise_m)),noise_seed_reproduction='exact',factor_separation='same start verified for center/strength/ideal contrasts',scope='Independent loop range/cost and saved-state error recomputation; no extra refits; 12 seed identities are paired across scenes, not independent scene replicates')
    (out/'READBACK.json').write_text(json.dumps(report,indent=2))
    main=[r for r in infos if not r['peer_only'] and r['information']=='data_motion']
    fig,axs=plt.subplots(2,1,figsize=(12,7),constrained_layout=True)
    labels=[r['scene'] for r in main];xx=np.arange(len(labels))
    axs[0].bar(xx,[r['rank'] for r in main]);axs[0].set_ylim(20,26);axs[0].set_ylabel('Full state rank / 25');axs[0].set_xticks(xx,labels,rotation=65,ha='right',fontsize=8)
    axs[1].bar(xx,[r['bias_information_m_minus2'] for r in main]);axs[1].set_ylabel('Projected bias information (1/m²)');axs[1].set_xticks(xx,labels,rotation=65,ha='right',fontsize=8)
    fig.savefig(out/'rank_and_bias_information.png',dpi=160);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(13,5),constrained_layout=True)
    chosen=['good/static/peer','weak/static/peer','near/static/peer','weak/turn/peer','near/turn/peer']
    for i,scene in enumerate(chosen):
        for ax,key in zip(axs,['bias_mae_m','position_rmse_2d_mean_m']):
            vals=[next(r[key] for r in summaries if r['scene']==scene and r['noise']=='gaussian' and r['variant']==v) for v in ['no_prior_base','nominal_base','center_plus','center_minus','strong','weak_prior','ideal_truth_center']]
            ax.plot(np.arange(7),vals,'o-',label=scene)
    for ax in axs:ax.set_xticks(range(7),['No prior','Survey .5','Center +','Center -','Survey .05','Survey 5','Ideal .5'],rotation=40,ha='right');ax.grid(alpha=.25)
    axs[0].set_ylabel('Bias MAE (m), 12 seeds');axs[1].set_ylabel('Mean position 2D RMSE (m)');axs[1].legend(fontsize=8)
    fig.savefig(out/'prior_sensitivity.png',dpi=160);plt.close(fig)
    ext={p.name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in args.run.iterdir() if p.is_file()}
    (out/'EXTERNAL_INDEX.json').write_text(json.dumps(dict(directory=str(args.run),files=ext,note='RAW.jsonl contains all observations, estimates, starts, prior centers and solver messages; regenerate using frozen CONFIG and analyze.py. External files are not required to inspect committed summary/full spectrum/observations.'),indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
