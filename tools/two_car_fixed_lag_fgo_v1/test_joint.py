"""Independent property checks for the joint F0 extension (no formal seeds)."""
import copy
import gzip
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from legacy import CARS, Event, FixedLagReplay, PoseWindowGraph, antenna, initial_prior
from graph import JointPrior, Objective, WindowGraph, eliminate_oldest, incident_system, joint_initial, peer_residual
from frontend import JointReplay

HERE = Path(__file__).resolve().parent
EPOCH = 1790000000000000000


def config():
    return json.loads((HERE / 'config.json').read_text())


def pose_at(t, i):
    return np.array([1.5+1.1*i+.012*t+.16*math.sin(.17*t+i),
                     3.4-1.5*i+.08*math.cos(.11*t+2*i), .3+.5*i+.12*math.sin(.13*t)])


def wall_ranges(pose, model, t=0.):
    ant = np.r_[antenna(pose, model['base_to_antenna_body_xy_m']), model['antenna_height_m']]
    return {k: float(np.linalg.norm(ant-np.asarray(xyz))+.008*math.sin(t+idx))
            for idx, (k, xyz) in enumerate(sorted(model['anchors_xyz_m'].items()))}


def inputs(n=32):
    c = config(); times = list(np.arange(n, dtype=float))
    local = np.array([[pose_at(t, i) for i in range(2)] for t in times])
    obs = [{car: wall_ranges(local[k, i], c['models'][car], t) for i, car in enumerate(CARS)}
           for k, t in enumerate(times)]
    peers = [float(np.linalg.norm(np.r_[antenna(local[k, 0], [.08, -.06]), .17]-
                                   np.r_[antenna(local[k, 1], [.12, -.08]), .2])+.015)
             for k in range(n)]
    return c, times, local, obs, peers


def raw(kind, car, t, received, value, tag=''):
    return dict(kind=kind, vehicle_id=car, case_id='synthetic_independent_fixture', record_index=0,
                header_epoch_ns=EPOCH+round(t*1e9), receive_epoch_ns=EPOCH+round(received*1e9),
                source_file_sha256='a'*64, topic='/'+str(car)+'/'+kind, value=value,
                representation='bridge', source_observation_id=f'{car}:{kind}:{t}:{tag}')


def ordered(events):
    events = sorted(events, key=lambda e: e['receive_epoch_ns'])
    for i, e in enumerate(events): e['record_index'] = i
    return events


def events_for(duration=32, peer_gap=None, omit_odom=None):
    c = config(); events = [raw('clock', None, 0, 0, {})]
    for tick in range(10*duration+1):
        t = tick/10
        ants = [np.r_[antenna(pose_at(t, i), c['models'][car]['base_to_antenna_body_xy_m']),
                      c['models'][car]['antenna_height_m']] for i, car in enumerate(CARS)]
        distance = float(np.linalg.norm(ants[0]-ants[1]))
        for i, car in enumerate(CARS):
            p = pose_at(t, i)
            if not (omit_odom and car == omit_odom[0] and omit_odom[1] <= t <= omit_odom[2]):
                events.append(raw('odom', car, t, t+.01+i*.001, {'pose': p.tolist()}))
            vals = wall_ranges(p, c['models'][car], t)
            if not peer_gap or not peer_gap[0] <= t < peer_gap[1]:
                vals['node_0' if i == 0 else 'node_1'] = distance
            events.append(raw('uwb', car, t, t+.02+i*.001, vals))
    return c, ordered(events)


def run(c, events, arm='D1'):
    rows = []; replay = JointReplay(c, arm, rows.append, EPOCH)
    for e in events: replay.ingest(copy.deepcopy(e))
    replay.finish()
    return replay, rows


def numerical_jac(fun, x, eps=1e-6):
    cols = []
    for i in range(len(x)):
        d = np.zeros_like(x); d[i] = eps
        cols.append((np.asarray(fun(x+d))-np.asarray(fun(x-d)))/(2*eps))
    return np.asarray(cols).T


