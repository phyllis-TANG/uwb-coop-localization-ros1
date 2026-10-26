#!/usr/bin/env python3
"""Independent field replay checks: hashes, exact as-of provenance, no false room poses."""
import argparse
import bisect
import csv
import json
import math
from pathlib import Path
import sys
import time

import replay


def verify_rows(estimates, source_rows, origin):
    by_car = {}
    for car in ("car1", "car2"):
        rows = sorted([r for r in source_rows if r["vehicle_id"] == car],
                      key=lambda r:(int(r["receive_epoch_ns"]),int(r["record_index"])))
        by_car[car] = (rows, [int(r["receive_epoch_ns"]) for r in rows])
    counts = {"rows":0, "source_pose_rows_verified":0, "blocked_rows_verified":0, "valid_source_rows":0}
    tick_counts = {}
    for e in estimates:
        counts["rows"] += 1
        tick = int(e["publish_receive_epoch_ns"])
        assert float(e["canonical_time_s"]) == (tick-origin)/1e9, "canonical receipt arithmetic"
        assert e["z_m"] in (None,""), "unestimated z must be empty"
        tick_counts[tick] = tick_counts.get(tick,0)+1
        if e["method_id"] != "odom_only":
            assert e["x_m"] in (None,"") and e["y_m"] in (None,"") and e["yaw_rad"] in (None,""), "blocked room pose was fabricated"
            assert str(e["valid"]) == "0" and e["fallback_status"] == "BLOCKED", "room method must remain blocked"
            counts["blocked_rows_verified"] += 1
            continue
        car = e["vehicle_id"]
        assert e["frame_id"] == car+"/odom", "source frame changed"
        assert e["state_epoch_ns"] in (None,""), "unmapped source clock was presented as master time"
        rows,receipts = by_car[car]
        index = bisect.bisect_right(receipts,tick)-1
        if index < 0:
            assert e["x_m"] in (None,"") and str(e["valid"]) == "0", "uninitialized pose must be null"
            continue
        r = rows[index]
        assert int(e["source_record_index"]) == int(r["record_index"]), "source record is not latest causal arrival"
        assert int(e["source_receive_epoch_ns"]) == int(r["receive_epoch_ns"]) <= tick, "future source admitted"
        assert int(e["source_header_epoch_ns"]) == int(r["header_epoch_ns"]), "header ns changed"
        assert float(e["x_m"]) == float(r["position_x"]), "source x changed"
        assert float(e["y_m"]) == float(r["position_y"]), "source y changed"
        x,y,z,w = [float(r["orientation_"+k]) for k in "xyzw"]
        yaw = math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        error = float(e["yaw_rad"])-yaw
        assert abs(math.atan2(math.sin(error),math.cos(error))) < 1e-12, "source yaw changed"
        counts["source_pose_rows_verified"] += 1
        counts["valid_source_rows"] += str(e["valid"]) == "1"
    assert tick_counts and all(n == 6 for n in tick_counts.values()), "each tick must preserve three methods/two vehicles"
    return counts


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--normalized",type=Path,required=True)
    p.add_argument("--results",type=Path,required=True,help="Directory containing T08/T10/T12/T14 runs")
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    started=time.monotonic();run=None
    try:
        config=Path(__file__).with_name("field_config.json")
        run=replay.create_run(args.output,config,[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        replay.verify_normalized(args.normalized)
        with (args.normalized/"odom.csv").open() as f:
            sources=[r for r in csv.DictReader(f) if r["experiment_id"] in replay.DEVELOPMENT]
        manifest=json.loads((replay.SESSION/"manifest.json").read_text())
        checks=[]
        for trial in sorted(replay.DEVELOPMENT):
            directory=args.results/trial
            state=json.loads((directory/"run.json").read_text())
            assert state["status"] == "BLOCKED", "field preconditions unexpectedly bypassed"
            for item in state["outputs"]:
                rel=Path(item["relative_path"])
                assert not rel.is_absolute() and ".." not in rel.parts
                assert replay.sha256(directory/rel) == item["sha256"], "run artifact hash changed"
            row=next(r for r in manifest["formal_bags"] if r["id"] == trial)
            with (directory/"estimate.csv").open() as f:
                counts=verify_rows(csv.DictReader(f),[r for r in sources if r["experiment_id"]==trial],row["first_bag_receive_epoch_ns"])
            counts["experiment_id"] = trial
            counts["run_sha256"] = replay.sha256(directory/"run.json")
            checks.append(counts)
            run["inputs"].append({"asset_id":"field_baseline_result","relative_path":trial+"/run.json","sha256":counts["run_sha256"]})
        replay.atomic_json(args.output/"verification.json",{"scope":"causal source replay and blocked-output integrity; no accuracy evaluation","checks":checks,"all_passed":True})
        replay.finish(args.output,run,"DONE",started)
        print(json.dumps(checks))
        return 0
    except (Exception,KeyboardInterrupt) as error:
        if run is not None:replay.finish(args.output,run,"FAILED",started,error)
        print("ERROR: "+str(error),file=sys.stderr)
        return 1


if __name__=="__main__":sys.exit(main())
