#!/usr/bin/env python3
"""Independent residual, Jacobian, elimination, causality and bounded-work checks."""
import copy
import math
import unittest
from unittest.mock import patch
import numpy as np
from single_car_sequential_replay import Event, load_solver, rotation
from single_car_fixed_lag import (BoundaryPrior, Objective, WindowGraph, FixedLagReplay,
                                  eliminate_oldest, initial_prior)
from test_single_car_sequential_replay import MODEL, POLICY, synthetic_events, run as reference_run


def problem(n=4):
    model = copy.deepcopy(MODEL)
    model['initial_heading_deg'] = 12.
    model['base_to_antenna_body_xy_m'] = [.12, -.08]
    times = np.arange(n, dtype=float)
    local = np.array([[.12*t, .03*t*t, .08*t] for t in times])
    prior = initial_prior(model)
    heading = math.radians(model['initial_heading_deg'])
    states = np.column_stack((local[:, :2]@rotation(heading).T+prior.point[:2],
                              local[:, 2]+heading))
    observations = []
    for i,p in enumerate(states):
        xy = p[:2]+rotation(p[2])@np.asarray(model['base_to_antenna_body_xy_m'])
        row = {key: float(np.linalg.norm(np.r_[xy,.2]-xyz))+.07*math.sin(i+k)
               for k,(key,xyz) in enumerate(sorted(model['anchors_xyz_m'].items()))}
        observations.append(row)
    # Include a large robust residual; do not limit Jacobian checks to inliers.
    observations[2]['a'] += 1.2
    states += np.random.default_rng(17).normal(scale=.02, size=states.shape)
    return model,times,local,observations,states,prior


def run_front(events, lag=20., max_nfev=50):
    rows = []
    replay = FixedLagReplay(MODEL,POLICY,rows.append,lag_s=lag,max_nfev=max_nfev)
    for e in events:
        replay.ingest(e)
    replay.finish()
    return replay,rows


def stable(rows):
    return [(r['state_time_s'],r['availability_cutoff_s'],r['status'],r['pose'],
             r.get('range_medians_m'),r.get('range_sample_counts')) for r in rows]


