"""Four-state planar motion, exact constant-control mean and engineering Q(dt)."""
import math
import numpy as np


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def rotation(yaw):
    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s], [s, c]])


def coefficients(phi):
    if abs(phi) < 1e-4:
        a = 1 - phi**2 / 6 + phi**4 / 120
        b = phi / 2 - phi**3 / 24 + phi**5 / 720
        da = -phi / 3 + phi**3 / 30 - phi**5 / 840
        db = .5 - phi**2 / 8 + phi**4 / 144
    else:
        a, b = math.sin(phi) / phi, (1 - math.cos(phi)) / phi
        da = (phi * math.cos(phi) - math.sin(phi)) / phi**2
        db = (phi * math.sin(phi) - (1 - math.cos(phi))) / phi**2
    return a, b, da, db


def transition(state, velocity, observed_rate, dt, estimate_bias):
    if not math.isfinite(dt) or dt < 0:
        raise ValueError('nonnegative finite physical dt required')
    x = np.asarray(state, dtype=float)
    vx, vy = velocity
    omega = observed_rate - x[3] if estimate_bias else observed_rate
    phi = omega * dt
    a, b, da, db = coefficients(phi)
    body = dt * np.array([a * vx - b * vy, b * vx + a * vy])
    change = rotation(x[2]) @ body
    out = x.copy()
    out[:2] += change
    out[2] = wrap(out[2] + phi)
    F = np.eye(4)
    F[:2, 2] = [-change[1], change[0]]
    if estimate_bias:
        derivative = rotation(x[2]) @ (dt * np.array([da * vx - db * vy, db * vx + da * vy]))
        F[:2, 3] = -dt * derivative
        F[2, 3] = -dt
    else:
        out[3] = 0.
        F[3, 3] = 0.
    return out, F


def process_covariance(state, velocity, observed_rate, dt, estimate_bias, sigma_v, sigma_yaw, sigma_bias):
    """Mid-heading frozen continuous linearization; includes bias cross terms.

    q_v: m^2/s; q_yaw: rad^2/s; q_bias: (rad/s)^2/s. A^3=0,
    so the integral of exp(A t) Qc exp(A t)' is a finite polynomial.
    This local engineering approximation is separate from the exact mean F.
    """
    omega = observed_rate - state[3] if estimate_bias else observed_rate
    world_velocity = rotation(state[2] + omega * dt / 2) @ np.asarray(velocity)
    A = np.zeros((4, 4))
    A[:2, 2] = [-world_velocity[1], world_velocity[0]]
    if estimate_bias:
        A[2, 3] = -1.
    Qc = np.diag([sigma_v**2, sigma_v**2, sigma_yaw**2, sigma_bias**2 if estimate_bias else 0.])
    powers = [np.eye(4), A, A @ A / 2]
    Q = np.zeros((4, 4))
    for i, left in enumerate(powers):
        for j, right in enumerate(powers):
            Q += (left @ Qc @ right.T) * dt**(i + j + 1) / (i + j + 1)
    return (Q + Q.T) / 2


def antenna(state, lever_xy, height):
    offset = rotation(state[2]) @ np.asarray(lever_xy)
    point = np.r_[np.asarray(state[:2]) + offset, height]
    H = np.zeros((3, 4))
    H[:2, :2] = np.eye(2)
    H[:2, 2] = [-offset[1], offset[0]]
    return point, H


def range_geometry(state8, vehicles, anchors, car, target):
    tag_other = 'node_0' if car == 'car1' else 'node_1'
    peer = target == tag_other
    own = 0 if car == 'car1' else 1
    positions, jacobians = {}, {}
    for i in (range(2) if peer else [own]):
        name = ('car1', 'car2')[i]
        positions[i], jacobians[i] = antenna(state8[4*i:4*i+4], vehicles[name]['lever_xy'], vehicles[name]['height'])
    delta = positions[0] - positions[1] if peer else positions[own] - np.asarray(anchors[target])
    predicted = float(np.linalg.norm(delta))
    if predicted < 1e-9:
        raise ValueError('degenerate zero range')
    unit = delta / predicted
    H = np.zeros(8)
    if peer:
        H[:4], H[4:] = unit @ jacobians[0], -unit @ jacobians[1]
    else:
        H[4*own:4*own+4] = unit @ jacobians[own]
    return predicted, H
