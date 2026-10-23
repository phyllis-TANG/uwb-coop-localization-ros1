#!/usr/bin/env python3
"""Omitted-link prediction instruments and lagged consistency weights.

These EKFs are diagnostic instruments, not the reported factor-graph estimator.
No checked range or final graph estimate feeds into its own prediction.
"""
import copy
import math
import time

import numpy as np
from scipy.optimize import least_squares

from single_car_fixed_lag import initial_prior
from single_car_sequential_replay import rotation, wrap
from two_car_updated_comparison import CARS
from two_car_stationary_confidence import PolicyObjective


def range_prediction(state, covariance, model, anchor):
    arm = rotation(state[2])@np.asarray(model['base_to_antenna_body_xy_m'])
    delta = state[:2]+arm-np.asarray(anchor)[:2]
    dz = model['antenna_height_m']-anchor[2]
    distance = float(np.sqrt(delta@delta+dz*dz))
    if distance <= 1e-12: raise ValueError('Degenerate range geometry')
    h = np.r_[delta/distance, (delta@np.array([-arm[1], arm[0]]))/distance]
    variance = max(0., float(h@covariance@h))
    return distance, variance, h


class PredictionFilter:
    def __init__(self, model):
        self.model = copy.deepcopy(model)
        prior = initial_prior(model)
        self.state = prior.point.copy()
        inverse = np.linalg.inv(prior.matrix)
        self.covariance = inverse@inverse.T

    def propagate(self, previous_local, local, dt):
        if dt <= 0: raise ValueError('Nonpositive filter timestep')
        measured = rotation(-previous_local[2])@(local[:2]-previous_local[:2])
        delta = rotation(self.state[2])@measured
        a = np.eye(3); a[:2, 2] = [-delta[1], delta[0]]
        self.state[:2] += delta
        self.state[2] = wrap(self.state[2]+wrap(local[2]-previous_local[2]))
        p = self.model['graph_parameters']
        q = np.diag([p['odom_translation_sigma_m']**2*dt]*2+
                    [math.radians(p['odom_yaw_sigma_deg'])**2*dt])
        self.covariance = a@self.covariance@a.T+q

    def update_other_walls(self, observations, omitted=None):
        model = self.model
        for key, raw in sorted(observations.items()):
            if key == omitted: continue
            predicted, variance, h = range_prediction(self.state, self.covariance,
                                                       model, model['anchors_xyz_m'][key])
            innovation = raw-model['range_bias_m'][key]-predicted
            r = model['graph_parameters']['range_sigma_m']**2
            robust_r = r*np.sqrt(1+innovation**2/(variance+r))
            gain = self.covariance@h/(variance+robust_r)
            self.state += gain*innovation
            self.state[2] = wrap(self.state[2])
            a = np.eye(3)-np.outer(gain, h)
            self.covariance = a@self.covariance@a.T+robust_r*np.outer(gain, gain)
            self.covariance = .5*(self.covariance+self.covariance.T)


def lagged_weight(history, policy):
    n = policy['history_bins']
    values = history[-n:]
    if len(values) < policy['minimum_valid_history'] or any(v is None for v in values):
        return 1.
    z = float(np.median(np.abs(values)))
    threshold = policy['threshold_abs_z']
    return float(np.clip((threshold/max(threshold, z))**2, policy['minimum_weight'], 1.))