class FixedLagTests(unittest.TestCase):
    def test_residual_matches_captured_unmodified_legacy_objective(self):
        model,t,local,obs,states,prior = problem()
        legacy = load_solver()
        captured = {}
        class Captured(Exception):
            pass
        def intercept(fun,initial,**kwargs):
            captured['fun']=fun
            raise Captured()
        with patch.object(legacy,'least_squares',intercept):
            with self.assertRaises(Captured):
                legacy.optimize_graph(local,obs,model['anchors_xyz_m'],model['range_bias_m'],
                    .2,prior.point[:2],prior.point[2],t,model['graph_parameters'],
                    tag_to_base_lever_xy_m=model['base_to_antenna_body_xy_m'])
        actual = Objective(t,local,obs,model,prior).fun(states.ravel())
        expected = captured['fun'](states.ravel())
        np.testing.assert_allclose(actual,expected,atol=2e-13,rtol=1e-13)

    def test_analytic_jacobians_match_central_differences_for_both_priors(self):
        model,t,local,obs,states,prior = problem()
        carried = BoundaryPrior(states[0]+[.01,-.02,.03],
                                [[4.,.3,-.2],[0.,3.,.7],[0.,0.,8.]], [.2,-.3,.1])
        for p in [prior,carried]:
            objective = Objective(t,local,obs,model,p)
            x=states.ravel();step=1e-6
            numeric=np.column_stack([(objective.fun(x+np.eye(len(x))[i]*step)
                                      -objective.fun(x-np.eye(len(x))[i]*step))/(2*step)
                                     for i in range(len(x))])
            np.testing.assert_allclose(objective.jac(x),numeric,atol=2e-6,rtol=2e-6)

    def test_square_root_prior_matches_full_schur_without_double_counting(self):
        model,t,local,obs,states,prior=problem()
        old=Objective(t,local,obs,model,prior)
        residual,jac=old.evaluate(states.ravel())
        new_prior,constant=eliminate_oldest(states,t,local,obs,model,prior)
        retained=Objective(t[1:],local[1:],obs[1:],model,new_prior)
        r2,j2=retained.evaluate(states[1:].ravel())
        h=jac.T@jac;g=jac.T@residual
        schur=h[3:,3:]-h[3:,:3]@np.linalg.solve(h[:3,:3],h[:3,3:])
        gradient=g[3:]-h[3:,:3]@np.linalg.solve(h[:3,:3],g[:3])
        np.testing.assert_allclose(j2.T@j2,schur,atol=4e-10,rtol=2e-11)
        np.testing.assert_allclose(j2.T@r2,gradient,atol=2e-10,rtol=2e-11)
        self.assertGreater(np.linalg.norm(new_prior.offset),1e-4)
        rng=np.random.default_rng(21)
        for _ in range(5):
            delta=rng.normal(scale=.01,size=3*(len(t)-1))
            old_delta=np.linalg.lstsq(jac[:,:3],-residual-jac[:,3:]@delta,rcond=None)[0]
            full_cost=np.linalg.norm(residual+jac[:,:3]@old_delta+jac[:,3:]@delta)**2
            carried_cost=np.linalg.norm(r2+j2@delta)**2+constant
            self.assertAlmostEqual(full_cost,carried_cost,places=9)

    def test_boundary_covariance_grows_under_pure_odom_instead_of_resetting(self):
        graph=WindowGraph(MODEL,lag_s=20.)
        for t in range(100):
            result=graph.update(t,np.zeros(3),{})
        self.assertEqual(graph.marginalizations,79)
        self.assertEqual(len(graph.states),21)
        covariance=np.linalg.inv(graph.prior.matrix.T@graph.prior.matrix)
        expected=[.2**2+79*.03**2,.2**2+79*.03**2,
                  math.radians(5)**2+79*math.radians(2)**2]
        np.testing.assert_allclose(covariance,np.diag(expected),atol=2e-12,rtol=1e-11)
        self.assertEqual(result['status'],'graph_no_current_ranges')
        self.assertLessEqual(graph.peak_solve_states,21)
        self.assertLessEqual(graph.peak_transient_states,22)

    def test_identical_before_first_marginalization(self):
        model,t,local,obs,_,_=problem(15)
        fixed=WindowGraph(model,20.);growing=WindowGraph(model,None)
        for a,b,c in zip(t,local,obs):
            x=fixed.update(a,b,c);y=growing.update(a,b,c)
            np.testing.assert_array_equal(x['pose'],y['pose'])
        self.assertEqual(fixed.marginalizations,0)

    def test_exact_nonlinear_motion_remains_exact_after_elimination(self):
        model=copy.deepcopy(MODEL);model['base_to_antenna_body_xy_m']=[.12,-.08]
        model['start_antenna_xyz_m']=[.12,-.08,.2]
        graph=WindowGraph(model,20.)
        for t in range(50):
            p=np.array([.03*t,.002*t*t,.01*t])
            xy=p[:2]+rotation(p[2])@np.asarray(model['base_to_antenna_body_xy_m'])
            obs={key:float(np.linalg.norm(np.r_[xy,.2]-xyz))
                 for key,xyz in model['anchors_xyz_m'].items()}
            result=graph.update(t,p,obs)
            np.testing.assert_allclose(result['pose'],p,atol=2e-10,rtol=0.)
        self.assertEqual(graph.marginalizations,29)

    def test_frontend_matches_legacy_inputs_and_deadlines(self):
        events=synthetic_events(10.)
        reference=reference_run(events).records
        _,rows=run_front(events)
        for old,new in zip(reference,rows):
            for key in ['state_time_s','availability_cutoff_s','range_medians_m','range_sample_counts']:
                self.assertEqual(old.get(key),new.get(key))
        self.assertEqual(len(reference),len(rows))

    def test_pruned_odom_buffer_preserves_heading_unwrap_across_pi(self):
        events=[]
        for e in synthetic_events(10.):
            if e.kind=='odom':
                angle=3.+.1*e.header_s
                e=Event(e.received_s,e.kind,e.header_s,(0.,0.,math.atan2(math.sin(angle),math.cos(angle))))
            events.append(e)
        reference=reference_run(events).records
        replay,rows=run_front(events)
        for old,new in zip(reference,rows):
            np.testing.assert_allclose(new['local_odom'],old['local_odom'],atol=1e-14,rtol=0.)
        self.assertLessEqual(len(replay.odom),25)

    def test_future_mutation_and_truncation_after_marginalization(self):
        events=synthetic_events(35.)
        _,complete=run_front(events)
        changed=[Event(e.received_s,e.kind,e.header_s,
                       {key:value+.1 for key,value in e.value.items()})
                 if e.kind=='uwb' and e.received_s>30. else e for e in events]
        _,mutated=run_front(changed)
        past=lambda rows:[r for r in rows if r['availability_cutoff_s']<=30.]
        self.assertEqual(stable(past(complete)),stable(past(mutated)))
        self.assertNotEqual(complete[-1]['pose'],mutated[-1]['pose'])
        truncated=[e for e in events if e.received_s<=30.]+[Event(30.,'clock')]
        _,short=run_front(truncated)
        self.assertEqual(stable(past(complete)),stable(short))
        self.assertGreater(complete[-1]['marginalizations'],0)

    def test_long_running_estimator_has_no_internal_output_history(self):
        count=[0]
        def sink(record):
            count[0]+=1
        replay=FixedLagReplay(MODEL,POLICY,sink,lag_s=20.)
        for event in synthetic_events(120.):
            replay.ingest(event)
        replay.finish()
        self.assertEqual(count[0],119)
        self.assertLessEqual(len(replay.graph.states),21)
        self.assertLessEqual(replay.graph.peak_transient_states,22)
        self.assertLessEqual(max(replay.sensor_peaks.values()),60)
        self.assertFalse(hasattr(replay,'_records'))
        self.assertTrue(all(len(x)<=512 for x in [replay.odom,replay.ranges]))

    def test_missing_bracket_is_not_extrapolated_and_eof_is_not_extended(self):
        rows=[];replay=FixedLagReplay(MODEL,POLICY,rows.append)
        for e in [Event(0.,'odom',0.,(0.,0.,0.)),Event(.01,'uwb',0.,{'a':2.}),Event(2.1,'clock')]:
            replay.ingest(e)
        replay.finish()
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'missing_odom_bracket')
        self.assertIsNone(rows[0]['pose'])

    def test_equal_deadline_and_late_closed_bin(self):
        rows=[];policy=dict(POLICY,minimum_samples_per_link=1)
        replay=FixedLagReplay(MODEL,policy,rows.append)
        for e in [Event(0.,'odom',0.,(0.,0.,0.)),Event(.01,'uwb',0.,{'a':2.}),
                  Event(.8,'uwb',.7,{'a':2.}),Event(1.9,'odom',2.,(0.,0.,0.)),
                  Event(2.,'uwb',1.2,{'a':4.}),Event(2.1,'clock')]:
            replay.ingest(e)
        saved=copy.deepcopy(rows[0])
        replay.ingest(Event(2.4,'uwb',1.3,{'a':100.}));replay.finish()
        self.assertEqual(rows[0],saved)
        self.assertEqual(saved['range_medians_m']['a'],3.)
        self.assertEqual(replay.counters['late_packets_for_closed_bins'],1)

    def test_bootstrap_buffer_overflow_and_keyframe_spacing_are_explicit(self):
        replay=FixedLagReplay(MODEL,POLICY,lambda r:None,max_sensor_samples=4)
        for i in range(4):
            replay.ingest(Event(i*.1,'odom',i*.1,(0.,0.,0.)))
        with self.assertRaises(BufferError):
            replay.ingest(Event(.4,'odom',.4,(0.,0.,0.)))
        graph=WindowGraph(MODEL,20.)
        graph.update(0.,np.zeros(3),{})
        with self.assertRaisesRegex(ValueError,'spacing'):
            graph.update(.5,np.zeros(3),{})

    def test_iteration_budget_failure_is_not_accepted(self):
        graph=WindowGraph(MODEL,20.,max_nfev=1)
        observations={key:float(np.linalg.norm(np.array([0.,0.,.2])-xyz))+.2
                      for key,xyz in MODEL['anchors_xyz_m'].items()}
        for t in range(3):
            r=graph.update(t,np.zeros(3),observations)
        self.assertFalse(r['accepted_graph'])
        self.assertEqual(r['status'],'predict_only_solver_failed')
        np.testing.assert_array_equal(r['pose'],np.zeros(3))

    def test_rank_failure_is_not_replaced_by_an_invented_prior(self):
        empty=BoundaryPrior(np.zeros(3),np.zeros((3,3)),np.zeros(3))
        for states in [np.zeros((2,3)),np.array([[0.,0.,.37],[.2,-.1,.52]])]:
            with self.assertRaisesRegex(ValueError,'Rank-deficient'):
                eliminate_oldest(states,[0.,1.],states,[{},{}],MODEL,empty)


if __name__=='__main__':
    unittest.main()