class FactorTests(unittest.TestCase):
    def test_peer_residual_independent_3d_geometry_and_jacobian(self):
        c = config(); x = np.array([1.1, 2.4, math.pi-.03, 2.2, 3.3, -math.pi+.07])
        c['models']['car2']['antenna_height_m'] = .93
        positions = []
        for i, car in enumerate(CARS):
            m = c['models'][car]; lx, ly = m['base_to_antenna_body_xy_m']; th = x[3*i+2]
            positions.append([x[3*i]+math.cos(th)*lx-math.sin(th)*ly,
                              x[3*i+1]+math.sin(th)*lx+math.cos(th)*ly, m['antenna_height_m']])
        for measured in (1.1, 2.6, float(np.linalg.norm(np.subtract(*positions)))):
            r, j = peer_residual(x, measured, c['models'], .2)
            error = (np.linalg.norm(np.subtract(*positions))-measured)/.2
            self.assertAlmostEqual(r*r, 2*(math.sqrt(1+error*error)-1), places=11)
            fd = numerical_jac(lambda z: peer_residual(z, measured, c['models'], .2)[0], x)
            np.testing.assert_allclose(j, fd, atol=2e-8, rtol=2e-7)
        _, j = peer_residual(x, 1.1, c['models'], .2)
        np.testing.assert_allclose(j[:2], -j[3:5], atol=1e-13)

    def test_peer_invalid_and_coincident_guard(self):
        c = config(); x = np.array([1., 2., 0., 1., 2., 0.])
        for car in CARS:
            c['models'][car]['base_to_antenna_body_xy_m'] = [0., 0.]
            c['models'][car]['antenna_height_m'] = .2
        for measured in (0., -1., float('nan')):
            with self.assertRaises(ValueError): peer_residual(x, measured, c['models'], .2)
        with self.assertRaises(ValueError): peer_residual(x, 1., c['models'], .2)

    def test_full_objective_jacobian_and_d0_block_diagonal(self):
        c, t, local, obs, peers = inputs(4); prior = joint_initial(c)
        prior.offset = np.array([.2, -.1, .05, .3, -.4, .07])
        x = local.reshape(4, 6).ravel()+np.tile([.02, -.03, .01, -.04, .01, -.02], 4)
        for enabled in (False, True):
            obj = Objective(t, local, obs, peers, c, prior, enabled)
            np.testing.assert_allclose(obj.jac(x), numerical_jac(obj.fun, x), atol=3e-7, rtol=2e-6)
            if not enabled:
                h = obj.jac(x).T @ obj.jac(x)
                a = (6*np.arange(4)[:, None]+np.arange(3)).ravel()
                b = (6*np.arange(4)[:, None]+np.arange(3, 6)).ravel()
                np.testing.assert_allclose(h[np.ix_(a, b)], 0., atol=1e-12)

    def test_joint_qr_matches_schur_with_affine_offset_and_constant(self):
        c, t, local, obs, peers = inputs(3)
        states = local.reshape(3, 6)+[.1, -.03, .03, -.02, .05, -.01]
        prior = joint_initial(c); prior.offset += np.arange(6)*.13-.2
        r, j = incident_system(states, t, local, obs, peers, c, prior, True)
        h, g = j.T@j, j.T@r
        hs = h[6:, 6:]-h[6:, :6]@np.linalg.solve(h[:6, :6], h[:6, 6:])
        gs = g[6:]-h[6:, :6]@np.linalg.solve(h[:6, :6], g[:6])
        cs = float(r@r-g[:6]@np.linalg.solve(h[:6, :6], g[:6]))
        p, constant, details = eliminate_oldest(states, t, local, obs, peers, c, prior, True)
        np.testing.assert_allclose(p.matrix.T@p.matrix, hs, rtol=2e-11, atol=3e-10)
        np.testing.assert_allclose(p.matrix.T@p.offset, gs, rtol=2e-11, atol=3e-10)
        self.assertAlmostEqual(float(p.offset@p.offset+constant), cs, places=10)
        self.assertGreater(np.linalg.norm(hs[:3, 3:]), .01)
        self.assertGreater(np.linalg.norm(p.offset), .01)
        self.assertEqual(details['rank_joint'], 12)

    def test_retained_factors_not_consumed_or_double_counted(self):
        c, t, local, obs, peers = inputs(3); states = local.reshape(3, 6); prior = joint_initial(c)
        p, k, _ = eliminate_oldest(states, t, local, obs, peers, c, prior, True)
        changed = copy.deepcopy(obs); changed[1]['car1']['node_2'] += 4.; changed[2]['car2']['node_3'] += 3.
        other = peers.copy(); other[1] += 8.; other[2] += 5.
        p2, k2, _ = eliminate_oldest(states, t, local, changed, other, c, prior, True)
        np.testing.assert_array_equal(p.matrix, p2.matrix); np.testing.assert_array_equal(p.offset, p2.offset)
        self.assertEqual(k, k2)
        obj = Objective(t[1:], local[1:], obs[1:], peers[1:], c, p, True)
        # 6 prior + 6 between + 16 walls + 2 retained peer residuals.
        self.assertEqual(len(obj.fun(states[1:].ravel())), 30)
        off, _, _ = eliminate_oldest(states, t, local, obs, peers, c, prior, False)
        np.testing.assert_allclose((off.matrix.T@off.matrix)[:3, 3:], 0., atol=2e-12)

    def test_d0_matches_two_original_f0_graphs_through_marginalization(self):
        c, t, local, obs, peers = inputs(31)
        joint = WindowGraph(c, False); singles = [PoseWindowGraph(c['models'][car]) for car in CARS]
        worst = 0.
        for k, stamp in enumerate(t):
            output = joint.update(stamp, local[k], obs[k], peers[k])
            for i, car in enumerate(CARS):
                ref = singles[i].update(stamp, local[k, i], obs[k][car])
                err = np.max(np.abs(np.asarray(output['pose'])[3*i:3*i+3]-ref['pose']))
                worst = max(worst, err)
                self.assertLess(err, 1e-5)
                self.assertEqual(output['accepted_graph'], ref['accepted_graph'])
        self.assertEqual(joint.marginalizations, 10)
        self.assertEqual(joint.peak_solve_states, 21)
        self.assertEqual(joint.peak_transient_states, 22)

    def test_solver_failure_predicts_and_never_accepts_candidate(self):
        c, t, local, obs, peers = inputs(5); graph = WindowGraph(c)
        for k in range(2): graph.update(t[k], local[k], obs[k], peers[k])
        with patch('graph.least_squares', side_effect=ValueError('injected')):
            out = graph.update(t[2], local[2], obs[2], peers[2])
        self.assertFalse(out['accepted_graph']); self.assertEqual(out['status'], 'predict_only_solver_error')
        np.testing.assert_array_equal(out['pose'], out['prediction_pose'])
        fake = SimpleNamespace(x=np.asarray(graph.states).ravel(), success=False, status=0, nfev=50,
                               cost=1., optimality=1., message='injected budget')
        # Separate graph avoids a candidate dimension mismatch as another keyframe is appended.
        graph2 = WindowGraph(c)
        for k in range(2): graph2.update(t[k], local[k], obs[k], peers[k])
        fake.x = np.tile([100., 100., 1., 100., 100., 1.], 3)
        with patch('graph.least_squares', return_value=fake):
            out = graph2.update(t[2], local[2], obs[2], peers[2])
        self.assertFalse(out['accepted_graph']); self.assertEqual(out['status'], 'predict_only_solver_failed')
        np.testing.assert_array_equal(out['pose'], out['prediction_pose'])
        self.assertNotEqual(out['pose'], out['candidate_pose'])
        self.assertTrue(graph2.update(t[3], local[3], obs[3], peers[3])['accepted_graph'])

    def test_marginalization_failure_transaction_and_recovery(self):
        c, t, local, obs, peers = inputs(24); graph = WindowGraph(c)
        for k in range(21): graph.update(t[k], local[k], obs[k], peers[k])
        before = copy.deepcopy(graph.snapshot())
        with patch('graph.eliminate_oldest', side_effect=np.linalg.LinAlgError('injected rank failure')):
            out = graph.update(t[21], local[21], obs[21], peers[21])
        self.assertEqual(out['status'], 'predict_only_marginal_error'); self.assertFalse(out['accepted_graph'])
        self.assertEqual(graph.snapshot(), before)
        out = graph.update(t[22], local[22], obs[22], peers[22])
        self.assertTrue(out['accepted_graph']); self.assertEqual(graph.marginalizations, 2)

    def test_rank_deficiency_reported_not_replaced_with_diagonal(self):
        c, t, local, obs, peers = inputs(2); prior = joint_initial(c); prior.matrix[:] = 0
        with self.assertRaisesRegex(ValueError, 'Rank-deficient'):
            eliminate_oldest(local.reshape(2, 6), t, local, [{car: {} for car in CARS}]*2,
                             [None, None], c, prior, False)


