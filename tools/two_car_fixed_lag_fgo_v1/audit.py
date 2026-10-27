#!/usr/bin/env python3
"""Independent artifact readback: no optimizer, graph, frontend or legacy imports."""
import argparse
import bisect
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np

CARS = ('car1', 'car2')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def read_jsonl(path):
    with (gzip.open(path, 'rt') if str(path).endswith('.gz') else open(path)) as f:
        return [json.loads(line) for line in f if line.strip()]


def wrap(value):
    return math.atan2(math.sin(value), math.cos(value))


def ant(p, model):
    lx, ly = model['base_to_antenna_body_xy_m']; c, s = math.cos(p[2]), math.sin(p[2])
    return np.array([p[0]+c*lx-s*ly, p[1]+s*lx+c*ly, model['antenna_height_m']])


def body_delta(left, right):
    dx, dy = right[0]-left[0], right[1]-left[1]
    co, si = math.cos(left[2]), math.sin(left[2])
    return np.array([co*dx+si*dy, -si*dx+co*dy])


def range_residual(predicted, measured, scale):
    e = (predicted-measured)/scale
    return e*math.sqrt(2/(math.hypot(1, e)+1))


def residuals(flat, times, local, observations, peers, models, prior, peer_enabled):
    """Direct model equations, independent of implementation row order/derivatives."""
    x = np.asarray(flat).reshape(-1, 6); local = np.asarray(local)
    delta = x[0]-np.asarray(prior['point'])
    delta[2], delta[5] = wrap(delta[2]), wrap(delta[5])
    residual = list(np.asarray(prior['matrix'])@delta+np.asarray(prior['offset']))
    for k, stamp in enumerate(times):
        for i, car in enumerate(CARS):
            model = models[car]; p = model['graph_parameters']; state = x[k, 3*i:3*i+3]
            if k:
                previous = x[k-1, 3*i:3*i+3]; scale = math.sqrt(stamp-times[k-1])
                difference = body_delta(previous, state)-body_delta(local[k-1, i], local[k, i])
                residual.extend(difference/(p['odom_translation_sigma_m']*scale))
                residual.append(wrap(state[2]-previous[2]-wrap(local[k, i, 2]-local[k-1, i, 2]))/
                                (math.radians(p['odom_yaw_sigma_deg'])*scale))
            antenna = ant(state, model)
            for name, raw in sorted(observations[k][car].items()):
                measured = raw-model['range_bias_m'][name]
                if measured <= 0: raise AssertionError('Nonpositive corrected range')
                residual.append(range_residual(np.linalg.norm(antenna-np.asarray(model['anchors_xyz_m'][name])),
                                               measured, p['range_sigma_m']))
        if peer_enabled and peers[k] is not None:
            prediction = np.linalg.norm(ant(x[k, :3], models['car1'])-ant(x[k, 3:], models['car2']))
            residual.append(range_residual(prediction, peers[k], residuals.peer_sigma))
    return np.asarray(residual)


def finite_jac(fun, x, eps=1e-6):
    x = np.asarray(x).ravel(); out = []
    for j in range(len(x)):
        d = np.zeros_like(x); d[j] = eps
        out.append((fun(x+d)-fun(x-d))/(2*eps))
    return np.asarray(out).T


