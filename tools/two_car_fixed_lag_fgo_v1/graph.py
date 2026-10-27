"""Six variables per keyframe; full joint square-root boundary prior."""
import copy
from dataclasses import dataclass
import math
import time
import numpy as np
from scipy.optimize import least_squares
from legacy import CARS, BoundaryPrior, PoseObjective, initial_prior, predict, antenna


@dataclass
class JointPrior:
    point: np.ndarray
    matrix: np.ndarray
    offset: np.ndarray

    def __post_init__(self):
        self.point = np.asarray(self.point, float).copy()
        self.matrix = np.asarray(self.matrix, float).copy()
        self.offset = np.asarray(self.offset, float).copy()
        if self.point.shape != (6,) or self.matrix.shape != (6, 6) or self.offset.shape != (6,):
            raise ValueError('Invalid joint prior shape')
        if not all(np.isfinite(x).all() for x in (self.point, self.matrix, self.offset)):
            raise ValueError('Nonfinite joint prior')

    def residual(self, state):
        d = np.asarray(state) - self.point
        d[[2, 5]] = np.arctan2(np.sin(d[[2, 5]]), np.cos(d[[2, 5]]))
        return self.matrix @ d + self.offset

    def record(self):
        return dict(point=self.point.tolist(), matrix=self.matrix.tolist(), offset=self.offset.tolist())


def joint_initial(config):
    priors = [initial_prior(config['models'][c]) for c in CARS]
    matrix = np.zeros((6, 6))
    for i, p in enumerate(priors):
        matrix[3*i:3*i+3, 3*i:3*i+3] = p.matrix
    return JointPrior(np.concatenate([p.point for p in priors]), matrix, np.zeros(6))


def peer_residual(state, measured, models, sigma):
    """Signed pseudo-Huber residual and exact d/d[x1,y1,yaw1,x2,y2,yaw2]."""
    if not np.isfinite(measured) or measured <= 0 or sigma <= 0:
        raise ValueError('Invalid peer observation or scale')
    positions, derivatives = [], []
    for i, car in enumerate(CARS):
        m = models[car]; p = state[3*i:3*i+3]
        lx, ly = m['base_to_antenna_body_xy_m']; co, si = np.cos(p[2]), np.sin(p[2])
        positions.append(np.r_[antenna(p, [lx, ly]), m['antenna_height_m']])
        derivatives.append(np.array([-si*lx-co*ly, co*lx-si*ly]))
    d = positions[0] - positions[1]; distance = np.linalg.norm(d)
    if distance <= 1e-12:
        raise ValueError('Degenerate peer antenna distance')
    error = (distance-measured)/sigma; s = math.sqrt(1+error*error)
    residual = error*math.sqrt(2/(s+1))
    derivative = math.sqrt((s+1)/2)/s/sigma
    unit = d[:2]/distance
    jac = derivative*np.r_[unit, unit @ derivatives[0], -unit, -unit @ derivatives[1]]
    return residual, jac


