"""Online-only identity/time/correlation policy, separate from simulation truth."""
from collections import Counter
import math

TAGS = {"car1": "node_1", "car2": "node_0"}
CARS = tuple(TAGS)
WALLS = {"node_2", "node_3", "node_8", "node_10"}


class Admission:
    def __init__(self, config):
        self.config = config
        self.seen = set()
        self.used_peer_bins = set()
        self.last = -1
        self.counts = Counter()

    def take(self, now_ns, arrived):
        if type(now_ns) is not int or now_ns < self.last:
            raise ValueError("cutoff must be monotonic integer ns")
        self.last = now_ns
        walls, groups, trace = {}, {}, []
        for r in sorted(arrived, key=lambda r: (r["receive_ns"], r["record_index"])):
            reason = None
            car, target = r["vehicle_id"], r["target_id"]
            key = (car, r["record_index"], r["link_index"])
            if type(r["sample_ns"]) is not int or type(r["receive_ns"]) is not int:
                raise ValueError("timestamps must be integer ns")
            if r["receive_ns"] > now_ns:
                raise ValueError("caller supplied an observation that has not arrived")
            if car not in TAGS or r["tag_id"] != TAGS[car]:
                reason = "identity"
            elif target not in WALLS | {TAGS[CARS[1-CARS.index(car)]]}:
                reason = "target_identity"
            elif r["clock_mapping_id"] != "synthetic_exact_v1":
                reason = "unvalidated_measurement_clock"
            elif r["source"] != "raw" or not r["primary_observation"] or not r["valid"]:
                reason = "not_primary_valid_raw"
            elif key in self.seen:
                reason = "duplicate"
            elif not math.isfinite(r["range_m"]) or r["range_m"] <= 0:
                reason = "invalid_range"
            elif r["sample_ns"] > r["receive_ns"] or r["sample_ns"] > now_ns:
                reason = "future_sample"
            elif now_ns-r["sample_ns"] > self.config["max_age_ns"]:
                reason = "stale_sample"
            self.seen.add(key)
            if reason:
                self.counts[reason] += 1
                trace.append({"record_index": r["record_index"], "vehicle_id": car, "reason": reason})
                continue
            if target in WALLS:
                k = (car, target)
                if k in walls:
                    self.counts["wall_superseded"] += 1
                if k not in walls or r["sample_ns"] > walls[k]["sample_ns"]:
                    walls[k] = r
            else:
                width = self.config["correlation_bin_ns"]
                b = (r["sample_ns"] + width//2)//width
                # One unordered pair only in this two-vehicle interface. The bin
                # persists across calls, including late reciprocal observations.
                if b in self.used_peer_bins:
                    self.counts["correlated_late_suppressed"] += 1
                    trace.append({"record_index": r["record_index"], "vehicle_id": car,
                                  "reason": "correlated_late_suppressed"})
                else:
                    groups.setdefault(b, []).append(r)
        peers = []
        for b, rows in sorted(groups.items()):
            preferred = CARS[b % 2]
            selected = min(rows, key=lambda r: (r["vehicle_id"] != preferred,
                                               -r["sample_ns"], r["record_index"]))
            peers.append(selected)
            self.used_peer_bins.add(b)
            self.counts["correlated_same_call_suppressed"] += len(rows)-1
            for r in rows:
                trace.append({"record_index": r["record_index"], "vehicle_id": r["vehicle_id"],
                              "sample_ns": r["sample_ns"], "receive_ns": r["receive_ns"],
                              "reason": "selected" if r is selected else "correlated_same_call_suppressed"})
        self.counts["peer_factors"] += len(peers)
        self.counts["wall_factors"] += len(walls)
        return list(walls.values()), peers, trace


class Gate:
    """Per-direction innovation quarantine; no fault labels or future inputs."""
    def __init__(self, config):
        self.config = config
        self.state = {c: {"bad": 0, "good": 0, "closed": False} for c in CARS}

    def admit(self, car, z):
        s = self.state[car]
        if abs(z) > self.config["gate_z"]:
            s["bad"] += 1
            s["good"] = 0
            if s["bad"] >= self.config["quarantine_bad_count"]:
                s["closed"] = True
            return False
        s["bad"] = 0
        s["good"] += 1
        if s["closed"] and s["good"] >= self.config["reopen_good_count"]:
            s["closed"] = False
        return not s["closed"]
