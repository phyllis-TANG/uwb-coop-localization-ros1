"""Independent full-rank certificate from prior plus motion chain, no A J.

For a full-rank d-column boundary prior, each F0 motion edge has an invertible
right-state block (2D rotation + yaw); each covered F3 edge has invertible right
block (2D rotation + gyro/bias Cholesky). Their block-triangular stack already
has full column rank. Adding nonnegative UWB information cannot reduce rank.
This certificate does not certify observability against real sensor errors.
"""
import argparse
import json
import math
from pathlib import Path
import numpy as np
from .common import begin,finish,lines,require,write


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--performance',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_independent_structural_numeric_rank_gate_certificate')
    try:
        checks=[]
        for case in ('004023','005135'):
            for group in ('Q0','Q1','Q2','Q3'):
                folder=a.performance/(case+'_'+group);config=json.loads((folder/'config.json').read_text())['base'];rows=lines(folder/'graphs.jsonl.gz');dimension=4 if config['arm']=='F3' else 3;edges={};count=flag_checks=0
                for g in rows:
                    r=g['row'];s=r['objective_snapshot'];M=np.asarray(s['prior']['matrix']);require(M.shape[1]==dimension and np.linalg.matrix_rank(M)==dimension,'rank certificate needs full-column-rank carried prior')
                    require(config['model']['graph_parameters']['odom_translation_sigma_m']>0,'positive translation whitening')
                    if config['arm']=='F3':
                        require(config['angular']['angle_noise_density_rad_sqrt_s']['value']>0 and config['angular']['bias_random_walk_rad_s_sqrt_s']['value']>0,'positive gyro/bias covariance')
                        if r.get('angular_interval') is not None:edges[g['role'],g['state_epoch_ns']]=r['angular_interval']
                        for e in s.get('interval_end_epochs_ns',[]):require(edges[g['role'],e]['valid'],'uncovered gyro edge: this simple full-rank certificate is insufficient; requires numeric fallback')
                    else:require(config['model']['graph_parameters']['odom_yaw_sigma_deg']>0,'positive yaw whitening')
                    require(all(t2>t1 for t1,t2 in zip(s['times_s'],s['times_s'][1:])),'positive transition time')
                    for state in s['states']:require(abs(math.atan2(math.sin(state[2]-s['prior']['point'][2]),math.cos(state[2]-s['prior']['point'][2])))<math.pi-1e-6,'prior angle branch boundary')
                    if r['accepted_graph'] and 'numerical_full_rank' in r:require(r['numerical_full_rank'] is True and r['numerical_rank']==dimension*r['graph_states'],'reported rank conflicts with independent motion/prior full-rank certificate');flag_checks+=1
                    count+=1
                checks.append(dict(case_id=case,group=group,graph_records_certified=count,declared_full_rank_flags_checked=flag_checks))
        write(a.output/'verification.json',dict(status='PASS',checks=checks,online_Jacobian_imported=False,certificate='full-column-rank prior + positive whitened invertible right-state transition blocks; checked coverage and positive dt. Adding nonnegative ranges cannot decrease rank.',limitation='Numerical full rank is not statistical independence, physical calibration or guaranteed estimation accuracy. Certificate is intentionally rejected on uncovered F3 edges.'));finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
