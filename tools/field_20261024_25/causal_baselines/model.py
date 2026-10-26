"""SE(2) odometry and fixed-variance EKF baselines, strictly arrival-causal.

The six-state filter holds one base pose at each vehicle's last odometry
measurement time. Range evaluation projects those anchors to the *individual*
range measurement time using a bounded, explicitly configured constant twist.
Out-of-sequence measurements are rejected, never silently retimed or smoothed.
"""
from collections import Counter
import copy
import math

import numpy as np

CARS = ("car1", "car2")
TAGS = {"car1": "node_1", "car2": "node_0"}
WALLS = ("node_2", "node_3", "node_8", "node_10")
METHODS = ("odom_only", "independent", "joint")


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


def rotation(angle):
    c, s = math.cos(angle), math.sin(angle)
    return np.array([[c, -s], [s, c]])


def pose_from_row(row):
    q = np.array([float(row["orientation_"+k]) for k in "xyzw"])
    if not np.isfinite(q).all() or abs(float(q @ q)-1) > 1e-3:
        raise ValueError("invalid non-unit odometry quaternion")
    x, y, z, w = q
    yaw = math.atan2(2*(w*z+x*y), 1-2*(y*y+z*z))
    pose = np.array([float(row["position_x"]), float(row["position_y"]), yaw])
    if not np.isfinite(pose).all():
        raise ValueError("nonfinite odometry position")
    return pose


def compose_odom(state, previous, current):
    """Body-relative odometry increment; preserves nonzero heading and reverse."""
    delta = rotation(-previous[2]) @ (current[:2]-previous[:2])
    change = rotation(state[2]) @ delta
    predicted = np.r_[state[:2]+change, wrap(state[2]+wrap(current[2]-previous[2]))]
    jacobian = np.eye(3)
    jacobian[:2, 2] = [-change[1], change[0]]
    return predicted, jacobian


def twist_translation(twist, dt):
    vx, vy, omega = twist
    if abs(omega*dt) < 1e-8:
        # First-order angular terms also make the zero-turn limit continuous.
        return np.array([vx*dt-vy*omega*dt*dt/2, vy*dt+vx*omega*dt*dt/2])
    sine, cosine = math.sin(omega*dt), math.cos(omega*dt)
    return np.array([(vx*sine+vy*(cosine-1))/omega,
                     (vx*(1-cosine)+vy*sine)/omega])


def antenna_at(state, twist, dt, car_config):
    lever = np.asarray(car_config["antenna_body_xyz_m"]["value"], dtype=float)
    displacement = twist_translation(twist, dt)+rotation(twist[2]*dt) @ lever[:2]
    offset = rotation(state[2]) @ displacement
    position = np.r_[state[:2]+offset, car_config["base_height_m"]["value"]+lever[2]]
    jacobian = np.zeros((3, 3))
    jacobian[:2, :2] = np.eye(2)
    jacobian[:2, 2] = [-offset[1], offset[0]]
    return position, jacobian


