#!/usr/bin/env python3
"""Compile frozen T10 evidence without opening a bag or promoting pending fields."""
import argparse
import json
from pathlib import Path
import sys

from io_utils import ROOT,dump,git_state,output_hashes,sha,utc
sys.path.append(str(Path(__file__).resolve().parents[1]/"parameter_clock_prep"))
from interface import compile_template

DEFAULT_TEMPLATE=Path(__file__).resolve().parents[1]/"parameter_clock_prep/results/T10_input_template.json"


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template",type=Path,default=DEFAULT_TEMPLATE);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists():raise FileExistsError(args.output)
    template=json.loads(args.template.read_text())
    if template["experiment_id"]!="T10":raise ValueError("this preflight is T10 only")
    config,ready=compile_template(template)
    missing=[]
    for car,vehicle in template["vehicles"].items():
        for name in ("antenna_body_xy_m","initial_antenna_xy_room_m","initial_body_yaw_room_rad","initial_record_binding"):
            item=vehicle[name]
            if item.get("status")!="provided":missing.append(dict(field="vehicles."+car+"."+name,status=item.get("status"),reason=item.get("source"),details=item))
        for topic,item in vehicle["sample_time_adjustments"].items():
            if item.get("status")!="provided":missing.append(dict(field="vehicles."+car+".sample_time_adjustments."+topic,status=item.get("status"),reason=item.get("source"),details=item))
    for group,item in template["clock_groups"].items():
        if item.get("status")!="provided":missing.append(dict(field="clock_groups."+group,status=item.get("status"),reason=item.get("source"),details=item))
    blockers=sorted({reason for methods in ready["methods"].values() for values in methods.values() for reason in values})
    args.output.mkdir(parents=True);dump(args.output/"strict_baseline_config.json",config);dump(args.output/"readiness.json",ready)
    decision=dict(schema_version=1,status="BLOCKED" if blockers else "DONE",**git_state(),created_at_utc=utc(),
        source_template_sha256=sha(args.template),source_template_relative_path=str(args.template.relative_to(ROOT)) if args.template.is_relative_to(ROOT) else args.template.name,
        source_bag_sha256=template["source_bag_sha256"],bag_read=False,room_localization_executed=False,field_accuracy_evaluation_executed=False,
        blocked_fields=missing,baseline_blockers=blockers,
        B_handoff_status="not present in frozen starting checkout; no waiting or assumption substitution",
        known_heights={car:template["vehicles"][car]["antenna_height_m"] for car in ("car1","car2")},
        reference_scope="not_accepted",actual_field_ATE_RMSE=None,
        next_step="B supplies traceable initial pose/record binding, horizontal lever and clock/sample models; compile a new config, then call same Candidate/process event interface",
        existing_strict_three_baseline_command=[sys.executable,"tools/field_20261024_25/causal_baselines/replay.py","--normalized","<verified_normalized_root>","--config","strict_baseline_config.json","--experiment","T10","--output","<new_external_output>"],
        limitations=["first-arrived odom candidates are provenance, not approved initial records","no assumption config created","holdout bags not opened"])
    dump(args.output/"decision.json",decision)
    dump(args.output/"run.json",dict(schema_version=1,role="A_T10_readiness",status=decision["status"],**git_state(),created_at_utc=utc(),
        source_sha256={str(Path(__file__).relative_to(ROOT)):sha(__file__),"tools/field_20261024_25/parameter_clock_prep/interface.py":sha(Path(__file__).resolve().parents[1]/"parameter_clock_prep/interface.py")},
        inputs=[dict(asset_id="T10_existing_parameter_template",relative_path=str(args.template.relative_to(ROOT)) if args.template.is_relative_to(ROOT) else args.template.name,sha256=sha(args.template))],outputs=output_hashes(args.output),blocked_reasons=blockers,
        command_argv=[sys.executable,__file__]+(argv if argv is not None else sys.argv[1:])))
    print(json.dumps(dict(status=decision["status"],missing_parameter_groups=len(missing),baseline_blockers=blockers)))
    return 2 if blockers else 0


if __name__=="__main__":sys.exit(main())
