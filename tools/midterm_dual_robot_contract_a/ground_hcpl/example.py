"""Seed 101 causal development example. The filter only accepts observation packets."""
import argparse
import gzip
import json
import subprocess
from pathlib import Path

import numpy as np
from statistics import NormalDist

RUNTIME_SHA = 'd3b39fa9003519f70aef4abfdd050fc969a4a513'
RUNTIME_DIR = 'docs/research/ground_b_round1/runtime'
EVALUATION_SHA = '01e588021e7e3ddd918b1d1fc9561973373758c6'
EVALUATION_DIR = 'docs/research/ground_continuous_b/runs/101_nominal'
CARS = ('car1', 'car2')
TARGET = 10
R = np.eye(9) * .04**2
Q = np.diag([.03**2] * 4 + [.01**2] * 9)
AL = .1
RISK = .01
NS = 10**9


def source_bytes(local_dir, sha, repo_dir, name):
    if local_dir is not None:
        return (Path(local_dir) / name).read_bytes()
    return subprocess.check_output(['git', 'show', f'{sha}:{repo_dir}/{name}'])


def rotation(angle):
    return np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])


def antenna_offset(odom, reference, model):
    """Room-frame antenna displacement relative to the surveyed reference pose."""
    heading = np.deg2rad(model['initial_heading_deg'])
    lever = np.asarray(model['base_to_antenna_body_xy_m'])
    body_displacement = np.asarray(odom[:2]) - reference[:2]
    base_in_room = rotation(heading - reference[2]) @ body_displacement
    lever_in_room = (rotation(heading + (odom[2] - reference[2])) - rotation(heading)) @ lever
    return base_in_room + lever_in_room


def select_packets(events, config, last):
    """Select only equal-header-time frames actually received by each deadline."""
    epoch = config['epoch_ns']
    first = config['prior_state_s']
    if last < first:
        raise ValueError('Target precedes the survey')
    groups = {t: {} for t in range(first, last + 1)}
    previous_receive = None
    for event in events:
        received = event['receive_epoch_ns']
        if previous_receive is not None and received < previous_receive:
            raise ValueError('Input feed must follow receipt order')
        previous_receive = received
        if received > epoch + (last + 1) * NS:
            break
        stamp = event['header_epoch_ns']
        t, frac = divmod(stamp - epoch, NS)
        key = event['vehicle_id'], event['kind']
        if frac or t not in groups or key[0] not in CARS or key[1] not in ('uwb', 'odom'):
            continue
        if received < stamp:
            raise ValueError(f'Receipt precedes acquisition for {key} at {t}')
        if received > stamp + NS:
            continue
        if key in groups[t]:
            raise ValueError(f'Duplicate {key} at {t}')
        groups[t][key] = event

    models = config['models']
    anchors = models['car1']['anchors_xyz_m']
    names = sorted(anchors)
    if models['car2']['anchors_xyz_m'] != anchors:
        raise ValueError('The two vehicles must use the same surveyed anchors')
    packets = []
    for t, group in groups.items():
        if len(group) != 4:
            raise ValueError(f'Incomplete sensor epoch at {t} s')
        uwb = [group[car, 'uwb'] for car in CARS]
        odom = [group[car, 'odom'] for car in CARS]
        ranges = [frame['value'][name] for frame in uwb for name in names]
        ranges.append(uwb[0]['value']['node_0'])
        range_ids = [e['source_observation_id'] for e in uwb]
        range_receipts = [(e['receive_epoch_ns'] - epoch) / NS for e in uwb]
        odom_receipts = [(e['receive_epoch_ns'] - epoch) / NS for e in odom]
        packets.append(dict(t=t, ranges=ranges, heights=[models[c]['antenna_height_m'] for c in CARS],
                            anchors=[anchors[k] for k in names], range_ids=range_ids,
                            peer_id=range_ids[0] + '/node_0', anchor_order=names,
                            odom=[e['value']['pose'] for e in odom],
                            odom_ids=[e['source_observation_id'] for e in odom], cutoff=t + 1.,
                            range_receipts=range_receipts, range_received=max(range_receipts),
                            odom_receipts=odom_receipts, inputs_ready_s=max(range_receipts + odom_receipts)))
    return packets


