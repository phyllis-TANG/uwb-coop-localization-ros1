#!/usr/bin/env python3
"""Monitoring only: raw one-step innovations and independent anchor exclusions.

No truth, fault labels, thresholds selected from test data, automatic exclusion,
or probability/protection-level interpretation. The full locator is untouched.
"""
from __future__ import annotations
import copy
import hashlib
import json
import math
import time
import numpy as np
from single_car_fixed_lag import FixedLagReplay, WindowGraph, Objective, initial_prior
from single_car_sequential_replay import antenna, predict


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def range_residuals(model, pose, observations):
    xy = antenna(pose, model['base_to_antenna_body_xy_m'])
    rows = []
    sigma = model['graph_parameters']['range_sigma_m']
    for key, raw in sorted(observations.items()):
        corrected = raw-model['range_bias_m'][key]
        predicted = float(np.linalg.norm(np.r_[xy, model['antenna_height_m']]-model['anchors_xyz_m'][key]))
        residual = predicted-corrected
        z = residual/sigma
        s = math.sqrt(1+z*z)
        rows.append(dict(anchor=key, raw_median_m=raw, corrected_median_m=corrected,
                         predicted_range_m=predicted, raw_residual_m=residual,
                         normalized_raw_residual=z,
                         pseudo_huber_transformed_residual=z*math.sqrt(2/(s+1)),
                         irls_weight=1/s, irls_weighted_residual=z/math.sqrt(s)))
    return rows


def numerical_rank(matrix, rtol=1e-8):
    s = np.linalg.svd(matrix, compute_uv=False)
    if not len(s) or s[0] <= 0:
        return 0, None
    rank = int(np.sum(s > s[0]*rtol))
    condition = float(s[0]/s[-1]) if s[-1] > 0 else None
    return rank, condition


def graph_validity(graph, result, observations, rules):
    reasons = []
    if not result.get('accepted_graph'):
        reasons.append(result.get('status', 'no_graph'))
    if len(observations) < 3:
        reasons.append('insufficient_current_anchor_redundancy')
    rank, condition = 0, None
    jrank, jcondition = None, None
    if result.get('pose') is not None and observations:
        xy = antenna(result['pose'], graph.model['base_to_antenna_body_xy_m'])
        refs = np.array([graph.model['anchors_xyz_m'][k] for k in sorted(observations)])
        delta = xy-refs[:, :2]
        distances = np.sqrt(np.sum(delta**2, axis=1)+(graph.model['antenna_height_m']-refs[:, 2])**2)
        rank, condition = numerical_rank(delta/distances[:, None], rules.get('rank_rtol', 1e-8))
    if rank != 2 or condition is None or condition > rules.get('condition_limit', 1e8):
        reasons.append('invalid_current_xy_geometry')
    if result.get('accepted_graph'):
        objective = Objective(graph.times, graph.local, graph.observations, graph.model, graph.prior)
        jac = objective.jac(np.asarray(graph.states).ravel())
        jrank, jcondition = numerical_rank(jac, rules.get('rank_rtol', 1e-8))
        if jrank != jac.shape[1] or jcondition is None or jcondition > rules.get('condition_limit', 1e8):
            reasons.append('invalid_graph_rank_or_condition')
    return dict(available=not reasons, reasons=reasons, current_anchor_count=len(observations),
                xy_rank=rank, xy_condition=condition, graph_jacobian_rank=jrank,
                graph_jacobian_condition=jcondition)


class Trigger:
    def __init__(self, threshold, consecutive=2):
        self.threshold, self.consecutive, self.count = threshold, consecutive, 0

    def update(self, statistic, available):
        if not available or statistic is None or self.threshold is None:
            self.count = 0
            return None
        self.count = self.count+1 if statistic > self.threshold else 0
        return bool(self.count >= self.consecutive)