class Objective:
    def __init__(self, times, local, observations, peers, config, prior, peer_enabled=True):
        self.times = np.asarray(times, float); self.n = len(times)
        self.local = np.asarray(local, float)
        if self.local.shape != (self.n, 2, 3) or len(peers) != self.n or len(observations) != self.n:
            raise ValueError('Inconsistent joint graph inputs')
        self.config, self.prior = config, prior
        self.parts = []
        for i, car in enumerate(CARS):
            zero = BoundaryPrior(np.zeros(3), np.zeros((3, 3)), np.zeros(3))
            self.parts.append(PoseObjective(times, self.local[:, i], [o[car] for o in observations], config['models'][car], zero))
        self.peers = [(i, p) for i, p in enumerate(peers) if peer_enabled and p is not None]
        self._x = None

    def evaluate(self, flat):
        flat = np.asarray(flat)
        if self._x is not None and np.array_equal(flat, self._x):
            return self._r, self._j
        states = flat.reshape(self.n, 6)
        residuals = [self.prior.residual(states[0])]
        j0 = np.zeros((6, 6*self.n)); j0[:, :6] = self.prior.matrix
        jacobians = [j0]
        for i, part in enumerate(self.parts):
            cols = (6*np.arange(self.n)[:, None]+np.arange(3*i, 3*i+3)).ravel()
            r, j = part.evaluate(flat[cols])
            expanded = np.zeros((len(r)-3, 6*self.n)); expanded[:, cols] = j[3:]
            residuals.append(r[3:]); jacobians.append(expanded)
        for index, measured in self.peers:
            r, j = peer_residual(states[index], measured, self.config['models'], self.config['peer']['sigma_m'])
            expanded = np.zeros((1, 6*self.n)); expanded[0, 6*index:6*index+6] = j
            residuals.append(np.array([r])); jacobians.append(expanded)
        self._x = flat.copy(); self._r = np.concatenate(residuals); self._j = np.vstack(jacobians)
        return self._r, self._j

    def fun(self, x):
        return self.evaluate(x)[0].copy()

    def jac(self, x):
        return self.evaluate(x)[1].copy()


def incident_system(states, times, local, observations, peers, config, prior, peer_enabled):
    """Only factors touching oldest pair; retained walls/peer are absent."""
    obj = Objective(times[:2], local[:2], [observations[0], {c: {} for c in CARS}],
                    [peers[0], None], config, prior, peer_enabled)
    return obj.evaluate(np.asarray(states[:2]).ravel())


def eliminate_oldest(states, times, local, observations, peers, config, prior, peer_enabled):
    r, j = incident_system(states, times, local, observations, peers, config, prior, peer_enabled)
    old, boundary = j[:, :6], j[:, 6:12]
    rank_old, rank_joint = np.linalg.matrix_rank(old), np.linalg.matrix_rank(j)
    if rank_old != 6 or rank_joint != 12:
        raise ValueError('Rank-deficient joint elimination')
    q, _ = np.linalg.qr(old, mode='complete')
    jp, rp = q[:, 6:].T @ boundary, q[:, 6:].T @ r
    q2, matrix = np.linalg.qr(jp, mode='reduced'); offset = q2.T @ rp
    if matrix.shape != (6, 6) or np.linalg.matrix_rank(matrix) != 6:
        raise ValueError('Rank-deficient joint boundary')
    sign = np.where(np.diag(matrix) < 0, -1., 1.)
    matrix, offset = sign[:, None]*matrix, sign*offset
    constant = max(0., float(rp@rp-offset@offset))
    result = JointPrior(states[1], matrix, offset)
    details = dict(times_s=list(times[:2]), states=np.asarray(states[:2]).tolist(),
                   local=np.asarray(local[:2]).tolist(), old_observations=observations[0], old_peer_m=peers[0],
                   before=prior.record(), after=result.record(), constant=constant,
                   rank_old=int(rank_old), rank_joint=int(rank_joint),
                   cross_information_norm=float(np.linalg.norm((matrix.T@matrix)[:3, 3:])))
    return result, constant, details


