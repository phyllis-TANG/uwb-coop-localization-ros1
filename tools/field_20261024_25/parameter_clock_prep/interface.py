"""Compile documented minimal inputs to the existing PR46 baseline interface.

Compilation is not calibration. Pending values remain pending, with no implicit
zero lever arm, zero clock offset, nominal start, or synthetic parameter reuse.
"""
import copy
import json
from pathlib import Path
import sys

import numpy as np

BASELINE = Path(__file__).resolve().parents[1]/"causal_baselines"
sys.path.insert(0, str(BASELINE))
import model

DEVELOPMENT = ("T08", "T10", "T12", "T14")


def provided(value):
    return model.known(value)


def compile_clock(group, adjustment, source_id):
    """sample_master_ns = affine(header_host_ns) + signed sample offset.

    Uncertainty fields are declared absolute bounds; add them conservatively,
    without assuming independent errors or inferring delay from receipt data.
    """
    output = {"status":"pending", "field":"header_epoch_ns", "source_origin_ns":None,
        "destination_origin_ns":None, "rate_numerator":None, "rate_denominator":None,
        "uncertainty_ns":None, "source_clock_id":source_id,
        "destination_clock_id":"bag_receive_epoch_ns",
        "source":"host mapping and publication-to-sample adjustment not both provided"}
    if group.get("status") != "provided" or adjustment.get("status") != "provided":return output
    integers = ("source_origin_ns", "destination_origin_ns", "rate_numerator", "rate_denominator", "uncertainty_ns")
    for key in integers:
        if not isinstance(group.get(key), int) or isinstance(group[key], bool):raise ValueError("integer host clock required: "+key)
    for key in ("offset_ns", "uncertainty_ns"):
        if not isinstance(adjustment.get(key), int) or isinstance(adjustment[key], bool):raise ValueError("integer sample adjustment required: "+key)
    if min(group["rate_numerator"],group["rate_denominator"]) <= 0 or min(group["uncertainty_ns"],adjustment["uncertainty_ns"]) < 0:
        raise ValueError("invalid clock rate or uncertainty")
    interval = group.get("valid_source_interval_ns")
    if not isinstance(interval,list) or len(interval)!=2 or not all(isinstance(x,int) for x in interval) or interval[0]>interval[1]:
        raise ValueError("provided host mapping needs explicit valid source interval")
    if not group.get("source") or not adjustment.get("source"):raise ValueError("clock evidence source required")
    output.update({k:group[k] for k in integers})
    output.update(status="provided", destination_origin_ns=group["destination_origin_ns"]+adjustment["offset_ns"],
        uncertainty_ns=group["uncertainty_ns"]+adjustment["uncertainty_ns"],
        source=group["source"]+"; "+adjustment["source"], source_clock_id=source_id,
        source_kind="synthetic" if "synthetic" in (group.get("source_kind"),adjustment.get("source_kind")) else "documented_calibration",
        valid_source_interval_ns=interval, sample_time_semantics=adjustment.get("semantics"))
    return output


def binding_ready(binding):
    return (binding.get("status") == "provided" and bool(binding.get("source"))
        and isinstance(binding.get("source_file_sha256"),str) and len(binding["source_file_sha256"])==64
        and all(isinstance(binding.get(k),int) and not isinstance(binding[k],bool) for k in ("record_index","header_epoch_ns","receive_epoch_ns")))


def compile_template(template):
    if template.get("schema_version") != 1 or template["experiment_id"] not in DEVELOPMENT:
        raise ValueError("development-only input template required")
    config = json.loads((BASELINE/"field_config.json").read_text())
    config["experiment_notes"] = {template["experiment_id"]:template["experiment_notes"]}
    derived = {}
    for car in model.CARS:
        src, cc = template["vehicles"][car], config["vehicles"][car]
        # Deliberately do not synthesize a Z lever or a base height.
        cc.pop("antenna_body_xyz_m")
        cc.pop("base_height_m")
        cc["antenna_body_xy_m"] = copy.deepcopy(src["antenna_body_xy_m"])
        cc["antenna_height_m"] = copy.deepcopy(src["antenna_height_m"])
        binding = src["initial_record_binding"]
        xy,yaw,lever = src["initial_antenna_xy_room_m"],src["initial_body_yaw_room_rad"],src["antenna_body_xy_m"]
        if all(provided(x) for x in (xy,yaw,lever)) and binding_ready(binding):
            p = np.asarray(xy["value"],dtype=float)
            arm = np.asarray(lever["value"],dtype=float)
            heading = float(yaw["value"])
            if p.shape!=(2,) or arm.shape!=(2,) or not np.isfinite(np.r_[p,arm,heading]).all():raise ValueError("invalid initial geometry")
            base = p-model.rotation(heading) @ arm
            cc["initial_room_pose"] = {"status":"provided","value":[float(base[0]),float(base[1]),model.wrap(heading)],
                "source":"derived: p_base=p_antenna-R(yaw)*lever_xy; "+xy["source"]+"; "+yaw["source"]+"; "+lever["source"],
                "source_kind":"derived_record", "uncertainty_note":"PR46 engineering covariance retained; input uncertainty/correlation not newly calibrated"}
            cc["initial_record_binding"] = copy.deepcopy(binding)
            derived[car] = "base initial pose derived only from provided antenna XY, body yaw, XY lever and exact record binding"
        else:
            cc["initial_room_pose"]["source"] = "pending antenna XY/body yaw/XY lever/exact source-record binding; no nominal or endpoint substitution"
            derived[car] = "pending"
        group = template["clock_groups"][src["ros_clock_group_id"]]
        for topic,field in (("odom","odom_clock"),("uwb","range_clock")):
            cc[field] = compile_clock(group, src["sample_time_adjustments"][topic],src["ros_clock_group_id"])
    model.validate_config(config)
    return config, {"methods":model.readiness(config),"derived":derived,
        "minimal_geometry":["body-frame base-to-antenna XY","absolute antenna Z","initial antenna XY plus body yaw and source-record binding, or directly surveyed base pose"],
        "evaluation_only_pending":["accepted independent reference","reference space/time uncertainty and evaluation window"],
        "experiment_notes":template["experiment_notes"]}
