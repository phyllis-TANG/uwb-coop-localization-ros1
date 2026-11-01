"""Independent scalar/finite-difference reader; no solver or adapter imports."""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np
from common import CARS, ROOT, dump, lines, sha

spec = importlib.util.spec_from_file_location('_sim_dev_scalar', ROOT/'tools/two_car_imu_fgo/independent.py')
ind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ind)


def residual(snapshot, states, config, weight):
    # The original independent scalar equations may use a different row order.
    local = dict(snapshot, peer_enabled=False)
    result = list(ind.residual(local, states, config, 8))
    x = np.asarray(states).reshape(-1, 8)
    if snapshot['peer_enabled']:
        for k, measured in enumerate(snapshot['peers_m']):
            if measured is not None:
                distance = np.linalg.norm(ind.ant(x[k, :4], config['models']['car1'])-ind.ant(x[k, 4:], config['models']['car2']))
                result.append(np.sqrt(weight)*ind.robust(distance, measured, config['peer']['sigma_m']))
    return np.array(result)


def marginal(detail, config, weight, enabled):
    snapshot = ind.incident(detail, enabled)
    x = np.asarray(detail['states']).ravel()
    fun = lambda v:residual(snapshot, v, config, weight)
    r = fun(x)
    eye = np.eye(len(x))*1e-6
    jac = np.column_stack([(fun(x+d)-fun(x-d))/2e-6 for d in eye])
    a, b = jac[:, :8], jac[:, 8:]
    jp = b-a@np.linalg.lstsq(a, b, rcond=None)[0]
    rp = r-a@np.linalg.lstsq(a, r, rcond=None)[0]
    matrix, offset = np.array(detail['after']['matrix']), np.array(detail['after']['offset'])
    ind.require(np.allclose(matrix.T@matrix, jp.T@jp, atol=1e-5, rtol=1e-8), '8D weighted Schur H/cross')
    ind.require(np.allclose(matrix.T@offset, jp.T@rp, atol=1e-6, rtol=1e-8), '8D weighted Schur affine')
    ind.require(abs(offset@offset+detail['constant']-rp@rp) < 1e-6, '8D weighted Schur constant')


def audit(run, events_path):
    run = Path(run)
    meta, cfg = (json.loads((run/name).read_text()) for name in ('run.json', 'config.json'))
    ind.require(meta['status'] == 'DONE', 'Run incomplete')
    ind.require(meta['input_sha256'] == sha(events_path), 'Input SHA')
    for name, digest in meta['outputs'].items():
        ind.require(sha(run/name) == digest, 'Output SHA '+name)
    weight = {'M2':0., 'M3':1., 'M3W025':.25}[meta['method_id']]
    events, rows = list(lines(events_path)), list(lines(run/'updates.jsonl.gz'))
    ind.require(bool(events) and bool(rows), 'Empty evidence')
    controls = ind.controls(events, cfg)
    counts = dict(publications=0, objectives=0, angular_intervals=0, gyro_segments=0, marginals_fd=0, bins=0)
    history, consumed = {}, set()
    previous = prior = None
    previous_epoch = None
    for row in rows:
        state, cutoff = row['state_epoch_ns'], row['availability_cutoff_epoch_ns']
        if previous_epoch is not None:
            ind.require(state-previous_epoch == 10**9, 'Missing/repeated publication epoch')
        previous_epoch = state
        ind.require(cutoff-state == 10**9 and cutoff <= events[-1]['receive_epoch_ns'], 'Publication/EOF causality')
        ind.require(row['peer_cost_weight'] == weight and row['odom_yaw_fallback'] is False, 'Weight/gyro semantics')
        ind.bins_check(row, events, cfg, meta['epoch_origin_ns'])
        counts['bins'] += 1
        snap = row['snapshot']
        ind.require(len(snap['times_s']) <= 21 and row['scalar_variables'] == 8*len(snap['times_s']), 'Window bound')
        if row['angular_intervals']:
            for ci, car in enumerate(CARS):
                edge = row['angular_intervals'][car]
                counts['angular_intervals'] += 1
                counts['gyro_segments'] += ind.edge_check(edge, [e for e in controls[car] if e['record_index'] <= row['availability_prefix_max_record_index']], cutoff, cfg['angular'][car]['max_hold_ns']['value'])
                if previous is not None:
                    angle = edge['raw_angle_rad']-previous[4*ci+3]*edge['dt_ns']/1e9 if edge['valid'] else 0.
                    ind.require(abs(ind.wrap(row['prediction_pose'][4*ci+2]-previous[4*ci+2]-angle)) < 1e-10, 'Hidden odom angular fallback')
        previous = row['pose']
        history[row['state_time_s']] = row
        for t, obs, local, peer in zip(snap['times_s'], snap['observations'], snap['local'], snap['peers_m']):
            ind.require(obs == {c:history[t]['bins'][c]['observations'] for c in CARS}, 'Retained walls')
            ind.require(local == [history[t]['bins'][c]['local_odom'] for c in CARS], 'Retained odom')
            ind.require(peer == (history[t]['peer_median_m'] if snap['peer_enabled'] else None), 'Retained peer')
        for detail in row['marginalization_details']:
            t0, t1 = detail['times_s']
            ind.require(t0 not in consumed, 'Repeated factor consumption')
            consumed.add(t0)
            ind.require(detail['old_observations'] == {c:history[t0]['bins'][c]['observations'] for c in CARS}, 'Old wall source')
            ind.require(detail['intervals'] == [history[t1]['angular_intervals']], 'Old gyro source')
            if prior is not None:
                ind.require(detail['before'] == prior, 'Prior lineage')
            prior = detail['after']
            marginal(detail, cfg, weight, snap['peer_enabled'])
            counts['marginals_fd'] += 1
        if prior is not None:
            ind.require(snap['prior'] == prior, 'Current prior lineage')
        ind.require(row['marginalizations'] == len(consumed), 'Marginal count')
        if row['accepted_graph']:
            r = residual(snap, snap['states'], cfg, weight)
            ind.require(abs(r@r/2-row['optimizer']['cost']) < 1e-7, 'Weighted full objective cost')
            counts['objectives'] += 1
        if weight == 0:
            matrix = np.array(snap['prior']['matrix'])
            ind.require(np.linalg.norm((matrix.T@matrix)[:4, 4:]) < 1e-9, 'M2 cross-car prior')
        counts['publications'] += 1
    return dict(status='PASS', counts=counts, online_solver_or_analytic_jacobian_imported=False,
        scope='Saved 8D objectives, all saved QR priors, receipt bins and gyro support; no B2 monitor validation')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', required=True, type=Path)
    p.add_argument('--events', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Refuse overwrite')
    result = audit(a.run, a.events)
    dump(a.output, result)
    print(json.dumps(result))