class WindowGraph:
    def __init__(self, config, peer_enabled=True):
        self.config = copy.deepcopy(config); self.peer_enabled = peer_enabled
        self.prior = joint_initial(config)
        self.times, self.local, self.observations, self.peers, self.states = [], [], [], [], []
        self.lag_s = config['fixed_lag_s']; self.max_nfev = config['optimizer']['max_nfev']
        self.marginalizations = 0; self.eliminated_constant = 0.
        self.peak_solve_states = self.peak_transient_states = 0

    def update(self, stamp, local, observations, peer):
        local = np.asarray(local, float)
        if local.shape != (2, 3) or not np.isfinite(local).all():
            raise ValueError('Invalid two-car Odom')
        if self.times and stamp-self.times[-1] < 1-1e-9:
            raise ValueError('Invalid joint keyframe spacing')
        guess = self.prior.point.copy() if not self.states else np.concatenate([
            predict(self.states[-1][3*i:3*i+3], self.local[-1][i], local[i]) for i in range(2)])
        # Transaction protects maintained graph if marginalization fails.
        old = (self.times[:], self.local[:], self.observations[:], self.peers[:], self.states[:],
               self.prior, self.marginalizations, self.eliminated_constant)
        self.times.append(float(stamp)); self.local.append(local.copy())
        self.observations.append(copy.deepcopy(observations)); self.peers.append(peer)
        self.states.append(guess.copy())
        self.peak_transient_states = max(self.peak_transient_states, len(self.times))
        started = time.perf_counter(); details = []
        try:
            while self.times[-1]-self.times[0] > self.lag_s+1e-12:
                self.prior, constant, detail = eliminate_oldest(self.states, self.times, self.local,
                    self.observations, self.peers, self.config, self.prior, self.peer_enabled)
                details.append(detail); self.eliminated_constant += constant; self.marginalizations += 1
                for seq in (self.times, self.local, self.observations, self.peers, self.states): del seq[0]
        except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
            (self.times, self.local, self.observations, self.peers, self.states, self.prior,
             self.marginalizations, self.eliminated_constant) = old
            return dict(pose=guess.tolist(), prediction_pose=guess.tolist(), accepted_graph=False,
                status='predict_only_marginal_error', optimizer={'error': str(error)},
                graph_states=len(self.times), marginalizations=self.marginalizations,
                marginal_wall_s=time.perf_counter()-started, solve_wall_s=0., marginalization_details=[],
                graph_time_span_s=self.times[-1]-self.times[0] if self.times else 0.)
        marginal_wall = time.perf_counter()-started; n = len(self.times)
        self.peak_solve_states = max(self.peak_solve_states, n)
        accepted, status, info, candidate = False, 'predict_only_warmup', {}, None
        started = time.perf_counter()
        if n >= 3:
            try:
                objective = Objective(self.times, self.local, self.observations, self.peers,
                                      self.config, self.prior, self.peer_enabled)
                result = least_squares(objective.fun, np.asarray(self.states).ravel(), jac=objective.jac,
                    method='trf', tr_solver='exact', loss='linear', max_nfev=self.max_nfev,
                    ftol=1e-7, xtol=1e-7, gtol=1e-7)
                if np.isfinite(result.x).all(): candidate = result.x.reshape(n, 6)[-1].tolist()
                accepted = bool(result.success and candidate is not None)
                info = dict(success=bool(result.success), status=int(result.status), nfev=int(result.nfev),
                            cost=float(result.cost), optimality=float(result.optimality), message=str(result.message))
                if accepted:
                    self.states = [p.copy() for p in result.x.reshape(n, 6)]; status = 'graph'
                else: status = 'predict_only_solver_failed'
            except (ValueError, FloatingPointError, np.linalg.LinAlgError) as error:
                status = 'predict_only_solver_error'; info = {'error': type(error).__name__+': '+str(error)}
        return dict(pose=self.states[-1].tolist(), prediction_pose=guess.tolist(), candidate_pose=candidate,
            accepted_graph=accepted, status=status, optimizer=info, graph_states=n,
            graph_time_span_s=self.times[-1]-self.times[0], marginalizations=self.marginalizations,
            marginal_wall_s=marginal_wall, solve_wall_s=time.perf_counter()-started,
            prior=self.prior.record(), marginalization_details=details)

    def snapshot(self):
        return dict(times_s=self.times, local=np.asarray(self.local).tolist(), observations=self.observations,
                    peers_m=self.peers, states=np.asarray(self.states).tolist(), prior=self.prior.record(),
                    eliminated_constant=self.eliminated_constant, peer_enabled=self.peer_enabled)
