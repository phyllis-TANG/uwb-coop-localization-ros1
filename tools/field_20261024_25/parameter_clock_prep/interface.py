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


def derived_kind(items,neutral):
    """A derivation must not upgrade assumptions or hide synthetic inputs."""
    kinds=[item.get("source_kind","unspecified") for item in items]
    if "synthetic" in kinds:return "synthetic"
    if any("engineering" in k or "assumption" in k for k in kinds):return "engineering_assumption"
    return neutral


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
        source_kind=derived_kind([group,adjustment],"provided_clock_mapping"),
        input_source_kinds=[group.get("source_kind","unspecified"),adjustment.get("source_kind","unspecified")],
        valid_source_interval_ns=interval, sample_time_semantics=adjustment.get("semantics"))
    return output


def binding_ready(binding):
    return (binding.get("status") == "provided" and bool(binding.get("source"))
        and isinstance(binding.get("source_file_sha256"),str) and len(binding["source_file_sha256"])==64
        and all(c in "0123456789abcdef" for c in binding["source_file_sha256"])
        and all(isinstance(binding.get(k),int) and not isinstance(binding[k],bool) and binding[k]>=0 for k in ("record_index","header_epoch_ns","receive_epoch_ns")))


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
        if binding.get("status") == "provided":
            if not binding_ready(binding):raise ValueError("complete exact source-record binding required")
            if binding["source_file_sha256"] != template["source_bag_sha256"]:
                raise ValueError("initialization binding belongs to a different experiment bag")
        xy,yaw,lever = src["initial_antenna_xy_room_m"],src["initial_body_yaw_room_rad"],src["antenna_body_xy_m"]
        if all(provided(x) for x in (xy,yaw,lever)) and binding_ready(binding):
            p = np.asarray(xy["value"],dtype=float)
            arm = np.asarray(lever["value"],dtype=float)
            heading = float(yaw["value"])
            if p.shape!=(2,) or arm.shape!=(2,) or not np.isfinite(np.r_[p,arm,heading]).all():raise ValueError("invalid initial geometry")
            base = p-model.rotation(heading) @ arm
            cc["initial_room_pose"] = {"status":"provided","value":[float(base[0]),float(base[1]),model.wrap(heading)],
                "source":"derived: p_base=p_antenna-R(yaw)*lever_xy; "+xy["source"]+"; "+yaw["source"]+"; "+lever["source"],
                "source_kind":derived_kind([xy,yaw,lever],"derived_input"),
                "input_provenance":{"antenna_xy":copy.deepcopy(xy),"body_yaw":copy.deepcopy(yaw),"lever_xy":copy.deepcopy(lever)},
                "uncertainty_note":"PR46 engineering covariance retained; input uncertainty/correlation not newly calibrated"}
            cc["initial_record_binding"] = copy.deepcopy(binding)
            derived[car] = "base initial pose derived only from provided antenna XY, body yaw, XY lever and exact record binding"
        else:
            cc["initial_room_pose"]["source"] = "pending antenna XY/body yaw/XY lever/exact source-record binding; no nominal or endpoint substitution"
            derived[car] = "pending"
        for topic,field in (("odom","odom_clock"),("uwb","range_clock")):
            group_id = src.get("clock_group_ids",{}).get(topic) or src.get("ros_clock_group_id")
            if group_id not in template["clock_groups"]:raise ValueError("explicit clock group required: "+car+":"+topic)
            group = template["clock_groups"][group_id]
            cc[field] = compile_clock(group, src["sample_time_adjustments"][topic],group_id)
    model.validate_config(config)
    return config, {"methods":model.readiness(config),"derived":derived,
        "minimal_geometry":["body-frame base-to-antenna XY","absolute antenna Z","initial antenna XY plus body yaw and source-record binding, or directly surveyed base pose"],
        "evaluation_only_pending":["accepted independent reference","reference space/time uncertainty and evaluation window"],
        "experiment_notes":template["experiment_notes"]}


def main(argv=None):
    import argparse
    import time
    import replay
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv);started=time.monotonic();run=None
    try:
        run=replay.create_run(args.output,args.template,[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        run["role"]="minimal_parameter_compilation"
        run["source_sha256"].update({str(p.relative_to(replay.ROOT)):replay.sha256(p) for p in Path(__file__).parent.glob("*.py")})
        run["config_sha256"]["baseline_field_config.json"]=replay.sha256(BASELINE/"field_config.json")
        run["inputs"]=[{"asset_id":"parameter_template","relative_path":args.template.name,"sha256":replay.sha256(args.template)}]
        config,ready=compile_template(json.loads(args.template.read_text()))
        replay.atomic_json(args.output/"baseline_config.json",config)
        replay.atomic_json(args.output/"readiness.json",ready)
        run["blocked_reasons"]=sorted({reason for method in ready["methods"].values() for reasons in method.values() for reason in reasons})
        status="BLOCKED" if run["blocked_reasons"] else "DONE"
        replay.finish(args.output,run,status,started)
        return 2 if status=="BLOCKED" else 0
    except (Exception,KeyboardInterrupt) as error:
        if run is not None:replay.finish(args.output,run,"FAILED",started,error)
        print("ERROR: "+str(error),file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