def runtime_packets(directory=None):
    def raw(name):
        return source_bytes(directory, RUNTIME_SHA, RUNTIME_DIR, name)
    config = json.loads(raw('geometry.json'))
    if config['raw_range_sigma_m'] != .04:
        raise ValueError('Development range sigma differs from the example model')
    lines = gzip.decompress(raw('events.jsonl.gz')).splitlines()
    return config, select_packets(map(json.loads, lines), config, TARGET)


def geometry(x,packet):
    xyz=np.column_stack((x[:4].reshape(2,2),packet['heights']))
    offsets=xyz[:,None,:]-np.array(packet['anchors'])
    ranges=np.linalg.norm(offsets,axis=2)
    peer=xyz[0]-xyz[1]
    d=np.linalg.norm(peer)
    H=np.column_stack((np.zeros((9,4)),np.eye(9)))
    for car in range(2):
        H[4*car:4*car+4,2*car:2*car+2]=offsets[car,:,:2]/ranges[car,:,None]
    H[-1,:4]=np.r_[peer[:2]/d,-peer[:2]/d]
    return np.r_[ranges.ravel(),d]+x[4:],H


def rank_report(H):
    sv=np.linalg.svd(H,compute_uv=False)
    threshold = float(sv[0] * 1e-9) if sv.size else 0.
    return dict(rank=int(np.sum(sv > threshold)), columns=H.shape[1],
                singular_values=sv.tolist(), threshold=threshold)


def ranks(history,links):
    n=len(history)
    dim=4+links
    measurement=np.zeros((9*n,dim*n))
    motion=np.zeros((4*(n-1),dim*n))
    process=np.zeros((links*(n-1),dim*n))
    for i,H in enumerate(history):
        block=np.column_stack((H[:,:4],np.eye(9) if links==9 else H[:,[-1]]))
        measurement[9*i:9*i+9,i*dim:(i+1)*dim]=block/.04
        if i:
            for matrix,offset,size,sd in [(motion,0,4,.03),(process,4,links,.01)]:
                for j,sign in [(i-1,-1),(i,1)]:
                    matrix[(i-1)*size:i*size,j*dim+offset:j*dim+offset+size]=sign*np.eye(size)/sd
    data=np.vstack([measurement,motion])
    smooth=np.vstack([data,process])
    prior=np.zeros((dim,dim*n))
    prior[:,:dim]=np.diag([1/.2]*4+[1/.3]*links)
    return dict(measurement=rank_report(measurement),motion=rank_report(motion),
                data=rank_report(data),with_bias_process=rank_report(smooth),
                with_initial_prior=rank_report(np.vstack([smooth,prior])))


