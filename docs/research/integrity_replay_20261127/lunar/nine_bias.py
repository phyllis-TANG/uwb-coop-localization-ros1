"""Nine-range historical innovation baseline adapted for the causal lunar observations."""
from statistics import NormalDist

import numpy as np


class NineBiasFilter:
    """Lunar adaptation of archived nine-bias innovation gate and history-inclusive HPL.

    Archive: tools/midterm_dual_robot_contract_a/round2/trajectory.py (Filter.step).
    Per-step horizontal displacement covariance comes from lunar observations, and the
    bias driving-noise variance uses actual dt. The first epoch uses the noisy 0.5-m
    prior in the archive with no displacement or bias diffusion before the update.
    """
    def __init__(self, obs):
        self.anchors = np.asarray(obs["anchors"])
        self.x = np.r_[np.asarray(obs["prior"]).ravel(), np.zeros(9)]
        self.cov = np.diag([obs["sigma_prior"]**2] * 4 + [.3**2] * 9)
        self.noise = np.eye(9) * obs["sigma_range"]**2
        self.motion_var = obs["sigma_motion"]**2
        self.transfer = np.empty((13, 0))
        self.prev = None
        self.gaussian_factor = NormalDist().inv_cdf(1. - .005 / 2.)

    def step(self, t, ranges, odom, heights):
        self.x[:4] += np.asarray(odom).ravel()
        if self.prev is not None:
            dt = t - self.prev
            assert dt > 0
            self.cov += np.diag([self.motion_var] * 4 + [.01**2 * dt] * 9)
        self.prev = t
        xyz = np.column_stack((self.x[:4].reshape(2, 2), heights))
        delta = xyz[:, None] - self.anchors[None, :]
        dist = np.linalg.norm(delta, axis=-1)
        peer = xyz[1] - xyz[0]
        peer_dist = np.linalg.norm(peer)
        assert min(np.min(dist), peer_dist) > 1e-8
        H = np.zeros((9, 13))
        for rover in (0, 1):
            H[4*rover:4*rover+4, 2*rover:2*rover+2] = delta[rover, :, :2] / dist[rover, :, None]
        H[8, :2] = -peer[:2] / peer_dist
        H[8, 2:4] = -H[8, :2]
        H[:, 4:] = np.eye(9)
        innovation = np.asarray(ranges) - (np.r_[dist.ravel(), peer_dist] + self.x[4:])
        S = H @ self.cov @ H.T + self.noise
        stat = float(innovation @ np.linalg.solve(S, innovation))
        accept = stat <= 21.665994333461924  # archive 99% chi-square gate, df=9
        bound = [None, None]
        if accept:
            gain = np.linalg.solve(S, H @ self.cov).T
            A = np.eye(13) - gain @ H
            self.x += gain @ innovation
            self.cov = A @ self.cov @ A.T + gain @ self.noise @ gain.T
            self.transfer = np.column_stack((A @ self.transfer, gain))
            residual_effect = .02 * np.abs(self.transfer[:4]).sum(axis=1)
            axis_bound = residual_effect + self.gaussian_factor * np.sqrt(np.diag(self.cov)[:4])
            bound = np.linalg.norm(axis_bound.reshape(2, 2), axis=1).tolist()
        return dict(t=t, xy=self.x[:4].reshape(2, 2).copy().tolist(), hpl=bound,
                    fd_pass=accept, status="accepted" if accept else "innovation_rejected",
                    augmented=[], selected=[])
