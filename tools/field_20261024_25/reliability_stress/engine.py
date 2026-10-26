"""Small causal XY estimator; intentionally has no simulator/evaluator import."""
import copy
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_adapter import antenna, wall_distance  # PR45 geometry, unchanged
from protocol import CARS, Gate, Admission


def range_jac(a, b):
    d = a-b
    norm = max(float(np.linalg.norm(d)), 1e-9)
    return norm, d[:2]/norm


class Estimator:
    def __init__(self, method, config, geometry, initial):
        if method not in config["methods"]:
            raise ValueError("unknown method")
        online_keys = ("methods", "initial_sigma_m", "process_sigma_m", "gn_iterations", "wall_sigma_m",
                       "peer_sigma_m", "huber_delta", "gate_z", "quarantine_bad_count", "reopen_good_count",
                       "healthy_information_min", "healthy_shift_cap_m", "weak_shift_cap_m", "max_age_ns", "correlation_bin_ns")
        self.method, self.config, self.geometry = method, {k: copy.deepcopy(config[k]) for k in online_keys}, copy.deepcopy(geometry)
        self.xy = np.array([initial[c][:2] for c in CARS], dtype=float)
        self.shadow = self.xy.copy()
        self.cov = np.eye(4)*config["initial_sigma_m"]**2
        self.shadow_cov = self.cov.copy()
        self.history = []
        self.admission = Admission(config)
        self.gate = Gate(config)
        self.linear_solves = 0

    def _solve(self, H, b):
        self.linear_solves += 1
        return np.linalg.solve(H, b)

    def _pose_at(self, stamp):
        if stamp in self.pose_cache:
            return self.pose_cache[stamp]
        times = [t for t, _ in self.history]
        index = int(np.searchsorted(times, stamp, side="right"))-1
        if index < 0 or stamp > times[-1]:
            raise ValueError("no arrived odometry covering sample time")
        if index == len(times)-1 or times[index] == stamp:
            self.pose_cache[stamp] = self.history[index][1]
            return self.pose_cache[stamp]
        # Both endpoints have already arrived at the current cutoff.
        f = (stamp-times[index])/(times[index+1]-times[index])
        self.pose_cache[stamp] = self.history[index][1]*(1-f)+self.history[index+1][1]*f
        return self.pose_cache[stamp]

    def _antenna(self, xy, index, stamp):
        key = (index, stamp)
        if key not in self.antenna_offsets:
            pose = self._pose_at(stamp)[index]
            lag = pose[:2]-self.history[-1][1][index, :2]
            self.antenna_offsets[key] = antenna(np.r_[lag, pose[2]], CARS[index], self.geometry)
        position = self.antenna_offsets[key].copy()
        position[:2] += xy
        return position

    def _wall_update(self, predicted, prior_cov, walls):
        inv = np.linalg.inv(prior_cov)
        x = predicted.copy()
        for _ in range(self.config["gn_iterations"]):
            H, b = inv.copy(), inv@(x-predicted).ravel()
            information = np.zeros((2, 2, 2))
            counts = [0, 0]
            for r in walls:
                i = CARS.index(r["vehicle_id"])
                p = self._antenna(x[i], i, r["sample_ns"])
                h, j = range_jac(p, np.asarray(self.geometry["anchors_xyz_m"][r["target_id"]]))
                w = 1/self.config["wall_sigma_m"]**2
                information[i] += w*np.outer(j, j)
                b[2*i:2*i+2] += w*j*(h-r["range_m"])
                counts[i] += 1
            for i in range(2):
                H[2*i:2*i+2, 2*i:2*i+2] += information[i]
            x -= self._solve(H, b).reshape(2, 2)
        infos = [float(np.linalg.eigvalsh(v)[0]) for v in information]
        return x, np.linalg.inv(H), infos, counts

    def _peer_geometry(self, x, row):
        a = self._antenna(x[0], 0, row["sample_ns"])
        b = self._antenna(x[1], 1, row["sample_ns"])
        h, j = range_jac(a, b)
        return h, np.r_[j, -j]

    def _peer_update(self, mean, cov, rows, robust=False):
        inv = np.linalg.inv(cov)
        x = mean.copy()
        for _ in range(self.config["gn_iterations"]):
            H, b = inv.copy(), inv@(x-mean).ravel()
            for r in rows:
                h, j = self._peer_geometry(x, r)
                residual = (h-r["range_m"])/self.config["peer_sigma_m"]
                w = 1/self.config["peer_sigma_m"]**2
                if robust:
                    w *= min(1., self.config["huber_delta"]/max(abs(residual), 1e-12))
                H += w*np.outer(j, j)
                b += w*j*(h-r["range_m"])
            x -= self._solve(H, b).reshape(2, 2)
        full_cov = np.linalg.inv(H)
        return x, full_cov

    def step(self, now_ns, odom, arrived):
        """odom is the arrived, room-aligned synthetic pose at now; no truth API."""
        started = time.monotonic()
        odom = np.asarray(odom, dtype=float)
        if odom.shape != (2, 3) or not np.isfinite(odom).all():
            raise ValueError("expected finite two-car arrived odometry")
        delta = np.zeros((2, 2)) if not self.history else odom[:, :2]-self.history[-1][1][:, :2]
        if self.history and now_ns <= self.history[-1][0]:
            raise ValueError("odometry time must strictly increase")
        self.history.append((now_ns, odom.copy()))
        self.pose_cache = {}
        self.antenna_offsets = {}
        walls, peers, trace = self.admission.take(now_ns, arrived)
        q = np.eye(4)*self.config["process_sigma_m"]**2
        last_shadow, last_cov = self.shadow.copy(), self.shadow_cov.copy()
        shadow, shadow_cov, _, _ = self._wall_update(last_shadow+delta, last_cov+q, walls)
        # Equal budget: even the unused shadow peer pass solves the same fixed
        # number of 4x4 systems. Its row list is ALWAYS empty.
        shadow, shadow_cov = self._peer_update(shadow, shadow_cov, [])
        if self.method == "firewall":
            prior, pcov = last_shadow+delta, last_cov+q
        else:
            prior, pcov = self.xy+delta, self.cov+q
        mean, cov, info, counts = self._wall_update(prior, pcov, walls)
        accepted, innovations = [], []
        for r in peers:
            h, j = self._peer_geometry(mean, r)
            variance = self.config["peer_sigma_m"]**2 + float(j@cov@j)
            z = (r["range_m"]-h)/np.sqrt(variance)
            use = self.method != "independent"
            if self.method in ("firewall", "no_firewall"):
                use = self.gate.admit(r["vehicle_id"], float(z))
            innovations.append({"vehicle_id": r["vehicle_id"], "record_index": r["record_index"],
                                "z": float(z), "accepted": bool(use)})
            if use:
                accepted.append(r)
        x, out_cov = self._peer_update(mean, cov, accepted, robust=self.method == "huber")
        healthy = [counts[i] >= 3 and info[i] >= self.config["healthy_information_min"] for i in range(2)]
        caps = [self.config["healthy_shift_cap_m"] if h else self.config["weak_shift_cap_m"] for h in healthy]
        clipped = [False, False]
        if self.method in ("firewall", "no_firewall"):
            for i in range(2):
                d = x[i]-mean[i]
                norm = float(np.linalg.norm(d))
                if norm > caps[i]:
                    x[i] = mean[i]+d*caps[i]/norm
                    clipped[i] = True
            # Conservative marginal feedback for ablation; no spurious precision
            # gain from a clipped update. Firewall never feeds either back.
            out_cov = cov.copy()
        success = bool(np.isfinite(x).all())
        self.xy, self.cov = (x, out_cov) if success else (prior, pcov)
        self.shadow, self.shadow_cov = shadow, shadow_cov
        d = {"solver_success": success, "linear_solves_cumulative": self.linear_solves,
             "wall_count": counts, "wall_information_min": info, "healthy": healthy,
             "shift_cap_m": caps, "clipped": clipped, "causal": True,
             "peer_factors": len(peers), "peer_accepted": len(accepted),
             "innovations": innovations, "gate": copy.deepcopy(self.gate.state), "admission_trace": trace,
             "shift_from_independent_shadow_m": np.linalg.norm(self.xy-shadow, axis=1).tolist(),
             "elapsed_s": time.monotonic()-started}
        return self.xy.copy(), d