def estimate(packets, models, prior_state_s):
    if not packets or [p['t'] for p in packets] != list(range(prior_state_s, prior_state_s + len(packets))):
        raise ValueError('Expected consecutive one-second packets beginning at the survey')
    survey_xy = np.concatenate([models[c]['start_antenna_xyz_m'][:2] for c in CARS])
    x = np.r_[survey_xy, np.zeros(9)]
    P = np.diag([.2**2] * 4 + [.3**2] * 9)
    reference = packets[0]['odom']
    previous = np.zeros(4)
    transfer = np.zeros((13, 0))
    Hs = []
    history = []
    for i, p in enumerate(packets):
        # The survey and first range packet describe the very same state.
        offset = np.concatenate([antenna_offset(o, r, models[c])
                                 for c, o, r in zip(CARS, p['odom'], reference)])
        u = offset - previous
        previous = offset
        prior = x + np.r_[u, np.zeros(9)]
        prior_cov = P if i == 0 else P + Q
        pred,H=geometry(prior,p)
        Hs.append(H)
        innovation=p['ranges']-pred
        S=H@prior_cov@H.T+R
        K=np.linalg.solve(S,H@prior_cov).T
        A=np.eye(13)-K@H
        x=prior+K@innovation
        P=A@prior_cov@A.T+K@R@K.T
        transfer=np.column_stack((A@transfer,K))
        history.append(dict(t=p['t'],inputs_ready_s=p['inputs_ready_s'],u=u.tolist(),prior=prior.tolist(),prior_cov=prior_cov.tolist(),
            predicted=pred.tolist(),innovation=innovation.tolist(),H=H.tolist(),S=S.tolist(),
            gain=K.tolist(),posterior=x.tolist(),posterior_cov=P.tolist()))
    stat=float(innovation@np.linalg.solve(S,innovation))
    threshold=21.665994333461924
    cars=[]
    for i in range(2):
        axes=slice(2*i,2*i+2)
        sigma=np.sqrt(np.diag(P)[axes])
        bias=.02*np.abs(transfer[axes]).sum(axis=1)
        variants={}
        current=.02*np.abs(K[axes]).sum(axis=1)
        for label,alpha,bound in [('eq13_to_16',RISK,current),('axis_preallocated',RISK/2,current),
                                  ('history_preallocated',RISK/2,bias)]:
            k=NormalDist().inv_cdf(1-alpha/2)
            cpl=bound+k*sigma
            hcpl=float(np.linalg.norm(cpl))
            variants[label]=dict(axis_alpha=alpha,k=k,CPL=cpl.tolist(),HCPL=hcpl,
                alarm=bool(stat>threshold or hcpl>AL),available=bool(stat<=threshold and hcpl<=AL))
        cars.append(dict(car=i+1,state_time=packets[-1]['t'],published_antenna_xy=x[axes].tolist(),
            inputs_ready_s=packets[-1]['inputs_ready_s'],decision_ready_time=None,AL=AL,sigma=sigma.tolist(),history_bias_bound=bias.tolist(),current_bias_bound=current.tolist(),variants=variants))
    # Single-epoch witness: horizontal error is canceled by link biases.
    direction=np.r_[1.,0.,0.,0.]
    null=np.r_[direction,-Hs[0][:,:4]@direction]
    return dict(prior_state_s=prior_state_s,first_epoch_failure=dict(H=Hs[0].tolist(),null_vector=null.tolist(),
                residual_norm=float(np.linalg.norm(Hs[0]@null))),packets=packets,history=history,R=R.tolist(),Q=Q.tolist(),transfer=transfer.tolist(),
        remaining_range_bias_bound=.02,axis_nominal_alpha=RISK,innovation_test=dict(statistic=stat,
        rank=int(np.linalg.matrix_rank(S)),threshold=threshold,alarm=bool(stat>threshold)),cars=cars,
        ranks={str(n):ranks(Hs,n) for n in (1,9)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, help='local copy of the two #145 runtime files')
    parser.add_argument('--evaluation-dir', type=Path, help='local copy of the #143 seed-101 evaluation files')
    parser.add_argument('--runtime-only', action='store_true', help='emit the full runtime result before offline scoring')
    args = parser.parse_args()
    config, packets = runtime_packets(args.runtime_dir)
    models = config['models']
    output = estimate(packets, models, config['prior_state_s'])
    output['survey_init'] = {c: {k: models[c][k] for k in
                                 ('initial_heading_deg', 'start_antenna_xyz_m', 'base_to_antenna_body_xy_m')}
                             for c in CARS}
    output['source_sha'] = RUNTIME_SHA
    if not args.runtime_only:
        def evaluation(name):
            return json.loads(gzip.decompress(source_bytes(args.evaluation_dir, EVALUATION_SHA, EVALUATION_DIR, name)))
        truth = evaluation('truth.json.gz')[20 * TARGET]
        output['evaluation_source_sha'] = EVALUATION_SHA
        output['evaluation_only'] = [
            dict(truth_xy=v, error_m=float(np.linalg.norm(np.asarray(v) - car['published_antenna_xy'])))
            for v, car in zip(truth, output['cars'])]
        records = evaluation('records.json.gz')
        output['independent_epoch_baseline'] = next(r['aug'] for r in records if r['t'] == TARGET)
    print(json.dumps(output, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
