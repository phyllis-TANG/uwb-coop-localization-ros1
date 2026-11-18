import argparse,csv,gzip,json,sys,time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import chi2
from region import solve
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DOC=ROOT/'docs/research/ground_continuous_b'
sys.path.insert(0,str(ROOT/'tools/cooperative_integrity_baselines_20261029'))
from binding import simulate
from engine import run
from monitors import antenna
CFG=json.loads((DOC/'config.json').read_text())
CARS=('car1','car2')
def dump(path,x):
    with gzip.open(path,'wt') as f:json.dump(x,f,separators=(',',':'),allow_nan=False)
def augmented(obs):
    anchors=np.asarray(obs['anchors']);h=np.asarray(obs['heights']);y=np.asarray(obs['ranges'])
    initial=[]
    for i in range(2):
        z=y[4*i:4*i+4]
        d=np.sum(anchors[:,:2]**2,axis=1)+(h[i]-anchors[:,2])**2
        initial.extend(np.linalg.lstsq(2*(anchors[1:,:2]-anchors[0,:2]),z[0]**2-z[1:]**2+d[1:]-d[0],rcond=None)[0])
    def residual(x):
        xyz=np.column_stack((x[:4].reshape(2,2),h))
        return (np.r_[np.linalg.norm(xyz[:,None]-anchors,axis=2).ravel(),np.linalg.norm(xyz[1]-xyz[0])+x[4]]-y)/.04
    fit=least_squares(residual,[*initial,0],max_nfev=50)
    stat=float(fit.fun@fit.fun)
    return dict(xy=fit.x[:4].reshape(2,2).tolist(),bias=float(fit.x[4]),stat=stat,ready=bool(fit.success and np.linalg.matrix_rank(fit.jac)==5),alarm=bool(stat>chi2.ppf(.99,4)))
def generate(seed,scene):
    cfg,events,truth,_=simulate.make_case(seed,'nominal')
    for e in events:
        t=(e['header_epoch_ns']-simulate.EPOCH_NS)/1e9
        if e['kind']=='uwb' and e['vehicle_id']=='car1' and 24<=t<38:
            if scene=='wall':
                for k in cfg['models']['car1']['anchors_xyz_m']:e['value'][k]+=.3
            if scene in ('peer_ramp','peer_step'):
                e['value']['node_0']+=.6*((t-24)/13.95 if scene=='peer_ramp' else 1)
    return cfg,events,truth

def trial(seed,scene):
    path=DOC/'runs'/f'{seed}_{scene}';path.mkdir(parents=True,exist_ok=False)
    cfg,events,truth=generate(seed,scene)
    raw={}
    for e in events:
        dt=e['header_epoch_ns']-simulate.EPOCH_NS
        if e['kind']=='uwb' and dt%10**9==0:raw.setdefault(dt//10**9,{})[e['vehicle_id']]=e
    outputs=[]
    def publish(r):
        m=r['monitor'];models=[cfg['models'][c] for c in CARS]
        xy=[antenna(r['pose'][3*i:3*i+3],model)[:2].tolist() for i,model in enumerate(models)]
        t=int(r['state_time_s']);frames=[raw[t][c] for c in CARS];keys=sorted(models[0]['anchors_xyz_m'])
        assert models[0]['anchors_xyz_m']==models[1]['anchors_xyz_m']
        obs=dict(anchors=[models[0]['anchors_xyz_m'][k] for k in keys],heights=[v['antenna_height_m'] for v in models],ranges=[e['value'][k] for e in frames for k in keys]+[frames[0]['value']['node_0']],ids=[e['source_observation_id'] for e in frames],anchor_order=keys,peer_id=frames[0]['source_observation_id']+'/node_0',received=max(e['receive_epoch_ns']-simulate.EPOCH_NS for e in frames)/1e9)
        start=time.perf_counter();aug=augmented(obs);augtime=time.perf_counter()-start
        start=time.perf_counter();reg=solve(obs,xy);regtime=time.perf_counter()-start
        outputs.append(dict(t=t,xy=xy,pub_ready=r['accepted_graph'],cutoff=r['availability_cutoff_s'],graph_cost=r['update_wall_s'],b2_cost=r['total_monitored_emit_wall_s'],b2=m['declarations']['B2_local|scale=1.0|a=0.01'],ss=m['ss'],bins=r['bins'],peer_median=r['peer_median_m'],peer_count=r['peer_sample_count'],obs=obs,region=reg,region_cost=regtime,aug=aug,aug_cost=augtime))
    run(events,cfg,publish)
    dump(path/'records.json.gz',outputs)
    # Evaluation-only 20 Hz antenna trajectories, using the original generator template.
    template=json.loads(simulate.CONFIG.read_text())
    dense=[[simulate.antenna_xyz(simulate.true_pose(i/20,c,template['models'][c]),template['models'][c])[:2].tolist() for c in CARS] for i in range(1280)]
    dump(path/'truth.json.gz',dense)
    assert len(outputs)==63
    if seed==101 and scene in ('nominal','wall'):
        old=list(csv.DictReader((ROOT/'docs/research/cooperative_integrity_baselines_20261029/results/trajectory.csv').open()))
        old=[r for r in old if r['scenario']==('nominal' if scene=='nominal' else 'car1_common_wall_bias')]
        for r in old:
            got=outputs[int(float(r['t_s']))-1]['xy'][CARS.index(r['car'])]
            np.testing.assert_allclose(got,[float(r['antenna_x_m']),float(r['antenna_y_m'])],rtol=0,atol=1e-7)
    print(seed,scene,len(outputs),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('seed',type=int);p.add_argument('scene',choices=CFG['scenarios']);a=p.parse_args();trial(a.seed,a.scene)