class ReplayTests(unittest.TestCase):
    def test_receive_prefix_after_multiple_real_marginalizations(self):
        c, events = events_for(34); _, full = run(c, events)
        limit = EPOCH+round(29.4e9)
        prefix = [e for e in events if e['receive_epoch_ns'] <= limit]
        _, truncated = run(c, prefix)
        reference = [r for r in full if r['availability_cutoff_epoch_ns'] <= prefix[-1]['receive_epoch_ns']]
        self.assertEqual(len(reference), len(truncated))
        self.assertGreater(truncated[-1]['marginalizations'], 3)
        for a, b in zip(reference, truncated):
            self.assertEqual(a['state_epoch_ns'], b['state_epoch_ns'])
            np.testing.assert_array_equal(a['pose'], b['pose'])
            self.assertEqual(a['snapshot'], b['snapshot'])
        modified = copy.deepcopy(events)
        for e in modified:
            if e['receive_epoch_ns'] > limit and e['kind'] == 'uwb':
                for k in e['value']: e['value'][k] += 2.
        _, changed = run(c, modified)
        for a, b in zip(reference, changed): np.testing.assert_array_equal(a['pose'], b['pose'])

    def test_deadline_equality_late_count_and_immutable_publication(self):
        c = config(); items = [raw('clock', None, 0, 0, {})]
        for car in CARS:
            for t in (0., .5, 1., 1.5, 2., 2.2):
                items.append(raw('odom', car, t, t+.001, {'pose': pose_at(t, CARS.index(car)).tolist()}))
            vals = wall_ranges(pose_at(0, CARS.index(car)), c['models'][car]); vals['node_0' if car == 'car1' else 'node_1'] = 2.
            items.append(raw('uwb', car, 0, .01, vals))
            for t in (.7, .8, .9, 1., 1.1):
                items.append(raw('uwb', car, t, 2., vals))
            items.append(raw('uwb', car, 1.2, 2.1, vals))
        replay, rows = run(c, ordered(items))
        self.assertEqual(len(rows), 1); row = rows[0]
        self.assertEqual(row['availability_cutoff_s'], 2.)
        self.assertEqual(row['peer_sample_count'], 5)
        self.assertEqual(row['dependency_receipt_max_s'], 2.)
        for car in CARS:
            self.assertEqual(row['bins'][car]['sample_counts']['node_2'], 5)
            self.assertEqual(replay.binners[car].counters['late_packets_for_closed_bins'], 1)

    def test_raw_bridge_and_canonical_duplicate_do_not_double_count(self):
        c, events = events_for(7); _, reference = run(c, events)
        more = []
        for e in events:
            more.append(copy.deepcopy(e))
            if e['kind'] == 'uwb':
                duplicate = copy.deepcopy(e); duplicate['receive_epoch_ns'] += 1
                raw_copy = copy.deepcopy(e); raw_copy['representation'] = 'raw'; raw_copy['receive_epoch_ns'] += 2
                more.extend([duplicate, raw_copy])
        replay, rows = run(c, ordered(more))
        self.assertGreater(replay.counters['duplicate_canonical_ignored'], 0)
        self.assertGreater(replay.counters['noncanonical_raw_ignored'], 0)
        for a, b in zip(reference, rows):
            self.assertEqual(a['peer_sample_count'], b['peer_sample_count'])
            self.assertEqual(a['bins'], b['bins']); np.testing.assert_array_equal(a['pose'], b['pose'])

    def test_peer_gap_and_recovery_no_zero_distance_or_reverse_fallback(self):
        c, events = events_for(15, peer_gap=(5., 10.))
        # Keep the reverse measurement, which must never fill the selected direction.
        for e in events:
            if e['kind'] == 'uwb' and e['vehicle_id'] == 'car2': e['value']['node_1'] = 9.
        _, rows = run(c, events)
        for row in rows:
            t = row['state_time_s']
            if 6. <= t <= 9.:
                self.assertIsNone(row['peer_median_m']); self.assertFalse(row['peer_factor_used'])
                self.assertEqual(row['reverse_peer_median_m'], 9.)
                self.assertTrue(row['accepted_graph'])
            if t >= 11.: self.assertTrue(row['peer_factor_used'])
        self.assertTrue(all(p is None or p > 0 for r in rows for p in r['snapshot']['peers_m']))

    def test_missing_odom_has_explicit_invalid_output_then_recovers(self):
        c, events = events_for(10, omit_odom=('car1', .9, 2.1)); _, rows = run(c, events)
        missing = [r for r in rows if r['status'] == 'missing_odom_bracket']
        # Remove all future bracket before the first deadline instead of allowing interpolation over gap.
        e2 = [e for e in events if not (e['kind'] == 'odom' and e['vehicle_id'] == 'car1' and
                                       e['receive_epoch_ns'] < EPOCH+int(2.01e9) and
                                       e['header_epoch_ns'] > EPOCH+int(.8e9))]
        _, rows2 = run(c, e2)
        missing = [r for r in rows2 if r['status'] == 'missing_odom_bracket']
        self.assertTrue(missing); self.assertIsNone(missing[0]['pose']); self.assertFalse(missing[0]['accepted_graph'])
        self.assertTrue(rows2[-1]['accepted_graph'])

    def test_two_car_frontend_d0_matches_original_f0(self):
        c, events = events_for(28); _, rows = run(c, events, 'D0')
        for car in CARS:
            singles = []; replay = FixedLagReplay(c['models'][car], c['replay'], singles.append)
            for e in events:
                t = (e['receive_epoch_ns']-EPOCH)/1e9
                if e['vehicle_id'] == car and e['kind'] in ('odom', 'uwb'):
                    h = (e['header_epoch_ns']-EPOCH)/1e9
                    replay.ingest(Event(t, e['kind'], h, e['value']['pose'] if e['kind'] == 'odom' else e['value']))
                else: replay.ingest(Event(t, 'clock'))
            replay.finish(); self.assertEqual(len(singles), len(rows))
            for a, b in zip(rows, singles):
                i = CARS.index(car)
                np.testing.assert_allclose(a['pose'][3*i:3*i+3], b['pose'], atol=1e-5, rtol=0)
                self.assertEqual(a['bins'][car]['observations'], b['range_medians_m'])

    def test_bounded_graph_frontend_and_identity_cache_over_120_seconds(self):
        c, events = events_for(120); replay, rows = run(c, events)
        self.assertEqual(replay.graph.peak_solve_states, 21); self.assertEqual(replay.graph.peak_transient_states, 22)
        self.assertLessEqual(replay.pending_peak, 1); self.assertLessEqual(replay.peer_peak, 20)
        self.assertLessEqual(max(r['scalar_variables'] for r in rows), 126)
        for car in CARS:
            self.assertLessEqual(len(replay.recent_ids[car]), 512)
            self.assertLessEqual(max(replay.binners[car].sensor_peaks.values()), 30)
        self.assertGreater(replay.graph.marginalizations, 90)

    def test_buffer_overflow_reports_failure(self):
        c, events = events_for(3); c['frontend']['max_sensor_samples_per_stream'] = 3
        with self.assertRaises(BufferError): run(c, events)

    def test_truth_leakage_and_bad_timestamp_identity_rejected(self):
        c, events = events_for(2)
        for bad in (dict(events[0], receive_epoch_ns=float(EPOCH)),
                    dict(events[0], value={'truth': [0, 0]})):
            with self.assertRaises(ValueError): run(c, [bad])
        with self.assertRaises(ValueError): run(c, events[:3]+events[1:3])

    def test_synthetic_scope_cannot_bypass_holdout_identifier(self):
        c, events = events_for(2)
        for case in ('T09', 'T11', 'T13', 'T15', '015334', '033248'):
            with self.assertRaisesRegex(ValueError, 'BLOCKED'):
                run(c, [dict(events[0], case_id=case)])


