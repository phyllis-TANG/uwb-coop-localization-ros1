"""Independent numerical and data-policy checks for the updated dual graph."""
import copy
import math
import unittest
from unittest.mock import patch

import numpy as np

from single_car_fixed_lag import initial_prior
from single_car_sequential_replay import rotation
from two_car_updated_comparison import (
    CARS, JointObjective, build_inputs, fit_static_wall_bias, solve, unique_positive_ranges)

OPT = dict(max_nfev=100, ftol=1e-7, xtol=1e-7, gtol=1e-7)


def fixture(n=5, noisy=True):
    anchors = {'node_10': [3.26, .1, 2.355], 'node_2': [5.28, 5.16, 2.755],
               'node_3': [5.28, 2.86, 2.355], 'node_8': [.1, 2.41, 2.3]}
    params = dict(keyframe_step_s=1., odom_translation_sigma_m=.03, odom_yaw_sigma_deg=2.,
        prior_position_sigma_m=.2, prior_heading_sigma_deg=5., range_sigma_m=.2)
    times, cars, truth = np.arange(1., n+1.), {}, []
    for ci,car in enumerate(CARS):
        start = [1.5,4.,.17] if ci == 0 else [2.,2.,.2]
        heading = 0. if ci == 0 else 90.
        lever = [.08,-.06] if ci == 0 else [.12,-.08]
        bias = {key: .08+.03*k+.2*ci for k,key in enumerate(sorted(anchors))}
        model = dict(anchors_xyz_m=anchors, range_bias_m=bias, start_antenna_xyz_m=start,
            initial_heading_deg=heading, base_to_antenna_body_xy_m=lever,
            antenna_height_m=start[2], graph_parameters=params)
        t = times-times[0]
        local = np.column_stack((.07*t, .01*t*t, .04*t))
        prior = initial_prior(model)
        states = np.column_stack((local[:, :2]@rotation(math.radians(heading)).T+prior.point[:2],
                                  local[:, 2]+prior.point[2]))
        antennas = states[:, :2]+np.array([rotation(th)@lever for th in states[:, 2]])
        observations = []
        for i,xy in enumerate(antennas):
            row = {key: float(np.linalg.norm(np.r_[xy,start[2]]-xyz))+bias[key]
                   +(.04*math.sin(i+k) if noisy else 0.)
                   for k,(key,xyz) in enumerate(sorted(anchors.items()))}
            observations.append(row)
        cars[car] = dict(model=model, local=local, initial=states, observations=observations)
        truth.append(antennas)
    peer = np.sqrt(np.sum((truth[0]-truth[1])**2,axis=1)+.03**2)
    peers = [dict(range_m=float(value)+(.2 if noisy and i==2 else 0.),
                  directions_m=[float(value),float(value)], direction_counts=[40,39])
             for i,value in enumerate(peer)]
    return dict(times=times,cars=cars,peers=peers,peer_sigma_m=.2)


