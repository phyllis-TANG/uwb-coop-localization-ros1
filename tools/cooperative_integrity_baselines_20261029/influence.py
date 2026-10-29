"""First-order shared primitive-noise sensitivities with each graph's own QR history.

This is a monitor of frozen graph outputs, not a second optimizer. It freezes
robust/nonlinear Jacobians and QR linearization choices, not a calibrated
sampling covariance of the complete adaptive nonlinear optimizer.
"""
import math
import numpy as np
from binding import graph, legacy
from monitors import antenna, antenna_jacobian
from common import digest


class Primitives:
    def __init__(self, times=range(1, 64)):
        times = list(times)
        keys = ['initial|'+str(i) for i in range(6)]
        for car in legacy.CARS:
            for left, right in zip(times, times[1:]):
                keys += [f'odom|{car}|{left:g}|{right:g}|{i}' for i in range(3)]
            for t in times:
                keys += [f'wall|{car}|{t:g}|{k}' for k in ('node_10','node_2','node_3','node_8')]
        keys += [f'peer|{t:g}' for t in times]
        self.keys = keys; self.index = {key:i for i,key in enumerate(keys)}
        if len(keys) != len(self.index): raise ValueError('Duplicate noise primitive')


def noise_matrix(obj, states, prior_b, primitives):
    """Exact frozen Objective row order; measurement derivative of robust transform."""
    residual, jac = obj.evaluate(np.asarray(states).ravel())
    b = np.zeros((len(residual), len(primitives.keys)))
    b[:6] = prior_b
    row = 6
    for ci, car in enumerate(legacy.CARS):
        for left, right in zip(obj.times, obj.times[1:]):
            for component in range(3):
                b[row, primitives.index[f'odom|{car}|{left:g}|{right:g}|{component}']] = -1.
                row += 1
        part = obj.parts[ci]
        for k, state_index in enumerate(part.index):
            pose = states[state_index, 3*ci:3*ci+3]
            distance = np.linalg.norm(antenna(pose, obj.config['models'][car])-part.refs[k])
            e = (distance-part.measured[k])/part.sigma_range
            s = math.hypot(1., e)
            # raw noise primitive has original engineering range_sigma (not raw .04).
            key = sorted(obj.config['models'][car]['anchors_xyz_m'])
            # Objective samples are ordered by key within each observation.
            # Recover key by the immutable reference coordinates; anchors are unique.
            candidates = [name for name in key if np.array_equal(part.refs[k], obj.config['models'][car]['anchors_xyz_m'][name])]
            if len(candidates) != 1: raise ValueError('Ambiguous anchor identity')
            col = primitives.index[f'wall|{car}|{obj.times[state_index]:g}|{candidates[0]}']
            b[row, col] = -math.sqrt((s+1)/2)/s
            row += 1
    for state_index, measured in obj.peers:
        distance = np.linalg.norm(antenna(states[state_index, :3], obj.config['models']['car1'])-
                                  antenna(states[state_index, 3:], obj.config['models']['car2']))
        s = math.hypot(1., (distance-measured)/obj.config['peer']['sigma_m'])
        b[row, primitives.index[f'peer|{obj.times[state_index]:g}']] = -math.sqrt((s+1)/2)/s
        row += 1
    if row != len(residual): raise AssertionError('Noise/Jacobian row binding mismatch')
    return b, jac


class Influence:
    def __init__(self, primitives):
        self.primitives = primitives
        self.prior_b = np.zeros((6, len(primitives.keys))); self.prior_b[:, :6] = -np.eye(6)
        self.consumed = set(); self.marginalizations = 0
        self.last_k = None; self.last_rank = None

    def update(self, maintained_graph, result):
        for detail in result['marginalization_details']:
            states = np.asarray(detail['states'])
            prior = graph.JointPrior(**detail['before'])
            obj = graph.Objective(detail['times_s'], detail['local'],
                [detail['old_observations'], {c:{} for c in legacy.CARS}],
                [detail['old_peer_m'], None], maintained_graph.config, prior,
                maintained_graph.peer_enabled)
            b, jac = noise_matrix(obj, states, self.prior_b, self.primitives)
            q, _ = np.linalg.qr(jac[:, :6], mode='complete')
            jp = q[:, 6:].T@jac[:, 6:12]
            q2, matrix = np.linalg.qr(jp, mode='reduced')
            sign = np.where(np.diag(matrix) < 0, -1., 1.)
            np.testing.assert_allclose(sign[:, None]*matrix, detail['after']['matrix'], atol=1e-10)
            next_b = sign[:, None]*(q2.T@q[:, 6:].T@b)
            ids = [f'wall|{car}|{detail["times_s"][0]:g}|{key}'
                   for car in legacy.CARS for key in detail['old_observations'][car]]
            if maintained_graph.peer_enabled and detail['old_peer_m'] is not None:
                ids += [f'peer|{detail["times_s"][0]:g}']
            ids += [f'odom|{car}|{detail["times_s"][0]:g}|{detail["times_s"][1]:g}|{i}'
                    for car in legacy.CARS for i in range(3)]
            if self.consumed & set(ids): raise AssertionError('Double-consumed marginalized primitive')
            self.consumed.update(ids); self.prior_b = next_b; self.marginalizations += 1
        self.last_k = None; self.last_rank = None
        if not result['accepted_graph']: return
        g = maintained_graph
        obj = graph.Objective(g.times, g.local, g.observations, g.peers, g.config, g.prior, g.peer_enabled)
        states = np.asarray(g.states)
        b, jac = noise_matrix(obj, states, self.prior_b, self.primitives)
        rank = np.linalg.matrix_rank(jac); self.last_rank = int(rank)
        if rank != jac.shape[1]: return
        # Stable QR least-squares solve, not inverse covariance of independent solutions.
        q, r = np.linalg.qr(jac, mode='reduced')
        self.last_k = -np.linalg.solve(r, q.T@b)[-6:]
        if not np.isfinite(self.last_k).all(): self.last_k = None

    def antenna_k(self, g, ci):
        if self.last_k is None: return None
        car = legacy.CARS[ci]
        return antenna_jacobian(g.states[-1][3*ci:3*ci+3], g.config['models'][car])@self.last_k[3*ci:3*ci+3]

    def record(self):
        return dict(prior_noise_sha256=digest(self.prior_b.tolist()),
                    prior_noise_columns=[self.primitives.keys[i] for i in np.flatnonzero(np.any(self.prior_b != 0, axis=0))],
                    consumed_ids=sorted(self.consumed), marginalizations=self.marginalizations,
                    graph_rank=self.last_rank)
