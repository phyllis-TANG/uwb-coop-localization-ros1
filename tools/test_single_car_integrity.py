#!/usr/bin/env python3
"""Independent tests of sensor isolation, signs, prior history and failure semantics."""
import copy
import inspect
import json
from pathlib import Path
import unittest
from unittest.mock import patch
import numpy as np
from single_car_fixed_lag import FixedLagReplay, BoundaryPrior, WindowGraph
from single_car_integrity import IntegrityReplay, Trigger, graph_validity, range_residuals
from single_car_integrity_sim import generate, injection
from single_car_sequential_replay import Event
from test_single_car_sequential_replay import MODEL, POLICY, synthetic_events

ROOT=Path(__file__).resolve().parents[1]
PROTOCOL=ROOT/'docs/field_tests/integrity_feasibility_v1_20261022/protocol.json'


def config(model=MODEL):
    return dict(model=copy.deepcopy(model),replay=copy.deepcopy(POLICY),lag_s=20.,max_nfev=50,
                max_sensor_samples=512,monitor_rules=dict(consecutive_exceedances=2,rank_rtol=1e-8,condition_limit=1e8))


def run(events,conf=None):
    rows=[]; replay=IntegrityReplay(conf or config(),rows.append,dict(M1=1.,M2=.05))
    for event in events:
        replay.ingest(event)
    replay.finish()
    return replay,rows


def stable(rows):
    return [(r['state_time_s'],r['pose'],r.get('range_medians_m'),r['M1'],r['M2'],
             [(k,h['pose'],h.get('prior_matrix'),h['prior_lineage_sha256']) for k,h in r['exclusion_hypotheses'].items()]) for r in rows]


