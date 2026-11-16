"""Six-epoch XY diagnostic only. Observations enter solve; truth never does."""
import hashlib
import importlib.util
import json
import time
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('pr97_xy', ROOT/'tools/midterm_simulation_phase1/identifiability.py')
pr97 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr97)
METHODS = ['B0', 'B1', 'B2', 'B3']
PEER = np.arange(8, 54, 9)

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def active(kind):
    mask = np.zeros(54)
    mask[np.arange(0, 54, 9) if kind == 'wall' else PEER] = 1
    return mask

def generate(geometry, motion, kind, bias, profile, seed, cfg):
    anchors, truth = pr97.design(geometry, motion)
    z = np.r_[truth.ravel(), 0.]
    clean, _ = pr97.model(z, anchors, kind)
    movement, _ = pr97.movement(z)
    # Streams have fixed lengths and identities across geometry/link/bias/profile.
    noisy = profile.startswith('noisy')
    rng = [np.random.default_rng(np.random.SeedSequence([seed, k])) for k in range(4)] if noisy else None
    er = rng[0].normal(0, cfg['range_sigma_m'], 54) if noisy else np.zeros(54)
    em = rng[1].normal(0, cfg['motion_sigma_m'], 20) if noisy else np.zeros(20)
    ep = rng[2].normal(0, cfg['position_prior_sigma_m'], 4) if noisy else np.zeros(4)
    init = rng[3].normal(0, cfg['initial_error_sigma_m'], 24) if noisy else np.tile([.1, .1, -.1, .1], 6)
    shift = np.array(cfg['biased_prior_offset_m']) if profile == 'noisy_biased_prior' else np.zeros(4)
    center = truth[0].ravel() + ep + shift
    mv = movement + em
    start = np.vstack([center, center + np.cumsum(mv.reshape(5, 4), axis=0)]).ravel() + init
    obs = dict(anchors=anchors.tolist(), ranges=(clean+er+bias*active(kind)).tolist(),
               movement=mv.tolist(), prior_center=center.tolist(), start=start.tolist(), kind=kind,
               prior_sigma=None if profile == 'noiseless_no_prior' else cfg['position_prior_sigma_m'],
               range_sigma=cfg['range_sigma_m'], motion_sigma=cfg['motion_sigma_m'])
    # Oracle correction is explicitly supplied ONLY to B3; B0/B1/B2 see no labels.
    return obs, truth, (bias*active(kind)), dict(range=er.tolist(), movement=em.tolist(), prior=ep.tolist(), initial=init.tolist())

def problem(obs, method, oracle_correction=None):
    augmented = method == 'B2'
    n = 25 if augmented else 24
    keep = np.ones(54, dtype=bool)
    if method == 'B0': keep[PEER] = False
    anchors = np.array(obs['anchors']); y = np.array(obs['ranges'])
    if method == 'B3':
        if oracle_correction is None: raise ValueError('B3 requires explicit oracle correction')
        y = y - oracle_correction
    target = y[keep]
    prior = np.zeros((4, n)); prior[:, :4] = np.eye(4)
    def evaluate(q):
        z = q if augmented else np.r_[q, 0.]
        v, j = pr97.model(z, anchors, obs['kind'])
        mv, mj = pr97.movement(z)
        r = [(v[keep]-target)/obs['range_sigma'], (mv-np.array(obs['movement']))/obs['motion_sigma']]
        js = [j[keep, :n]/obs['range_sigma'], mj[:, :n]/obs['motion_sigma']]
        if obs['prior_sigma'] is not None:
            r.append((q[:4]-obs['prior_center'])/obs['prior_sigma']); js.append(prior/obs['prior_sigma'])
        return np.concatenate(r), np.vstack(js)
    start = np.r_[obs['start'], 0.] if augmented else np.array(obs['start'])
    # Solver-consumed input receipt deliberately excludes unused peer values for B0.
    receipt = dict(anchors=obs['anchors'], ranges=target.tolist(), movement=obs['movement'],
                   prior_center=obs['prior_center'] if obs['prior_sigma'] is not None else None,
                   prior_sigma=obs['prior_sigma'], range_sigma=obs['range_sigma'], motion_sigma=obs['motion_sigma'],
                   start=start.tolist(), dimension=n)
    return evaluate, start, receipt

def information(j, relative_tol):
    scales = np.r_[np.ones(24), .1] if j.shape[1] == 25 else np.ones(24)
    _, s, vt = np.linalg.svd(j*scales, full_matrices=False)
    rank = int(np.sum(s > s[0]*relative_tol))
    cov = None
    if rank == j.shape[1]:
        inv = (vt.T / s**2) @ vt
        cov = scales[:, None]*inv*scales[None, :]
    return dict(rank=rank, dimension=j.shape[1], singular_values=s.tolist(),
                weakest_direction_scaled=vt[-1].tolist(), covariance=None if cov is None else cov.tolist())

def solve(obs, method, cfg, oracle_correction=None, max_nfev=None):
    fun, start, receipt = problem(obs, method, oracle_correction)
    starttime = time.perf_counter()
    try:
        fit = least_squares(lambda q: fun(q)[0], start, jac=lambda q: fun(q)[1],
                            x_scale=np.r_[np.ones(24), .1] if method=='B2' else np.ones(24),
                            max_nfev=max_nfev or cfg['max_nfev'], ftol=cfg['ftol'], xtol=cfg['xtol'], gtol=cfg['gtol'])
        r, j = fun(fit.x)
        finite = bool(np.all(np.isfinite(fit.x)) and np.all(np.isfinite(r)))
        converged = bool(fit.success and finite and fit.optimality <= cfg['accepted_optimality'])
        posterior = information(j, cfg['rank_relative_tol'])
        data_j = j[:-4] if obs['prior_sigma'] is not None else j
        data_info = information(data_j, cfg['rank_relative_tol'])
        status = 'CONVERGED_FULL_RANK' if converged and posterior['rank']==len(start) else ('CONVERGED_RANK_DEFICIENT' if converged else 'NOT_CONVERGED')
        return dict(method=method, status=status, success=converged, scipy_success=bool(fit.success), scipy_status=int(fit.status), message=fit.message,
                    nfev=fit.nfev, optimality=float(fit.optimality), elapsed_s=time.perf_counter()-starttime,
                    input_sha256=digest(receipt), estimate=fit.x.tolist(), whitened_residual_rms=float(np.sqrt(np.mean(r*r))),
                    residual_sum_squares=float(r@r), data_information=data_info, posterior_information=posterior)
    except Exception as exc:
        return dict(method=method, status='EXCEPTION', success=False, elapsed_s=time.perf_counter()-starttime,
                    input_sha256=digest(receipt), error=repr(exc), estimate=None)