def marginal_check(detail, config, enabled):
    obs = [detail['old_observations'], {c: {} for c in CARS}]
    peers = [detail['old_peer_m'], None]; x = np.asarray(detail['states']).ravel()
    def fun(flat):
        return residuals(flat, detail['times_s'], detail['local'], obs, peers,
                         config['models'], detail['before'], enabled)
    r, j = fun(x), finite_jac(fun, x)
    h, g = j.T@j, j.T@r
    hs = h[6:, 6:]-h[6:, :6]@np.linalg.solve(h[:6, :6], h[:6, 6:])
    gs = g[6:]-h[6:, :6]@np.linalg.solve(h[:6, :6], g[:6])
    cs = r@r-g[:6]@np.linalg.solve(h[:6, :6], g[:6])
    a, o = np.asarray(detail['after']['matrix']), np.asarray(detail['after']['offset'])
    np.testing.assert_allclose(a.T@a, hs, atol=3e-6, rtol=2e-6)
    np.testing.assert_allclose(a.T@o, gs, atol=2e-6, rtol=2e-6)
    np.testing.assert_allclose(o@o+detail['constant'], cs, atol=2e-6, rtol=2e-6)
    np.testing.assert_allclose(detail['after']['point'], detail['states'][1], atol=0, rtol=0)
    cross = float(np.linalg.norm((a.T@a)[:3, 3:]))
    if not enabled: np.testing.assert_allclose(cross, 0, atol=1e-8)
    return dict(times_s=detail['times_s'], hessian_max_abs=float(np.max(np.abs(a.T@a-hs))),
                gradient_max_abs=float(np.max(np.abs(a.T@o-gs))), constant_abs=float(abs(o@o+detail['constant']-cs)),
                cross_information_norm=cross)


def input_streams(events):
    streams = {c: {'odom': [], 'uwb': []} for c in CARS}; seen = set(); previous = None
    for e in events:
        ns, index = e['receive_epoch_ns'], e['record_index']
        if type(ns) is not int or type(index) is not int: raise AssertionError('Noninteger identity')
        if previous and (ns < previous[0] or index <= previous[1]): raise AssertionError('Receive order')
        previous = ns, index; car, kind = e.get('vehicle_id'), e['kind']
        if car not in CARS or kind not in ('odom', 'uwb'): continue
        if kind == 'uwb':
            if e.get('representation') != 'bridge': continue
            identity = (car, e['source_observation_id'])
            if identity in seen: continue
            seen.add(identity)
        streams[car][kind].append(e)
    return streams


def check_bins(row, config, streams, origin):
    cutoff = row['availability_cutoff_epoch_ns']; stamp = row['state_epoch_ns']
    # F0 associates bins in centered float seconds. Preserve its inherited
    # representational edge behavior; receipt/cutoff evidence remains integer ns.
    half = config['replay']['range_bin_half_width_s']
    all_peer_ids = {}
    for car in CARS:
        m = config['models'][car]; b = row['bins'][car]
        ranges = [e for e in streams[car]['uwb'] if e['receive_epoch_ns'] <= cutoff and
                  abs((e['header_epoch_ns']-origin)/1e9-row['state_time_s']) <= half]
        grouped = {k: [] for k in m['anchors_xyz_m']}
        peer = []; ids = []; key = 'node_0' if car == 'car1' else 'node_1'
        for e in ranges:
            for k, v in e['value'].items():
                if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0: continue
                if k in grouped and v-m['range_bias_m'][k] > 0: grouped[k].append(v)
                if k == key: peer.append(v); ids.append(e['source_observation_id'])
        expected = {k: float(np.median(v)) for k, v in grouped.items()
                    if len(v) >= config['replay']['minimum_samples_per_link']}
        if expected != b['observations']: raise AssertionError('Wall bin differs from receive prefix')
        if {k: len(v) for k, v in grouped.items()} != b['sample_counts']: raise AssertionError('Wall support differs')
        median = float(np.median(peer)) if len(peer) >= config['peer']['minimum_samples'] else None
        target = row['peer_median_m'] if car == 'car1' else row['reverse_peer_median_m']
        if median != target: raise AssertionError('Selected-direction peer median differs')
        dependencies = row['peer_dependencies'] if car == 'car1' else row['reverse_diagnostic_dependencies']
        if ids != [d['identity']['source_observation_id'] for d in dependencies]:
            raise AssertionError('Peer dependency identity mismatch')
        odom = [e for e in streams[car]['odom'] if e['receive_epoch_ns'] <= cutoff]
        times = [e['header_epoch_ns'] for e in odom]; at = bisect.bisect_left(times, stamp)
        for i in range(1, len(odom)):
            # Unwrap independently, retaining the original integer timeline.
            prev, cur = odom[i-1]['value']['pose'], odom[i]['value']['pose']
            cur[2] = prev[2]+wrap(cur[2]-prev[2])
        if at < len(times) and times[at] == stamp: pose = np.array(odom[at]['value']['pose'])
        elif at == 0 or at == len(times): pose = None
        else:
            ratio = (stamp-times[at-1])/(times[at]-times[at-1])
            left, right = np.array(odom[at-1]['value']['pose']), np.array(odom[at]['value']['pose'])
            pose = left+ratio*(right-left)
        if pose is None:
            if b['local_odom'] is not None: raise AssertionError('Unreceived Odom bracket used')
        else: np.testing.assert_allclose(b['local_odom'], pose, atol=3e-13, rtol=1e-13)
        all_peer_ids[car] = ids
    return all_peer_ids