class IntegrityReplay:
    """Full locator plus four persistent independent WindowGraph instances.

    Only immutable frontend medians/Odom are shared. Each exclusion graph starts
    at initial_prior(model), and never receives its excluded anchor at any time.
    Full-estimator failures poison monitoring rather than inventing confidence.
    """
    def __init__(self, config, on_output, thresholds=None):
        self.config = copy.deepcopy(config)
        self.model = self.config['model']
        self.rules = self.config['monitor_rules']
        self.on_output = on_output
        options = dict(lag_s=config['lag_s'], max_nfev=config['max_nfev'])
        self.full = FixedLagReplay(self.model, config['replay'], self._output,
                                   max_sensor_samples=config['max_sensor_samples'], **options)
        self.hypotheses = {k: WindowGraph(self.model, **options) for k in sorted(self.model['anchors_xyz_m'])}
        self.poisoned, self.lineage, self.seen_anchors = {}, {}, {}
        for k in self.hypotheses:
            self.lineage[k] = digest(dict(initial_point=self.hypotheses[k].prior.point.tolist(), excluded=k))
            self.seen_anchors[k] = set()
        thresholds = thresholds or {}
        self.triggers = {k: Trigger(thresholds.get(k), self.rules['consecutive_exceedances']) for k in ('M1','M2')}
        self.previous_pose = self.previous_local = None
        self.current_event_received_s = 0.
        self.event_start_perf = self.virtual_start = self.virtual_finish = 0.
        self.started_perf = time.perf_counter()
        self.monitored_outputs = 0

    def _stamp(self):
        return self.virtual_start+(time.perf_counter()-self.event_start_perf)

    def ingest(self, event):
        self.current_event_received_s = event.received_s
        self.virtual_start = max(event.received_s, self.virtual_finish)
        self.event_start_perf = time.perf_counter()
        self.full.ingest(event)
        self.virtual_finish = self._stamp()

    def finish(self):
        if not np.isfinite(self.full.now):
            return
        self.current_event_received_s = self.full.now
        self.virtual_start = max(self.full.now, self.virtual_finish)
        self.event_start_perf = time.perf_counter()
        self.full.finish()
        self.virtual_finish = self._stamp()

    def _output(self, row):
        row['trigger_receipt_s'] = self.current_event_received_s
        row['modeled_event_queue_s'] = self.virtual_start-self.current_event_received_s
        row['M0_available_receipt_s'] = self._stamp()
        m1start = time.perf_counter()
        obs = row.get('range_medians_m', {})
        local = row.get('local_odom')
        prefit, postfit, active = [], [], []
        validity = dict(available=False, reasons=['missing_odom_bracket'])
        if row['pose'] is not None:
            predicted = initial_prior(self.model).point if self.previous_pose is None else predict(
                self.previous_pose, self.previous_local, np.asarray(local))
            prefit = range_residuals(self.model, predicted, obs)
            postfit = range_residuals(self.model, row['pose'], obs)
            validity = graph_validity(self.full.graph, row, obs, self.rules)
            for t,p,o in zip(self.full.graph.times,self.full.graph.states,self.full.graph.observations):
                active.extend([dict(state_time_s=t, **r) for r in range_residuals(self.model,p,o)])
            self.previous_pose, self.previous_local = np.array(row['pose']), np.array(local)
        s1 = max((abs(r['normalized_raw_residual']) for r in prefit), default=None)
        a1 = self.triggers['M1'].update(s1,validity['available'])
        row['M1'] = dict(statistic=s1, alarm=a1, threshold=self.triggers['M1'].threshold,
                         consecutive_count=self.triggers['M1'].count, **validity)
        row['prefit_current_residuals'] = prefit
        row['postfit_current_residuals'] = postfit
        row['postfit_active_window_residuals'] = active
        row['M1_extra_wall_s'] = time.perf_counter()-m1start
        row['M1_available_receipt_s'] = self._stamp()
        m2start = time.perf_counter()
        hypotheses = {}
        for excluded, graph in self.hypotheses.items():
            retained = {k:v for k,v in obs.items() if k != excluded}
            result = dict(pose=None,accepted_graph=False,status='missing_odom_bracket')
            started = time.perf_counter()
            if excluded in self.poisoned:
                result['status'] = 'latched_hypothesis_error'
                result['error'] = self.poisoned[excluded]
            elif row['pose'] is not None:
                try:
                    result = graph.update(row['state_time_s'], local, retained)
                    self.seen_anchors[excluded].update(retained)
                    self.lineage[excluded] = digest([self.lineage[excluded],row['state_time_s'],local,retained])
                except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                    self.poisoned[excluded] = str(error)
                    result = dict(pose=None,accepted_graph=False,status='hypothesis_error',error=str(error))
            checked = graph_validity(graph,result,retained,self.rules)
            distance = None
            if result['pose'] is not None and row['pose'] is not None:
                distance = float(np.linalg.norm(antenna(result['pose'], self.model['base_to_antenna_body_xy_m'])-row['antenna_xy_m']))
            hypotheses[excluded] = dict(result, **checked, excluded_anchor=excluded,
                separation_m=distance, wall_s=time.perf_counter()-started,
                prior_lineage_sha256=self.lineage[excluded], source_anchor_ids=sorted(self.seen_anchors[excluded]),
                excluded_observations_ever_ingested=0)
            if excluded in self.seen_anchors[excluded] or any(excluded in o for o in graph.observations):
                raise AssertionError('Excluded anchor contaminated its hypothesis')
        ok = validity['available'] and all(h['available'] for h in hypotheses.values())
        s2 = max((h['separation_m'] for h in hypotheses.values() if h['separation_m'] is not None),default=None)
        a2 = self.triggers['M2'].update(s2,ok)
        reasons = ([] if validity['available'] else ['full_graph_invalid']) + [k+':'+','.join(h['reasons']) for k,h in hypotheses.items() if not h['available']]
        row['M2'] = dict(statistic=s2,alarm=a2,available=ok,reasons=reasons,
                         threshold=self.triggers['M2'].threshold,consecutive_count=self.triggers['M2'].count)
        row['exclusion_hypotheses'] = hypotheses
        row['M2_extra_wall_s'] = time.perf_counter()-m2start
        row['M2_available_receipt_s'] = self._stamp()
        row['unpaced_actual_output_elapsed_s'] = time.perf_counter()-self.started_perf
        row['M1']['conclusion'] = 'unavailable' if not validity['available'] else ('unconfigured' if a1 is None else ('alarm' if a1 else 'no_threshold_alarm'))
        row['M2']['conclusion'] = 'unavailable' if not ok else ('unconfigured' if a2 is None else ('alarm' if a2 else 'no_threshold_alarm'))
        self.monitored_outputs += 1
        self.on_output(row)
