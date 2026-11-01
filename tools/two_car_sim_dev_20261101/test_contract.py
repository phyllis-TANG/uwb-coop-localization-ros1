"""Interface/numerical contracts, using only exposed development seed7."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from common import CARS, EPOCH_NS, HERE, ROOT, digest, dump, lines, sha, sources, write_lines
from generate import design, make, validate
from adapter import WeightedObjective, core, replay, weighted_eliminate
import readback
eval_spec = importlib.util.spec_from_file_location('_sim_dev_evaluate', HERE/'evaluate.py')
evaluate = importlib.util.module_from_spec(eval_spec)
eval_spec.loader.exec_module(evaluate)


def fixture():
    from configuration import default_config
    config = default_config()
    times = [0., 1., 2.]
    states = np.tile(core.initial(config).point, (3, 1))
    local = np.zeros((3, 2, 3))
    for k in range(3):
        states[k] += np.array([.04*k, .007*k*k, .02*k, .001, .02*k, .01*k*k, -.01*k, -.002])
        local[k] = [[.03*k, .003*k*k, .01*k], [.02*k, .003*k, -.01*k]]
    obs = [{c:{key:float(np.linalg.norm(readback.ind.ant(states[k, i*4:i*4+4], config['models'][c])-value))+.005
               for key, value in config['models'][c]['anchors_xyz_m'].items()} for i,c in enumerate(CARS)} for k in range(3)]
    peers = [float(np.linalg.norm(readback.ind.ant(x[:4], config['models']['car1'])-readback.ind.ant(x[4:], config['models']['car2'])))+.08 for x in states]
    intervals = [{c:dict(valid=True, start_epoch_ns=k*10**9, end_epoch_ns=(k+1)*10**9, dt_ns=10**9,
                      raw_angle_rad=.02 if c == 'car1' else -.01, partial_angle_rad=.02,
                      segments=[], gaps=[]) for c in CARS} for k in range(2)]
    return config, times, local, obs, peers, intervals, states, core.initial(config)


def execute(config, events, method):
    rows = []
    engine = replay(config, method, rows.append, events[0]['receive_epoch_ns'])
    for event in events:
        engine.ingest(event)
    engine.finish()
    return rows, engine


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads((HERE/'development_static_moving.json').read_text())
        cls.config, cls.events, cls.truth, cls.labels = make(cls.spec, 'nominal')
        cls.fault = make(cls.spec, 'car1_wall_14')

    def test_source_locks_and_input_separation(self):
        self.assertGreater(len(sources()), 30)
        forbidden = {'truth', 'labels', 'fault', 'condition', 'bias_rad_s', 'trajectory'}
        for row in self.events:
            self.assertFalse(forbidden.intersection(row))
            self.assertFalse(forbidden.intersection(row['value']))
            self.assertLessEqual(row['header_epoch_ns'], row['receive_epoch_ns'])
        self.assertEqual(digest(make(self.spec, 'nominal')), digest((self.config, self.events, self.truth, self.labels)))
        c, events, truth, labels = self.fault
        self.assertEqual(c, self.config)
        self.assertEqual(truth, self.truth)
        self.assertNotEqual(labels, self.labels)

    def test_exact_common_fault_peer_and_all_other_streams_unchanged(self):
        changed = 0
        for a, b in zip(self.events, self.fault[1]):
            self.assertEqual(a['source_observation_id'], b['source_observation_id'])
            for key in ('record_index', 'header_epoch_ns', 'receive_epoch_ns', 'case_id', 'vehicle_id', 'kind'):
                self.assertEqual(a[key], b[key])
            active = a['kind'] == 'uwb' and a['vehicle_id'] == 'car1' and 6 <= (a['header_epoch_ns']-EPOCH_NS)/1e9 < 20
            for key, value in a['value'].items():
                if active and key in self.config['models']['car1']['anchors_xyz_m']:
                    self.assertAlmostEqual(b['value'][key]-value, .30, places=14)
                    changed += 1
                else:
                    self.assertEqual(b['value'][key], value)
            self.assertEqual(b.get('raw_message_sha256', digest(b['value'])), digest(b['value']))
        self.assertEqual(changed, 1120)

    def test_zero_noise_3d_ranges_and_present_time_gyro(self):
        spec = copy.deepcopy(self.spec)
        for k in spec['noise']:
            spec['noise'][k] = 0.
        spec['gyro_bias_rad_s'] = dict(car1=0., car2=0.)
        config, events, _, _ = make(spec, 'nominal')
        for row in events:
            car, kind = row['vehicle_id'], row['kind']
            if car is None:
                continue
            t = (row['header_epoch_ns']-EPOCH_NS)/1e9
            xy, yaw, rate = design(t, car, spec)
            model = config['models'][car]
            if kind == 'imu':
                self.assertAlmostEqual(row['value']['angular_velocity_rad_s'][2], rate, places=13)
            if kind == 'uwb':
                for key, anchor in model['anchors_xyz_m'].items():
                    expected = math.dist([*xy, model['antenna_height_m']], anchor)
                    self.assertAlmostEqual(row['value'][key], expected, places=13)
        self.assertEqual(design(16., 'car2', spec)[2], 0.)

    def test_roles_both_moving_and_unfrozen_inputs_rejected(self):
        swapped = copy.deepcopy(self.spec)
        swapped['fixed_car'] = 'car2'
        np.testing.assert_array_equal(design(5, 'car2', swapped)[0], [1.5, 4])
        np.testing.assert_array_equal(design(5, 'car1', swapped)[0], design(5, 'car2', self.spec)[0])
        both = json.loads((HERE/'development_both_moving.json').read_text())
        validate(both)
        vectors = [design(t, 'car2', both)[0]-design(t, 'car1', both)[0] for t in (0., 8., 16.)]
        self.assertGreater(abs(vectors[0][0]*vectors[1][1]-vectors[0][1]*vectors[1][0]), .01)
        self.assertGreater(np.linalg.norm(design(8., 'car1', both)[0]-design(0., 'car1', both)[0]), .1)
        for key, value in [('seed', 211), ('development_only', False), ('sample_step_ns', 10)]:
            bad = dict(self.spec, **{key:value})
            with self.assertRaises(ValueError):
                validate(bad)
        with self.assertRaises(ValueError):
            make(self.spec, 'car1_wall_28')  # 6+28 exceeds this short development horizon.

    def test_cost_weight_and_finite_difference_jacobian(self):
        c,t,l,o,p,e,x,prior = fixture()
        plain = core.Objective(t,l,o,p,e,c,prior,True)
        weighted = WeightedObjective(t,l,o,p,e,c,prior,True)
        r, j = plain.evaluate(x.ravel())
        w, k = weighted.evaluate(x.ravel())
        np.testing.assert_array_equal(w[:-3], r[:-3])
        np.testing.assert_array_equal(k[:-3], j[:-3])
        np.testing.assert_allclose(w[-3:], r[-3:]*.5)
        np.testing.assert_allclose(k[-3:], j[-3:]*.5)
        self.assertAlmostEqual(float(w[-3:]@w[-3:]), float(r[-3:]@r[-3:])*.25)
        np.testing.assert_array_equal(weighted.fun(x.ravel()), weighted.fun(x.ravel()))
        steps = np.eye(x.size)*1e-6
        fd = np.column_stack([(weighted.fun(x.ravel()+h)-weighted.fun(x.ravel()-h))/2e-6 for h in steps])
        np.testing.assert_allclose(k, fd, atol=3e-6, rtol=3e-6)

    def test_weighted_qr_prior_full_cross_affine_constant_negative_controls(self):
        c,t,l,o,p,e,x,prior = fixture()
        after, _, detail = weighted_eliminate(x,t,l,o,p,e,c,prior,True)
        readback.marginal(detail, c, .25, True)
        self.assertGreater(np.linalg.norm((after.matrix.T@after.matrix)[:4,4:]), .001)
        for kind in ('cross', 'affine', 'constant'):
            bad = copy.deepcopy(detail)
            if kind == 'cross':
                matrix = np.array(bad['after']['matrix'])
                matrix[:4,4:] = 0.
                bad['after']['matrix'] = matrix.tolist()
            elif kind == 'affine':
                bad['after']['offset'] = [0.]*8
            else:
                bad['constant'] += .1
            with self.assertRaises(ValueError):
                readback.marginal(bad, c, .25, True)

    def test_missing_gyro_never_reintroduces_odom_angle(self):
        c,t,l,o,p,e,x,prior = fixture()
        c['optimizer']['max_nfev'] = 1
        graph = core.WindowGraph(c, True)
        previous = graph.update(0., l[0], o[0], p[0])
        for k in (1,2):
            e[k-1]['car1'].update(valid=False, raw_angle_rad=None)
            l[k,0,2] = 2.*k
            graph.next_intervals = e[k-1]
            row = graph.update(t[k], l[k], o[k], p[k])
            self.assertEqual(row['prediction_pose'][2], previous['pose'][2])
            self.assertFalse(row['estimate_valid']['car1'])
            self.assertFalse(row['odom_yaw_fallback'])
            previous = row

    def test_prefix_causality_after_marginalization(self):
        prefix = [e for e in self.events if e['receive_epoch_ns'] <= EPOCH_NS+26*10**9]
        longer = [e for e in self.events if e['receive_epoch_ns'] <= EPOCH_NS+28*10**9]
        short, _ = execute(self.config, prefix, 'M3W025')
        long, _ = execute(self.config, longer, 'M3W025')
        long = [r for r in long if r['availability_cutoff_epoch_ns'] <= prefix[-1]['receive_epoch_ns']]
        self.assertEqual(len(short), len(long))
        for a,b in zip(short,long):
            for key in ('pose','prediction_pose','snapshot','prior','bins','angular_intervals','marginalization_details','monitor','state_epoch_ns'):
                self.assertEqual(a[key], b[key], key)
        self.assertGreater(short[-1]['marginalizations'], 0)

    def test_no_peer_other_car_fault_independence_through_prior(self):
        stop = EPOCH_NS+27*10**9
        a, _ = execute(self.config, [e for e in self.events if e['receive_epoch_ns'] <= stop], 'M2')
        altered = copy.deepcopy(self.fault[1])
        for event in altered:
            if event['kind'] == 'uwb':
                event['value']['node_0' if event['vehicle_id'] == 'car1' else 'node_1'] += 1.
        b, _ = execute(self.config, [e for e in altered if e['receive_epoch_ns'] <= stop], 'M2')
        for x,y in zip(a,b):
            np.testing.assert_allclose(x['pose'][4:], y['pose'][4:], atol=1e-10, rtol=0)
            self.assertTrue(all(v is None for v in x['snapshot']['peers_m']))
        self.assertGreater(a[-1]['marginalizations'], 0)

    def test_baseline_bins_b1_inputs_and_truth_file_access(self):
        events = [e for e in self.events if e['receive_epoch_ns'] <= EPOCH_NS+5*10**9]
        original_open = open
        def guard(path, *args, **kwargs):
            if 'truth' in str(path) or 'labels' in str(path):
                raise AssertionError('Estimator tried evaluator input')
            return original_open(path, *args, **kwargs)
        results = []
        with patch('builtins.open', guard):
            for method in ('M2','M3','M3W025'):
                rows, _ = execute(self.config, events, method)
                results.append(rows)
        for rows in results[1:]:
            self.assertEqual([r['bins'] for r in rows], [r['bins'] for r in results[0]])
            self.assertEqual([r['monitor']['B1']['raw_local'] for r in rows], [r['monitor']['B1']['raw_local'] for r in results[0]])
        for row in results[-1]:
            self.assertEqual(row['monitor']['B2']['network']['status'], 'unknown')
            self.assertFalse(row['monitor']['B1']['network']['available'])

    def test_evaluator_preserves_whole_run_unknown_alarm_and_hmi_denominators(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inp, run = root/'input', root/'run'
            inp.mkdir(); run.mkdir()
            c = copy.deepcopy(self.config)
            for car in CARS:
                c['models'][car]['base_to_antenna_body_xy_m'] = [0.,0.]
            dump(inp/'config.json', c); dump(run/'config.json', c)
            write_lines(inp/'events.jsonl.gz', [])
            write_lines(inp/'truth.jsonl.gz', [dict(state_epoch_ns=EPOCH_NS+t*10**9,
                cars={car:dict(pose=[0.,0.,0.],antenna_xyz_m=[0.,0.,.2]) for car in CARS}) for t in range(5)])
            dump(inp/'labels.json', dict(duration_s=4,epoch_ns=EPOCH_NS,condition='nominal',fault=None))
            dump(inp/'manifest.json', dict(files={p.name:sha(p) for p in inp.iterdir()}))
            rows = []
            for t,status in [(1,'alarm'),(2,'available'),(3,'unknown')]:
                dec = dict(status=status,alarm=status=='alarm',available=status=='available')
                mon = dict(local={car:dec for car in CARS}, network=dec)
                rows.append(dict(state_epoch_ns=EPOCH_NS+t*10**9,pose=[.2,0.,0.,0.,.2,0.,0.,0.],
                    estimate_valid={car:True for car in CARS},status='graph',monitor=dict(B1=mon,B2=mon)))
            write_lines(run/'updates.jsonl.gz', rows)
            dump(run/'run.json', dict(status='DONE', method_id='fixture',
                input_sha256=sha(inp/'events.jsonl.gz'), config_sha256=sha(inp/'config.json'),
                outputs={p.name:sha(p) for p in run.iterdir()}))
            result = evaluate.evaluate(run, inp)
            s = result['monitor']['B1']['local']['car1']['0.1']
            self.assertEqual([s[k] for k in ('unknown_s','alarm_s','available_s','overlimit_no_alarm_s','overlimit_available_no_alarm_s','overlimit_unknown_s','unknown_error_s','unprotected_or_unknown_error_s')], [2,1,1,2,1,1,1,3])
            self.assertEqual(result['cars']['car1']['whole_run_s'], 4)
            self.assertIsNone(s['normal_alarm_occupancy_fraction'])
            self.assertIsNone(result['recovery_time_s'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