class CliEvidenceTests(unittest.TestCase):
    def write_inputs(self, root, c, events):
        cfg = root / 'config.json'; inp = root / 'events.jsonl'
        cfg.write_text(json.dumps(c))
        inp.write_text(''.join(json.dumps(e)+'\n' for e in events))
        return cfg, inp

    def test_failed_run_persists_evidence_and_refuses_existing_directory(self):
        from replay import run as disk_run
        c, events = events_for(4)
        with tempfile.TemporaryDirectory(prefix='two-car-cli-') as tmp:
            root = Path(tmp); cfg, inp = self.write_inputs(root, c, events); output = root/'failed'
            with patch('replay.JointReplay.ingest', side_effect=ValueError('injected receive failure')):
                with self.assertRaisesRegex(ValueError, 'injected receive failure'):
                    disk_run(inp, cfg, 'D1', output)
            receipt = json.loads((output/'run.json').read_text())
            self.assertEqual(receipt['status'], 'FAILED')
            self.assertIn('injected receive failure', receipt['error'])
            self.assertTrue((output/'published.csv').exists()); self.assertTrue((output/'config.json').exists())
            before = {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()}
            with self.assertRaises(FileExistsError): disk_run(inp, cfg, 'D1', output)
            self.assertEqual(before, {p.name: p.read_bytes() for p in output.iterdir() if p.is_file()})

    def test_field_scope_and_holdout_refused_without_outputs(self):
        from replay import run as disk_run
        c, events = events_for(2); c['scope'] = 'field'
        with tempfile.TemporaryDirectory(prefix='two-car-field-') as tmp:
            root = Path(tmp); cfg, inp = self.write_inputs(root, c, events)
            for case in ('T08', 'T09', 'T11', 'T13', 'T15', '015334', '033248'):
                changed = copy.deepcopy(events)
                for e in changed: e['case_id'] = case
                _, inp = self.write_inputs(root, c, changed); out = root/case
                with self.assertRaisesRegex(ValueError, 'BLOCKED'):
                    disk_run(inp, cfg, 'D0', out)
                self.assertEqual(json.loads((out/'run.json').read_text())['status'], 'FAILED')
                self.assertFalse((out/'published.csv').exists())

    def test_independent_auditor_detects_sha_and_rehashed_objective_tampering(self):
        from replay import run as disk_run
        from audit import audit
        c, events = events_for(5)
        with tempfile.TemporaryDirectory(prefix='two-car-audit-') as tmp:
            root = Path(tmp); cfg, inp = self.write_inputs(root, c, events); out = root/'clean'
            disk_run(inp, cfg, 'D1', out)
            self.assertEqual(audit(out, inp)['status'], 'PASS')
            published = out/'published.csv'; original = published.read_bytes()
            published.write_bytes(original+b'\n')
            with self.assertRaisesRegex(AssertionError, 'Output SHA'): audit(out, inp)
            published.write_bytes(original)
            updates = out/'updates.jsonl.gz'
            with gzip.open(updates, 'rt') as f: rows = [json.loads(line) for line in f]
            target = next(r for r in rows if r['accepted_graph'])
            target['snapshot']['prior']['offset'][0] += 2.
            with gzip.open(updates, 'wt') as f:
                for row in rows: f.write(json.dumps(row)+'\n')
            # Even an attacker recomputing the artifact manifest cannot hide a
            # changed model snapshot from independent objective reconstruction.
            receipt = json.loads((out/'run.json').read_text())
            for artifact in receipt['outputs']:
                if artifact['relative_path'] == updates.name:
                    artifact['sha256'] = hashlib.sha256(updates.read_bytes()).hexdigest()
            (out/'run.json').write_text(json.dumps(receipt))
            with self.assertRaisesRegex(AssertionError, 'Objective cost differs'): audit(out, inp)


if __name__ == '__main__': unittest.main()