class UpdatedTwoCarTests(unittest.TestCase):
    def test_full_analytic_jacobian_matches_central_differences(self):
        inputs = fixture()
        initial = np.stack([inputs['cars'][c]['initial'] for c in CARS])
        x = (initial+np.random.default_rng(31).normal(scale=.03,size=initial.shape)).ravel()
        for joint in [False,True]:
            for antenna_prior in [False,True]:
                objective = JointObjective(inputs,joint,antenna_prior=antenna_prior)
                step=1e-6
                numeric=np.column_stack([(objective.fun(x+np.eye(len(x))[i]*step)
                                          -objective.fun(x-np.eye(len(x))[i]*step))/(2*step)
                                         for i in range(len(x))])
                np.testing.assert_allclose(objective.jac(x),numeric,atol=3e-6,rtol=3e-6)

    def test_antenna_prior_compatibility_matches_captured_legacy_residual(self):
        import two_car_offline_graph as old
        inputs=fixture()
        # The archived backend has no Car1 correction option; feed corrected
        # Car1 measurements explicitly for this residual-identity check only.
        car=inputs['cars']['car1'];bias=car['model']['range_bias_m']
        car['observations']=[{k:v-bias[k] for k,v in row.items()} for row in car['observations']]
        car['model']['range_bias_m']={key:0. for key in bias}
        legacy=dict(times=inputs['times'],anchors=car['model']['anchors_xyz_m'],
            parameters=dict(odom_translation_sigma_m=.03,odom_yaw_sigma_deg=2.,
                prior_position_sigma_m=.2,prior_heading_sigma_deg=5.,wall_sigma_m=.2,peer_sigma_m=.2),
            scenario=dict(run='L',wall_bias_car2_m=inputs['cars']['car2']['model']['range_bias_m']),
            cars={c:dict(local=x['local'],initial=x['initial'],walls=x['observations'],
                    heading=math.radians(x['model']['initial_heading_deg']),
                    lever=x['model']['base_to_antenna_body_xy_m']) for c,x in inputs['cars'].items()},
            peers=inputs['peers'])
        captured={}
        class Captured(Exception):pass
        def intercept(fun,initial,**kwargs):
            captured['fun']=fun
            raise Captured()
        for joint in [False,True]:
            with patch.object(old,'least_squares',intercept):
                with self.assertRaises(Captured):old.graph(legacy,joint)
            objective=JointObjective(inputs,joint,antenna_prior=True)
            x=np.stack([inputs['cars'][c]['initial'] for c in CARS])
            x+=np.random.default_rng(19).normal(scale=.02,size=x.shape)
            actual=objective.fun(x.ravel())
            a=3*objective.n+len(objective.parts[0].index)
            b=3*objective.n+len(objective.parts[1].index)
            r0,r1=actual[:a],actual[a:a+b]
            reordered=np.r_[r0[:3],r1[:3],r0[3:3*objective.n],r1[3:3*objective.n],
                            r0[3*objective.n:],r1[3*objective.n:],actual[a+b:]]
            np.testing.assert_allclose(reordered,captured['fun'](x.ravel()),atol=2e-13,rtol=1e-13)

    def test_peer_information_is_one_factor_per_epoch(self):
        inputs=fixture()
        independent=JointObjective(inputs,False)
        joint=JointObjective(inputs,True)
        self.assertEqual(joint.rows-independent.rows,len(inputs['times']))
        self.assertEqual(joint.wall_factor_count,independent.wall_factor_count)
        x=np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()
        before=independent.fun(x)
        changed=copy.deepcopy(inputs)
        for row in changed['peers']:row['range_m']+=10.
        np.testing.assert_array_equal(JointObjective(changed,False).fun(x),before)
        self.assertGreater(np.linalg.norm(JointObjective(changed,True).fun(x)-joint.fun(x)),1.)

    def test_missing_peer_directions_do_not_create_constraints(self):
        inputs=fixture()
        inputs['peers'][1]['range_m']=None
        self.assertEqual(len(JointObjective(inputs,True).peer_indices),4)
        for row in inputs['peers']:row['range_m']=None
        x=np.stack([inputs['cars'][c]['initial'] for c in CARS]).ravel()
        np.testing.assert_array_equal(JointObjective(inputs,True).fun(x),JointObjective(inputs,False).fun(x))

    def test_exact_nonzero_lever_motion_remains_exact_with_and_without_peer(self):
        inputs=fixture(noisy=False)
        for joint in [False,True]:
            fit=solve(inputs,joint,OPT)
            np.testing.assert_allclose(fit['states'],np.stack([inputs['cars'][c]['initial'] for c in CARS]),atol=1e-10)
            self.assertLess(fit['optimizer']['cost'],1e-20)

    def test_solver_budget_failure_is_not_accepted(self):
        inputs=fixture()
        inputs['cars']['car2']['initial']+=.3
        with self.assertRaisesRegex(RuntimeError,'Unaccepted optimization'):
            solve(inputs,True,dict(OPT,max_nfev=1))

    def test_static_bias_uses_own_car_reference_and_link_median(self):
        anchors={'a':[0.,0.,2.],'b':[4.,0.,2.]}
        reference=[1.,2.,.17]
        expected={k:float(np.linalg.norm(np.asarray(reference)-v)) for k,v in anchors.items()}
        run={'uwb':{'car1':[(i,{k:v+.25+(.01 if i%2 else -.01) for k,v in expected.items()})
                            for i in range(10)]}}
        fit=fit_static_wall_bias(run,'car1',reference,anchors)
        for row in fit.values():self.assertAlmostEqual(row['bias_m'],.25)
        self.assertEqual(fit['a']['samples'],10)

    def test_invalid_and_duplicate_ranges_are_explicitly_excluded(self):
        values,duplicates=unique_positive_ranges([('a',1.),('a',1.1),('b',2.),
            ('c',float('nan')),('d',0.),('e',-1.),('f',float('inf'))])
        self.assertEqual(values,{'b':2.})
        self.assertEqual(duplicates,1)

    def test_input_pairing_corrections_withholding_and_no_extrapolation(self):
        source=fixture(noisy=False)
        anchors=source['cars']['car1']['model']['anchors_xyz_m']
        p=dict(anchors_xyz_m=anchors,graph_parameters=source['cars']['car1']['model']['graph_parameters'],
            mounts={c:dict(lever_xy_m=source['cars'][c]['model']['base_to_antenna_body_xy_m'],
                           height_m=source['cars'][c]['model']['antenna_height_m']) for c in CARS},
            time_association=dict(range_bin_half_width_s=.4,minimum_samples_per_link=5))
        case=dict(start_antenna_xyz_m={c:source['cars'][c]['model']['start_antenna_xyz_m'] for c in CARS},
                  initial_heading_deg={c:source['cars'][c]['model']['initial_heading_deg'] for c in CARS})
        run=dict(duration_s=6.5,odom={},uwb={})
        bias={c:source['cars'][c]['model']['range_bias_m'] for c in CARS}
        for c in CARS:
            initial=source['cars'][c]['initial'][0]
            run['odom'][c]=[(float(t),*initial) for t in np.arange(0.,6.2,.05)]
            values=dict(source['cars'][c]['observations'][0]);values['node_0' if c=='car1' else 'node_1']=2.
            run['uwb'][c]=[(float(t),dict(values)) for t in np.arange(0.,6.2,.05)]
        configuration=dict(correction='per_car',withheld_wall_car=None,car2_peer_shift_s=0.,peer_sigma_m=.2)
        original=copy.deepcopy(run)
        inputs=build_inputs(run,case,p,configuration,bias)
        self.assertEqual(run,original)
        self.assertEqual(len(inputs['times']),5)
        self.assertEqual(len(inputs['peers']),5)
        for c in CARS:
            np.testing.assert_allclose(inputs['cars'][c]['local'],[source['cars'][c]['initial'][0]]*5)
            self.assertEqual(inputs['cars'][c]['observations'][0],source['cars'][c]['observations'][0])
        withheld=build_inputs(run,case,p,dict(configuration,withheld_wall_car='car1'),bias)
        self.assertEqual(withheld['cars']['car1']['observations'],[{}]*5)
        self.assertEqual(withheld['cars']['car2']['observations'],inputs['cars']['car2']['observations'])
        self.assertEqual(withheld['peers'],inputs['peers'])
        run['odom']['car2']=run['odom']['car2'][:50]
        with self.assertRaisesRegex(ValueError,'brackets'):build_inputs(run,case,p,configuration,bias)


if __name__=='__main__':unittest.main()
