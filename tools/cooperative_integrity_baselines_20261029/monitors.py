"""No truth/labels, online graphs or posterior residuals in the four-anchor test."""
import math
import numpy as np
from scipy.optimize import least_squares
from scipy.stats import chi2


def antenna(pose, model):
    x, y, yaw = pose
    lx, ly = model['base_to_antenna_body_xy_m']
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([x+c*lx-s*ly, y+s*lx+c*ly, model['antenna_height_m']])


def antenna_jacobian(pose, model):
    lx, ly = model['base_to_antenna_body_xy_m']; yaw = pose[2]
    return np.array([[1., 0., -math.sin(yaw)*lx-math.cos(yaw)*ly],
                     [0., 1., math.cos(yaw)*lx-math.sin(yaw)*ly]])


def four_anchor(observations, model, counts, noise):
    keys = sorted(model['anchors_xyz_m'])
    if len(keys) != 4 or any(k not in observations for k in keys):
        return dict(computable=False, reason='MISSING_FOUR_ANCHORS', statistic=None, df=None)
    refs = np.array([model['anchors_xyz_m'][k] for k in keys])
    z = np.array([observations[k]-model['range_bias_m'][k] for k in keys])
    if not np.isfinite(z).all() or np.any(z <= 0):
        return dict(computable=False, reason='INVALID_RANGE', statistic=None, df=None)
    if noise == 'engineering_0.2m': sigma = np.full(4, .2)
    elif noise == 'raw_0.04m': sigma = np.full(4, .04)
    elif noise == 'median_iid_asymptotic':
        if any(counts.get(k, 0) < 5 for k in keys):
            return dict(computable=False, reason='MISSING_SAMPLE_COUNTS', statistic=None, df=None)
        sigma = .04*np.sqrt(np.pi/(2*np.array([counts[k] for k in keys])))
    else: raise ValueError('Unknown frozen B1 noise model')
    # Squared slant-range differences provide an independent algebraic initializer.
    height = model['antenna_height_m']
    matrix = 2*(refs[1:, :2]-refs[0, :2])
    rhs = (z[0]**2-z[1:]**2+np.sum(refs[1:, :2]**2, axis=1)-np.sum(refs[0, :2]**2)
           +(height-refs[1:, 2])**2-(height-refs[0, 2])**2)
    if np.linalg.matrix_rank(matrix) < 2:
        return dict(computable=False, reason='UNOBSERVABLE_ANCHORS', statistic=None, df=None)
    initial = np.linalg.lstsq(matrix, rhs, rcond=None)[0]
    def fun(x):
        return (np.sqrt(np.sum((x-refs[:, :2])**2, axis=1)+(height-refs[:, 2])**2)-z)/sigma
    def jac(x):
        diff = x-refs[:, :2]
        rho = np.sqrt(np.sum(diff**2, axis=1)+(height-refs[:, 2])**2)
        return diff/rho[:, None]/sigma[:, None]
    try:
        fit = least_squares(fun, initial, jac=jac, loss='linear', max_nfev=100,
                            ftol=1e-10, xtol=1e-10, gtol=1e-10)
        if not fit.success or not np.isfinite(fit.x).all() or np.linalg.matrix_rank(fit.jac) != 2:
            return dict(computable=False, reason='FIT_FAILED_OR_RANK_DEFICIENT', statistic=None, df=None)
        return dict(computable=True, reason='EMPIRICAL_GAUSSIAN_REFERENCE_ONLY',
                    statistic=float(fit.fun@fit.fun), df=2, antenna_xy_m=fit.x.tolist(),
                    residuals_m=(fit.fun*sigma).tolist(), sigma_m=sigma.tolist())
    except (ValueError, np.linalg.LinAlgError, FloatingPointError) as error:
        return dict(computable=False, reason=type(error).__name__, statistic=None, df=None)


def decision(computable, statistic, threshold, main_accepted, reason=''):
    ready = bool(computable and main_accepted and statistic is not None and np.isfinite(statistic))
    alarm = bool(ready and statistic > threshold)
    return dict(computable=ready, alarm=alarm, available=bool(ready and not alarm),
                reason=reason if ready else 'UNKNOWN_OR_MAIN_NOT_ACCEPTED')


def separation(full_xy, subset_xy, full_influence, subset_influence):
    """Same primitive columns => cross covariance is explicit, never zeroed."""
    difference = np.asarray(full_xy)-subset_xy
    kf, ks = np.asarray(full_influence), np.asarray(subset_influence)
    kd = kf-ks
    covariance = kd@kd.T
    cross = kf@ks.T
    singular = np.linalg.svd(covariance, compute_uv=False)
    rank = int(np.sum(singular > max(1e-14, singular[0]*1e-10)))
    result = dict(delta_xy_m=difference.tolist(), separation_m=float(np.linalg.norm(difference)),
                  covariance=covariance.tolist(), cross_covariance=cross.tolist(),
                  full_covariance=(kf@kf.T).tolist(), subset_covariance=(ks@ks.T).tolist(), rank=rank,
                  independent_sum_covariance=(kf@kf.T+ks@ks.T).tolist(),
                  statistic=None, computable=False, reason='SEPARATION_RANK_DEFICIENT')
    if rank == 2 and np.isfinite(covariance).all():
        result.update(statistic=max(0., float(difference@np.linalg.solve(covariance, difference))),
                      computable=True, reason='FROZEN_LINEARIZATION_ENGINEERING_COVARIANCE')
    return result
