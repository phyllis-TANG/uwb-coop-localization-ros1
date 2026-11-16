"""Post-fit identity, not a new experiment: bias error = noise - geometry + residual."""
import argparse,csv,json
from pathlib import Path
import numpy as np
from analyze import write_csv


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    raw=[json.loads(s) for s in (args.run/'RAW.jsonl').read_text().splitlines()]
    obs={(r['scene'],r['seed']):r for r in raw if 'range_observed' in r}
    fits={(r['scene'],r['seed'],r['variant']):r for r in raw if 'estimate' in r}
    rows=[]
    for r in csv.DictReader((args.run/'PER_RUN.csv').open()):
        key=(r['scene'],int(r['seed']));o=obs[key];f=fits[(*key,r['variant'])]
        x=np.array(f['estimate'][:24]).reshape(6,2,2);truth=np.array(o['truth'][:24]).reshape(6,2,2)
        if r['kind']=='peer':
            dr=np.linalg.norm(x[:,1]-x[:,0],axis=1)-np.linalg.norm(truth[:,1]-truth[:,0],axis=1)
            indices=np.arange(6) if r['peer_only']=='True' else np.arange(8,54,9)
        else:
            a=np.array(o['anchors'][0]);dr=np.linalg.norm(x[:,0]-a,axis=1)-np.linalg.norm(truth[:,0]-a,axis=1);indices=np.arange(0,54,9)
        noise=float(np.mean(np.array(o['range_noise'])[indices]));geom=float(np.mean(dr));error=float(r['bias_error_m'])
        rows.append(dict(scene=key[0],seed=key[1],variant=r['variant'],noise=r['noise'],bias_error_m=error,active_range_noise_mean_m=noise,active_geometric_distance_error_mean_m=geom,active_residual_mean_m=error-noise+geom,solver_failed=r['solver_failed'],bias_failed=r['bias_failed']))
    write_csv(args.out/'BIAS_DECOMPOSITION.csv',rows)
    selected=[r for r in rows if r['scene']=='weak/static/peer' and r['variant']=='no_prior_base' and r['noise']=='gaussian']
    print(json.dumps(dict(weak_static_peer_no_prior=dict(mean_noise_m=float(np.mean([r['active_range_noise_mean_m'] for r in selected])),mean_geometric_distance_error_m=float(np.mean([r['active_geometric_distance_error_mean_m'] for r in selected])),mean_bias_error_m=float(np.mean([r['bias_error_m'] for r in selected])),max_stationarity_residual_m=max(abs(r['active_residual_mean_m']) for r in selected))),indent=2))

if __name__=='__main__':main()