def predict_confidence(inputs, policy):
    times = np.asarray(inputs['times'])
    keys = {c: sorted(inputs['cars'][c]['model']['anchors_xyz_m']) for c in CARS}
    omitted = {c: {k: PredictionFilter(inputs['cars'][c]['model']) for k in keys[c]} for c in CARS}
    all_wall = {c: PredictionFilter(inputs['cars'][c]['model']) for c in CARS}
    history = {c+'/'+k: [] for c in CARS for k in keys[c]}; history['peer'] = []
    series = {k: [] for k in history}
    for i, stamp in enumerate(times):
        for car in CARS:
            data = inputs['cars'][car]; model = data['model']
            for key, instrument in list(omitted[car].items())+[(None, all_wall[car])]:
                if i:
                    instrument.propagate(data['local'][i-1], data['local'][i], times[i]-times[i-1])
                instrument.update_other_walls(data['observations'][i], omitted=key)
                if key is None: continue
                predicted, variance, _ = range_prediction(instrument.state, instrument.covariance,
                                                          model, model['anchors_xyz_m'][key])
                sigma = float(np.sqrt(variance+model['graph_parameters']['range_sigma_m']**2))
                raw = data['observations'][i].get(key)
                corrected = raw-model['range_bias_m'][key] if raw is not None else None
                score = (predicted-corrected)/sigma if corrected is not None else None
                name = car+'/'+key
                series[name].append(dict(epoch=i, elapsed_s=float(stamp), predicted_m=predicted,
                    prediction_sd_with_measurement_m=sigma, measured_corrected_m=corrected,
                    signed_z=score, weight=lagged_weight(history[name], policy)))
                history[name].append(score)
        a, b = [all_wall[c] for c in CARS]
        ant, arm_derivative = [], []
        for f in [a, b]:
            arm = rotation(f.state[2])@np.asarray(f.model['base_to_antenna_body_xy_m'])
            ant.append(f.state[:2]+arm); arm_derivative.append(np.array([-arm[1], arm[0]]))
        delta = ant[0]-ant[1]
        dz = a.model['antenna_height_m']-b.model['antenna_height_m']
        distance = float(np.sqrt(delta@delta+dz*dz))
        if distance <= 1e-12: raise ValueError('Degenerate peer geometry')
        unit = delta/distance
        h = [np.r_[unit, unit@arm_derivative[0]], -np.r_[unit, unit@arm_derivative[1]]]
        variance = sum(float(v@f.covariance@v) for v, f in zip(h, [a, b]))
        sigma = float(np.sqrt(max(0., variance)+inputs['peer_sigma_m']**2))
        measurement = inputs['peers'][i]['range_m']
        score = (distance-measurement)/sigma if measurement is not None else None
        series['peer'].append(dict(epoch=i, elapsed_s=float(stamp), predicted_m=distance,
            prediction_sd_with_measurement_m=sigma, measured_corrected_m=measurement,
            signed_z=score, weight=lagged_weight(history['peer'], policy)))
        history['peer'].append(score)
    return series


class AdaptiveObjective(PolicyObjective):
    def __init__(self, inputs, joint, stationary, masks, fixed_scales, detector, confidence):
        super().__init__(inputs, joint, dict(stationary_covariance=stationary,
            range_confidence=False), masks, fixed_scales, detector)
        for car, part in zip(CARS, self.parts):
            base = inputs['cars'][car]['model']['graph_parameters']['range_sigma_m']
            part.sigma_range = np.asarray([base/np.sqrt(confidence[car+'/'+key][i]['weight'])
                for i, row in enumerate(inputs['cars'][car]['observations']) for key in sorted(row)])
        self.inputs['peer_sigma_m'] = np.asarray([inputs['peer_sigma_m']/np.sqrt(
            confidence['peer'][i]['weight']) for i in self.peer_indices])


def solve_objective(inputs, objective, optimizer):
    initial = np.stack([inputs['cars'][c]['initial'] for c in CARS])
    start, cpu = time.perf_counter(), time.process_time()
    fit = least_squares(objective.fun, initial.ravel(), jac=objective.jac,
        method='trf', tr_solver='exact', loss='linear', max_nfev=optimizer['max_nfev'],
        ftol=optimizer['ftol'], xtol=optimizer['xtol'], gtol=optimizer['gtol'])
    wall_s, cpu_s = time.perf_counter()-start, time.process_time()-cpu
    if not fit.success or not np.isfinite(fit.x).all():
        raise RuntimeError('Unaccepted optimization: '+str(fit.message))
    states = fit.x.reshape(2, len(inputs['times']), 3)
    antenna = np.asarray([states[ci, :, :2]+np.asarray([rotation(th)@np.asarray(
        inputs['cars'][car]['model']['base_to_antenna_body_xy_m']) for th in states[ci, :, 2]])
        for ci, car in enumerate(CARS)])
    return dict(states=states, antenna_xy=antenna,
        wall_factor_count=objective.wall_factor_count, peer_factor_count=len(objective.peer_indices),
        optimizer=dict(success=bool(fit.success), status=int(fit.status), message=str(fit.message),
            nfev=int(fit.nfev), njev=int(fit.njev), cost=float(fit.cost), optimality=float(fit.optimality),
            solve_wall_s=wall_s, solve_cpu_s=cpu_s))