def map_time(row, model):
    """Integer, origin-centered affine mapping; no float epoch arithmetic."""
    value = int(row[model["field"]])
    delta = (value-int(model["source_origin_ns"]))*int(model["rate_numerator"])
    denominator = int(model["rate_denominator"])
    # Nearest integer, ties away from zero, for both signed directions.
    scaled = (abs(delta)+denominator//2)//denominator
    return int(model["destination_origin_ns"])+(scaled if delta >= 0 else -scaled)


def known(item):
    return (isinstance(item, dict) and item.get("status") == "provided"
            and item.get("value") is not None and bool(item.get("source")))


def clock_ready(clock):
    fields = ("field", "source_origin_ns", "destination_origin_ns", "rate_numerator",
              "rate_denominator", "uncertainty_ns", "source", "source_clock_id", "destination_clock_id")
    return (isinstance(clock, dict) and clock.get("status") == "provided"
            and all(clock.get(k) is not None for k in fields) and bool(clock["source"])
            and clock["field"] == "header_epoch_ns"
            and all(isinstance(clock[k], int) and not isinstance(clock[k], bool) for k in fields[1:6])
            and clock["rate_numerator"] > 0 and clock["rate_denominator"] > 0
            and clock["uncertainty_ns"] >= 0)


def readiness(config):
    out = {m: {c: [] for c in CARS} for m in METHODS}
    for method in METHODS:
        for car in CARS:
            if method == "odom_only" and config["odom_only_frame"] == "source_odometry":
                continue
            cc = config["vehicles"][car]
            for name in ("initial_room_pose", "initial_covariance_diagonal"):
                if not known(cc.get(name)):
                    out[method][car].append(car+":"+name+":unknown")
            if not clock_ready(cc.get("odom_clock")):
                out[method][car].append(car+":odom_clock:unknown")
            if method != "odom_only":
                for name in ("antenna_body_xyz_m", "base_height_m"):
                    if not known(cc.get(name)):
                        out[method][car].append(car+":"+name+":unknown")
                if not clock_ready(cc.get("range_clock")):
                    out[method][car].append(car+":range_clock:unknown")
                if not known(config.get("anchors_xyz_m")):
                    out[method][car].append("anchors_xyz_m:unknown")
    # A joint solve needs both vehicles; one independent solve may still run.
    blockers = sorted(set(out["joint"]["car1"]+out["joint"]["car2"]))
    out["joint"] = {c: list(blockers) for c in CARS}
    return out


def validate_config(config):
    if config.get("schema_version") != 1 or config.get("scope") not in ("field", "synthetic"):
        raise ValueError("unsupported baseline configuration")
    if config["odom_only_frame"] not in ("source_odometry", "room"):
        raise ValueError("unsupported odom-only frame")
    if config["peer_source_vehicle"] not in CARS:
        raise ValueError("fixed peer direction required")
    if config["initialization_binding"] != "first_accepted_odometry_measurement":
        raise ValueError("initialization must explicitly bind to first odometry")
    for key in ("publish_period_ns", "max_publish_age_ns", "max_measurement_latency_ns", "max_extrapolation_ns",
                "min_range_spacing_ns", "geometry_window_ns", "max_events"):
        if not isinstance(config[key], int) or config[key] <= 0:
            raise ValueError("positive integer policy required: "+key)
    for key in ("wall_sigma_m", "peer_sigma_m", "odom_xy_sigma_sqrt_s", "odom_yaw_sigma_sqrt_s"):
        item = config["weights"][key]
        if not known(item) or not math.isfinite(item["value"]) or item["value"] <= 0:
            raise ValueError("explicit positive fixed weight required: "+key)
    def walk(value):
        if isinstance(value, dict):
            if config["scope"] == "field" and value.get("status") == "provided" and value.get("source_kind") == "synthetic":
                raise ValueError("synthetic parameter cannot be used in field configuration")
            for v in value.values():walk(v)
        elif isinstance(value, list):
            for v in value:walk(v)
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("nonfinite configuration value")
    walk(config)
    for car in CARS:
        cc = config["vehicles"][car]
        for key in ("odom_clock", "range_clock"):
            if isinstance(cc.get(key), dict) and cc[key].get("status") == "provided" and not clock_ready(cc[key]):
                raise ValueError("invalid provided clock model: "+car+":"+key)
            if clock_ready(cc.get(key)) and cc[key]["destination_clock_id"] != config["master_clock_id"]:
                raise ValueError("clock destination must match replay master clock")
        for key in ("initial_room_pose", "initial_covariance_diagonal", "antenna_body_xyz_m"):
            if known(cc.get(key)):
                v = np.asarray(cc[key]["value"], dtype=float)
                if v.shape != (3,) or not np.isfinite(v).all():
                    raise ValueError("invalid vehicle vector: "+key)
                if key == "initial_covariance_diagonal" and np.any(v <= 0):
                    raise ValueError("initial covariance must be positive")
        if known(cc.get("base_height_m")) and not math.isfinite(cc["base_height_m"]["value"]):
            raise ValueError("invalid base height")
    if known(config.get("anchors_xyz_m")):
        for target, xyz in config["anchors_xyz_m"]["value"].items():
            if target not in WALLS or np.asarray(xyz).shape != (3,) or not np.isfinite(xyz).all():
                raise ValueError("invalid wall anchor")


class Baseline:
    def __init__(self, method, config):
        validate_config(config)
        if method not in METHODS:raise ValueError("unknown method")
        self.method, self.config = method, copy.deepcopy(config)
        self.blocked = readiness(config)[method]
        self.local = method == "odom_only" and config["odom_only_frame"] == "source_odometry"
        self.x, self.P = np.zeros(6), np.zeros((6, 6))
        self.odom, self.anchor_ns, self.twist = {}, {}, {}
        self.last_row, self.last_header = {}, {}
        self.seen, self.link_time, self.wall_geometry = set(), {}, {}
        self.counts = Counter()
        self.last_failure = {}
        self.last_event_receive = None

    def _slice(self, car):
        i = CARS.index(car)*3
        return slice(i, i+3)

    def process(self, event):
        """An event is admitted only when the caller's publication cutoff allows it."""
        row, kind = event["row"], event["kind"]
        receive = int(row["receive_epoch_ns"])
        if self.last_event_receive is not None and receive < self.last_event_receive:
            raise ValueError("events must be processed in nondecreasing arrival order")
        self.last_event_receive = receive
        car = row["vehicle_id"]
        if car not in CARS:raise ValueError("unknown vehicle identity")
        affected = (car,)
        try:
            numeric_range = float(row.get("range_m"))
            if not math.isfinite(numeric_range):numeric_range = None
        except (TypeError, ValueError):numeric_range = None
        details = {"kind": kind, "vehicle_id": car, "receive_epoch_ns": receive,
                   "header_epoch_ns": int(row["header_epoch_ns"]) if row.get("header_epoch_ns") not in (None, "") else None,
                   "record_index": int(row["record_index"]), "target_id": row.get("target_id"),
                   "link_index": row.get("link_index"), "tag_id": row.get("tag_id"), "range_m": numeric_range,
                   "source_file_sha256": row["source_file_sha256"],
                   "raw_frame_id": row.get("raw_frame_id"), "bridge_frame_id": row.get("bridge_frame_id"),
                   "device_local_time_ms": row.get("device_local_time_ms"),
                   "device_system_time_ms": row.get("device_system_time_ms"),
                   "device_clock_id": row.get("device_clock_id"), "measurement_epoch_ns": None}
        def result(status):
            details["status"] = status
            self.counts[status] += 1
            if status.startswith("numerical_"):
                for c in affected:self.last_failure[c] = status
            elif status in ("initialized", "odometry_observed", "odometry_predicted", "wall_updated", "peer_updated"):
                for c in affected:self.last_failure.pop(c, None)
            return details
        if self.blocked[car]:return result("BLOCKED")
        identity = (kind, car, row["source_file_sha256"], int(row["record_index"]), int(row.get("link_index") or 0))
        if identity in self.seen:return result("duplicate_trace")
        self.seen.add(identity)
        if kind == "odom":
            if row["frame_id"] != car+"/odom" or row["child_frame_id"] != car+"/base_footprint":
                return result("invalid_odometry_frame")
            try:
                pose = pose_from_row(row)
                twist = np.array([float(row[k]) for k in ("linear_x", "linear_y", "angular_z")])
                if not np.isfinite(twist).all():raise ValueError("invalid twist")
                header = int(row["header_epoch_ns"])
            except (ValueError, TypeError, KeyError):return result("invalid_odometry")
            if car in self.last_header and header <= self.last_header[car]:
                return result("duplicate_or_out_of_order_odometry")
            cc = self.config["vehicles"][car]
            measured = receive if self.local else map_time(row, cc["odom_clock"])
            details["measurement_epoch_ns"] = None if self.local else measured
            if not self.local and measured > receive:return result("future_measurement_time")
            if not self.local and receive-measured > self.config["max_measurement_latency_ns"]:
                return result("stale_measurement_on_arrival")
            if car in self.anchor_ns and measured <= self.anchor_ns[car]:return result("out_of_order_measurement_time")
            sl = self._slice(car)
            if car not in self.odom:
                self.x[sl] = pose if self.local else cc["initial_room_pose"]["value"]
                if not self.local:self.P[sl, sl] = np.diag(cc["initial_covariance_diagonal"]["value"])
                status = "initialized"
            elif self.local:
                self.x[sl] = pose
                status = "odometry_observed"
            else:
                dt = (measured-self.anchor_ns[car])/1e9
                prediction, jac = compose_odom(self.x[sl], self.odom[car], pose)
                F = np.eye(6);F[sl, sl] = jac
                noise = np.array([self.config["weights"]["odom_xy_sigma_sqrt_s"]["value"]**2]*2+
                                 [self.config["weights"]["odom_yaw_sigma_sqrt_s"]["value"]**2])*dt
                G = np.eye(3);G[:2, :2] = rotation(self.x[sl][2])
                new_p = F @ self.P @ F.T
                new_p[sl, sl] += G @ np.diag(noise) @ G.T
                if not np.isfinite(prediction).all() or not np.isfinite(new_p).all():
                    return result("numerical_odometry_failed_hold")
                self.x[sl], self.P = prediction, (new_p+new_p.T)/2
                status = "odometry_predicted"
            self.odom[car], self.twist[car] = pose, twist
            self.anchor_ns[car], self.last_header[car] = measured, header
            self.last_row[car] = row
            return result(status)
        if kind != "range":raise ValueError("unknown event kind")
        if self.method == "odom_only":return result("excluded_odom_only")
        if row.get("tag_id") != TAGS[car]:return result("invalid_range_identity")
        if row.get("source") != "raw" or str(row.get("primary_observation")) not in ("1", "True"):
            return result("excluded_bridge_duplicate")
        if row.get("pairing_status") in ("ambiguous_header", "paired_mismatch"):
            return result("excluded_ambiguous_or_mismatched_pair")
        try:value = float(row["range_m"])
        except (ValueError, TypeError):return result("invalid_range")
        if str(row.get("valid")) not in ("1", "True") or not math.isfinite(value) or value <= 0:
            return result("invalid_range")
        target = row["target_id"]
        peer = target == TAGS["car2" if car == "car1" else "car1"]
        if target not in WALLS and not peer:return result("unknown_range_target")
        cc = self.config["vehicles"][car]
        measured = map_time(row, cc["range_clock"])
        details["measurement_epoch_ns"] = measured
        if measured > receive:return result("future_measurement_time")
        if receive-measured > self.config["max_measurement_latency_ns"]:return result("stale_measurement_on_arrival")
        if peer:
            if self.method == "independent":return result("excluded_independent_peer")
            if car != self.config["peer_source_vehicle"]:return result("excluded_correlated_reverse_direction")
        involved = CARS if peer else (car,)
        affected = involved
        for c in involved:
            if c not in self.odom:return result("missing_odometry_support:"+c)
            age = measured-self.anchor_ns[c]
            if age < 0:return result("measurement_before_odometry_anchor:"+c)
            if age > self.config["max_extrapolation_ns"]:return result("stale_odometry_support:"+c)
        key = (car, target)
        if key in self.link_time:
            delta = measured-self.link_time[key]
            if delta <= 0:return result("duplicate_or_out_of_order_link_time")
            if delta < self.config["min_range_spacing_ns"]:return result("excluded_fixed_rate_thinning")
        positions, jacobians, ages = {}, {}, {}
        for c in involved:
            ages[c] = measured-self.anchor_ns[c]
            positions[c], jacobians[c] = antenna_at(self.x[self._slice(c)], self.twist[c], ages[c]/1e9, self.config["vehicles"][c])
        if peer:
            delta = positions["car1"]-positions["car2"]
        else:
            if target not in self.config["anchors_xyz_m"]["value"]:return result("missing_anchor_geometry")
            delta = positions[car]-np.asarray(self.config["anchors_xyz_m"]["value"][target])
        expected = float(np.linalg.norm(delta))
        if expected < 1e-9:return result("degenerate_zero_distance")
        unit = delta/expected
        H = np.zeros(6)
        if peer:
            H[:3], H[3:] = unit @ jacobians["car1"], -unit @ jacobians["car2"]
        else:H[self._slice(car)] = unit @ jacobians[car]
        variance = self.config["weights"]["peer_sigma_m" if peer else "wall_sigma_m"]["value"]**2
        innovation_variance = float(H @ self.P @ H+variance)
        if not math.isfinite(innovation_variance) or innovation_variance <= 0:return result("numerical_range_failed_hold")
        K = self.P @ H/innovation_variance
        innovation = value-expected
        proposal = self.x+K*innovation
        proposal[2], proposal[5] = wrap(proposal[2]), wrap(proposal[5])
        J = np.eye(6)-np.outer(K, H)
        covariance = J @ self.P @ J.T+np.outer(K, K)*variance
        covariance = (covariance+covariance.T)/2
        try:
            covariance_valid = np.isfinite(covariance).all() and np.linalg.eigvalsh(covariance).min() >= -1e-10
        except np.linalg.LinAlgError:covariance_valid = False
        if not np.isfinite(proposal).all() or not covariance_valid:
            return result("numerical_range_failed_hold")
        self.x, self.P = proposal, covariance
        self.link_time[key] = measured
        if not peer:self.wall_geometry[(car, target)] = (measured, H[self._slice(car)][:2].copy())
        details.update(expected_range_m=expected, innovation_m=innovation, fixed_variance_m2=variance,
                       support_age_ns=ages, correlation_policy="fixed_single_direction" if peer else "fixed_rate_per_directed_link")
        return result("peer_updated" if peer else "wall_updated")

    def snapshot(self, publication_ns):
        if not isinstance(publication_ns, int):raise ValueError("publication must be exact integer ns")
        if self.last_event_receive is not None and publication_ns < self.last_event_receive:
            raise ValueError("publication precedes an admitted event")
        out = {}
        for car in CARS:
            reasons = self.blocked[car]
            common = {"blocked_reasons": reasons, "frame_id": car+"/odom" if self.local else "room",
                      "pose_reference_point": "base_footprint", "time_model_provided": not self.local and not reasons}
            if reasons or car not in self.odom:
                out[car] = dict(common, pose=None, covariance=None, valid=False,
                               fallback_status="BLOCKED" if reasons else "uninitialized")
                continue
            row = self.last_row[car]
            age = publication_ns-int(row["receive_epoch_ns"])
            state = self.x[self._slice(car)].copy()
            block = self.P[self._slice(car), self._slice(car)]
            covariance = None if self.local or not np.isfinite(block).all() else block.tolist()
            # Publications hold the last odometry-anchored estimate. No implicit
            # projection from host receipt time to physical state time is made.
            geometry = [v for (c,t),(stamp,v) in self.wall_geometry.items()
                        if c == car and 0 <= publication_ns-stamp <= self.config["geometry_window_ns"]]
            rank = int(np.linalg.matrix_rank(np.asarray(geometry), tol=1e-8)) if geometry else 0
            measurement_age = None if self.local else publication_ns-self.anchor_ns[car]
            stale = age > self.config["max_publish_age_ns"] or (measurement_age is not None and measurement_age > self.config["max_publish_age_ns"])
            failed = car in self.last_failure
            degraded = self.method != "odom_only" and (len(geometry)<3 or rank<2)
            out[car] = dict(common, pose=state.tolist(), covariance=covariance, valid=not stale and not failed,
                fallback_status="numerical_update_failed_hold" if failed else "stale_odometry_hold" if stale else "source_odometry_hold" if self.local else "dead_reckoning_degraded_geometry" if degraded else "filtered_odometry_anchor_hold",
                last_numerical_failure=self.last_failure.get(car),
                state_epoch_ns=None if self.local else self.anchor_ns[car],
                source_header_epoch_ns=int(row["header_epoch_ns"]), source_receive_epoch_ns=int(row["receive_epoch_ns"]),
                source_record_index=int(row["record_index"]), receipt_age_ns=age,
                measurement_age_ns=measurement_age,
                wall_xy_local_rank=rank, recent_wall_links=len(geometry), geometry_degraded=degraded,
                time_semantics="latest arrived source pose; header clock unmapped" if self.local else "pose at last odometry measurement time; held at publication")
        return out