class IntegrityTests(unittest.TestCase):
    def test_full_locator_bitwise_identical_and_no_feedback(self):
        events=synthetic_events(28.)
        plain=[]; baseline=FixedLagReplay(MODEL,POLICY,plain.append)
        for event in events: baseline.ingest(event)
        baseline.finish()
        _,monitored=run(events)
        self.assertEqual([r['pose'] for r in plain],[r['pose'] for r in monitored])
        self.assertEqual([r['status'] for r in plain],[r['status'] for r in monitored])
        self.assertGreater(monitored[-1]['marginalizations'],0)

    def test_future_receipt_mutation_and_truncation_do_not_change_past(self):
        events=synthetic_events(31.)
        _,complete=run(events)
        changed=[Event(e.received_s,e.kind,e.header_s,{k:v+.3 for k,v in e.value.items()})
                 if e.kind=='uwb' and e.received_s>27 else e for e in events]
        _,mutated=run(changed)
        _,truncated=run([e for e in events if e.received_s<=27]+[Event(27.,'clock')])
        past=lambda r:[x for x in r if x['availability_cutoff_s']<=27]
        self.assertEqual(stable(past(complete)),stable(past(mutated)))
        self.assertEqual(stable(past(complete)),stable(truncated))
        self.assertNotEqual(complete[-1]['pose'],mutated[-1]['pose'])

    def test_exclusion_history_and_qr_prior_independent_of_excluded_fault(self):
        events=synthetic_events(32.)
        changed=[Event(e.received_s,e.kind,e.header_s,dict(e.value,b=e.value['b']+.5)) if e.kind=='uwb' else e for e in events]
        nominal,nrows=run(events); fault,frows=run(changed)
        a,b=nominal.hypotheses['b'],fault.hypotheses['b']
        self.assertIsNot(a.prior,nominal.full.graph.prior)
        self.assertFalse(np.shares_memory(a.prior.matrix,nominal.full.graph.prior.matrix))
        self.assertGreater(a.marginalizations,0)
        np.testing.assert_array_equal(a.prior.matrix,b.prior.matrix)
        np.testing.assert_array_equal(a.prior.offset,b.prior.offset)
        np.testing.assert_array_equal(a.prior.point,b.prior.point)
        self.assertEqual(nrows[-1]['exclusion_hypotheses']['b']['pose'],frows[-1]['exclusion_hypotheses']['b']['pose'])
        self.assertEqual(nominal.lineage['b'],fault.lineage['b'])
        self.assertNotEqual(nrows[-1]['pose'],frows[-1]['pose'])
        for key,graph in fault.hypotheses.items():
            self.assertTrue(all(key not in row for row in graph.observations))
            self.assertNotIn(key,fault.seen_anchors[key])

    def test_missing_data_and_insufficient_redundancy_not_trusted(self):
        changed=[Event(e.received_s,e.kind,e.header_s,{k:v for k,v in e.value.items() if k!='a'}) if e.kind=='uwb' else e for e in synthetic_events(6.)]
        _,rows=run(changed)
        self.assertTrue(all(not r['M2']['available'] and r['M2']['alarm'] is None for r in rows))
        _,missing=run([Event(0,'odom',0,(0,0,0)),Event(.01,'uwb',0,{'a':2}),Event(2.1,'clock')])
        self.assertFalse(missing[0]['M1']['available']); self.assertFalse(missing[0]['M2']['available'])

    def test_rank_deficiency_is_unavailable_even_with_accepted_graph(self):
        model=copy.deepcopy(MODEL)
        model['anchors_xyz_m']={k:[float(i+1),0,.2] for i,k in enumerate(model['anchors_xyz_m'])}
        graph=WindowGraph(model)
        for t in range(3): result=graph.update(t,np.zeros(3),{k:float(i+1) for i,k in enumerate(model['anchors_xyz_m'])})
        result['accepted_graph']=True
        validity=graph_validity(graph,result,graph.observations[-1],config()['monitor_rules'])
        self.assertFalse(validity['available']); self.assertIn('invalid_current_xy_geometry',validity['reasons'])

    def test_solver_and_marginalization_failures_never_mean_no_alarm(self):
        conf=config(); conf['max_nfev']=1
        shifted=[Event(e.received_s,e.kind,e.header_s,{k:v+.2 for k,v in e.value.items()}) if e.kind=='uwb' else e for e in synthetic_events(6.)]
        _,rows=run(shifted,conf)
        self.assertTrue(any('solver_failed' in r['status'] for r in rows))
        self.assertTrue(all(not r['M1']['available'] for r in rows))
        replay=IntegrityReplay(config(),lambda r:None)
        replay.hypotheses['a'].prior=BoundaryPrior(np.zeros(3),np.zeros((3,3)),np.zeros(3))
        with patch('single_car_fixed_lag.eliminate_oldest',side_effect=ValueError('Rank-deficient test')):
            # A broken hypothesis is explicitly latched by the wrapper.
            graph=replay.hypotheses['a']
            original=graph.update
            def fail(*args): raise ValueError('Rank-deficient test')
            graph.update=fail
            output=[]; replay.on_output=output.append
            for event in synthetic_events(4.): replay.ingest(event)
            replay.finish()
            self.assertIn('a',replay.poisoned)
            self.assertTrue(all(not r['M2']['available'] for r in output))

    def test_single_bias_subtraction_and_uncompressed_residual(self):
        model=copy.deepcopy(MODEL); model['range_bias_m']['a']=.3
        row=range_residuals(model,[0,0,0],{'a':2.1})[0]
        self.assertAlmostEqual(row['corrected_median_m'],1.8)
        self.assertAlmostEqual(row['raw_residual_m'],0)
        row=range_residuals(model,[0,0,0],{'a':3.1})[0]
        self.assertAlmostEqual(row['raw_residual_m'],-1.)
        self.assertGreater(abs(row['normalized_raw_residual']),abs(row['pseudo_huber_transformed_residual']))

    def test_injection_times_sign_amplitude_and_recovery(self):
        p=json.loads(PROTOCOL.read_text())
        by_id={s['id']:s for s in p['scenarios']}
        for name,amplitude in [('positive',.3),('negative',-.3),('spike',.5)]:
            s=by_id[name]; start,end=s['interval_s']
            self.assertEqual(injection(s,start-.001),(False,0.))
            self.assertEqual(injection(s,start),(True,amplitude))
            self.assertEqual(injection(s,end),(False,0.))
        self.assertAlmostEqual(injection(by_id['ramp'],42.5)[1],.15)
        nominal,_,_,_,_=generate(p,by_id['nominal'],777)
        for name,amplitude in [('positive',.3),('negative',-.3)]:
            fault,_,_,labels,_=generate(p,by_id[name],777)
            json.dumps(labels)  # Regression: numpy.bool_ must not break label persistence.
            for a,b in zip(nominal,fault):
                self.assertEqual(a['received_s'],b['received_s'])
                if a['kind']=='uwb':
                    active=25<=a['header_s']<60
                    for k in a['value']:
                        self.assertAlmostEqual(b['value'][k]-a['value'][k],amplitude if active and k=='node_10' else 0.,places=12)
                else:self.assertEqual(a,b)

    def test_sensors_and_estimator_config_have_no_truth_or_labels(self):
        p=json.loads(PROTOCOL.read_text()); events,*_=generate(p,p['scenarios'][0],778)
        self.assertTrue(all(set(e)=={'received_s','kind','header_s','value'} for e in events))
        self.assertEqual(set(inspect.signature(IntegrityReplay).parameters),{'config','on_output','thresholds'})
        self.assertTrue(all(a['received_s']<=b['received_s'] for a,b in zip(events,events[1:])))
        for kind in ('odom','uwb'):
            rows=[e for e in events if e['kind']==kind]
            self.assertTrue(all(a['header_s']<b['header_s'] for a,b in zip(rows,rows[1:])))
        worker=(ROOT/'tools/run_single_car_integrity_worker.py').read_text()
        self.assertNotIn('import single_car_integrity_sim',worker)
        self.assertNotIn('truth.csv',worker)
        self.assertNotIn('fault_labels.json',worker)

    def test_correlated_noise_preserves_stationary_marginal_variance(self):
        rng=np.random.default_rng(998)
        for rho in (.2,.98):
            state=rng.normal()*.06; values=[]
            for _ in range(100000):
                state=rho*state+.06*np.sqrt(1-rho*rho)*rng.normal(); values.append(state)
            self.assertAlmostEqual(np.std(values),.06,delta=.004)

    def test_trigger_two_consecutive_and_unavailable_reset(self):
        trigger=Trigger(1.,2)
        self.assertFalse(trigger.update(2.,True)); self.assertTrue(trigger.update(2.,True))
        self.assertIsNone(trigger.update(2.,False)); self.assertFalse(trigger.update(2.,True))
        self.assertFalse(trigger.update(.5,True))


if __name__=='__main__': unittest.main()