def audit(root, events_path=None):
    root = Path(root); run = json.loads((root/'run.json').read_text())
    config = json.loads((root/'config.json').read_text()); enabled = run['method_id'] == 'D1'
    residuals.peer_sigma = config['peer']['sigma_m']
    if run['status'] != 'DONE': raise AssertionError('Run not completed')
    # run.config_sha256 identifies the original input file; config.json is a
    # canonical reserialization, whose bytes are separately covered by outputs.
    for output in run['outputs']:
        if sha(root/output['relative_path']) != output['sha256']: raise AssertionError('Output SHA '+output['relative_path'])
    rows = read_jsonl(root/'updates.jsonl.gz')
    with (root/'published.csv').open() as f: publications = list(csv.DictReader(f))
    if len(publications) != 2*len(rows): raise AssertionError('Missing publication rows')
    keys = [(int(p['state_epoch_ns']), p['vehicle_id']) for p in publications]
    if len(keys) != len(set(keys)): raise AssertionError('Publication rewrite/duplicate key')
    events = read_jsonl(events_path) if events_path else None
    streams = input_streams(events) if events is not None else None
    if events is not None and sha(events_path) != run['inputs'][0]['sha256']: raise AssertionError('Input SHA')
    costs = []; details = []; prior_epoch = None; prior_marginalizations = 0
    for index, row in enumerate(rows):
        epoch = row['state_epoch_ns']; cutoff = row['availability_cutoff_epoch_ns']
        if type(epoch) is not int or type(cutoff) is not int: raise AssertionError('Noninteger output ns')
        if prior_epoch is not None and epoch <= prior_epoch: raise AssertionError('Nonincreasing output keys')
        prior_epoch = epoch
        if cutoff-epoch != round(config['replay']['release_delay_s']*1e9): raise AssertionError('Changed wait')
        dep = row['dependency_receipt_max_s']
        if dep is not None and dep > row['availability_cutoff_s']+1e-12: raise AssertionError('Late dependency')
        for name in ('peer_dependencies', 'reverse_diagnostic_dependencies'):
            for p in row[name]:
                if p['identity']['receive_epoch_ns'] > cutoff: raise AssertionError('Future peer identity')
                if abs(p['header_s']-row['state_time_s']) > config['replay']['range_bin_half_width_s']+1e-12:
                    raise AssertionError('Peer outside bin')
        if streams is not None:
            check_bins(row, config, streams, run['epoch_origin_ns'])
            if cutoff > events[-1]['receive_epoch_ns']: raise AssertionError('Artificial EOF advancement')
        snap = row['snapshot']; times = snap['times_s']
        if times and times[-1]-times[0] > 20+1e-12: raise AssertionError('Unbounded time window')
        if len(times) > 21 or row['scalar_variables'] != 6*len(times): raise AssertionError('Variable bound/count')
        if row['marginalizations'] < prior_marginalizations: raise AssertionError('Marginal counter rolled back')
        if row['marginalizations']-prior_marginalizations != len(row['marginalization_details']):
            raise AssertionError('Missing marginal evidence')
        prior_marginalizations = row['marginalizations']; details.extend(row['marginalization_details'])
        for i, car in enumerate(CARS):
            pub = publications[2*index+i]
            if int(pub['state_epoch_ns']) != epoch or pub['vehicle_id'] != car: raise AssertionError('Published identity differs')
            if (pub['valid'] == 'True') != row['accepted_graph']: raise AssertionError('Validity differs')
            if pub['status'] != row['status']: raise AssertionError('Status differs')
            if row['pose'] is None:
                if any(pub[k] for k in ('base_x_m', 'base_y_m', 'yaw_rad')): raise AssertionError('Missing pose filled')
            else:
                p = row['pose'][3*i:3*i+3]
                np.testing.assert_allclose([float(pub[k]) for k in ('base_x_m', 'base_y_m', 'yaw_rad')], p, atol=1e-14, rtol=0)
                np.testing.assert_allclose([float(pub[k]) for k in ('antenna_x_m', 'antenna_y_m', 'antenna_z_m')],
                                           ant(p, config['models'][car]), atol=1e-14, rtol=0)
        if row['accepted_graph']:
            r = residuals(np.asarray(snap['states']).ravel(), times, snap['local'], snap['observations'],
                          snap['peers_m'], config['models'], snap['prior'], enabled)
            cost = float(r@r/2); reported = row['optimizer']['cost']
            if abs(cost-reported) > 1e-8*max(1, abs(cost)): raise AssertionError('Objective cost differs')
            costs.append(abs(cost-reported))
            np.testing.assert_allclose(row['pose'], snap['states'][-1], atol=0, rtol=0)
        if row['peer_factor_used'] and (not enabled or row['peer_median_m'] is None):
            raise AssertionError('Missing/disabled peer factor claimed')
    selected = [details[0], details[-1]] if len(details) > 1 else details
    checked = [marginal_check(d, config, enabled) for d in selected]
    return dict(schema_version=1, status='PASS', role='independent_two_car_artifact_readback',
        run_id=run['run_id'], method_id=run['method_id'], source_code_commit=run['code_commit'],
        declared_input_config_sha256=run['config_sha256'], archived_config_sha256=sha(root/'config.json'),
        auditor_sha256=sha(__file__), input_sha256=sha(events_path) if events_path else None,
        run_json_sha256=sha(root/'run.json'), publications_checked=len(publications),
        accepted_objectives_checked=len(costs), max_objective_cost_abs=max(costs, default=0.),
        marginalizations_recorded=len(details), marginalizations_finite_difference_checked=checked,
        receive_prefix_bins_checked=len(rows) if streams is not None else 0,
        checks=['artifact SHA', 'unique increasing publications', 'deadline/EOF dependencies',
                'published pose/antenna/validity', 'independent model objective', 'finite-difference Schur H/g/constant',
                '6x6 prior cross information', 'retained variables bounded'],
        limitations=['does not rerun optimizer or claim field accuracy',
                     'bin association preserves inherited F0 centered-float edge behavior at +/-0.4s; receipt cutoffs checked in integer ns',
                     'no rewrite verified as unique immutable output keys and snapshot consistency; executable prefix test is separate',
                     'finite-difference marginalization samples first and last elimination, not every elimination'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True); parser.add_argument('--events-jsonl', type=Path)
    parser.add_argument('--output', type=Path, required=True); args = parser.parse_args()
    if args.output.exists(): raise FileExistsError(args.output)
    try: result = audit(args.run, args.events_jsonl)
    except Exception as error:
        result = dict(status='FAIL', error=type(error).__name__+': '+str(error), auditor_sha256=sha(__file__))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False)+'\n')
    print(json.dumps({k: result[k] for k in ('status',) if k in result}))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__': raise SystemExit(main())
