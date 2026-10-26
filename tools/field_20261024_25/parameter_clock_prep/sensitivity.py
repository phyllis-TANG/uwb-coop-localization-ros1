#!/usr/bin/env python3
"""Finite one-factor synthetic sensitivity sweep with frozen observations."""
import argparse
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

import interface
sys.path.insert(0,str(interface.BASELINE))
import replay
import synthetic_validation as synthetic

HERE=Path(__file__).resolve().parent
PROTOCOL=HERE/"sensitivity_protocol.json"


def minimal_synthetic_config():
    config=json.loads(synthetic.CONFIG.read_text())
    for cc in config["vehicles"].values():
        xyz=cc.pop("antenna_body_xyz_m");base=cc.pop("base_height_m")
        cc["antenna_body_xy_m"]=dict(xyz,value=xyz["value"][:2])
        cc["antenna_height_m"]=dict(xyz,value=base["value"]+xyz["value"][2])
    return config


def perturb(config,condition):
    result=copy.deepcopy(config)
    path=condition["path"]
    if path:
        node=result
        for key in path[:-1]:node=node[key]
        node[path[-1]]+=condition["delta"]
    return result


def changed_leaves(a,b,path=()):
    if isinstance(a,dict):
        return [p for k in a for p in changed_leaves(a[k],b[k],path+(k,))]
    if isinstance(a,list):
        return [p for k in range(len(a)) for p in changed_leaves(a[k],b[k],path+(k,))]
    return [path] if a!=b else []


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv);started=time.monotonic();run=None
    try:
        run=replay.create_run(args.output,PROTOCOL,[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        run["role"]="synthetic_parameter_sensitivity"
        run["source_sha256"].update({str(x.relative_to(replay.ROOT)):replay.sha256(x) for x in HERE.glob("*.py")})
        protocol=json.loads(PROTOCOL.read_text());base=minimal_synthetic_config()
        if protocol["seeds"]!=base["validation_protocol"]["seeds"]:raise ValueError("fixed seed protocol changed")
        replay.atomic_json(args.output/"protocol.json",protocol)
        summary=[]
        for seed in protocol["seeds"]:
            # Generated once; all conditions receive exactly the same events.
            events,truth,origin,end=synthetic.fixture(base,seed,protocol["scenario"])
            fingerprint=hashlib.sha256(json.dumps(sorted(events,key=replay.event_key),sort_keys=True,allow_nan=False).encode()).hexdigest()
            before=copy.deepcopy(events);reference=None
            for condition in protocol["conditions"]:
                config=perturb(base,condition)
                expected=[] if condition["path"] is None else [tuple(condition["path"])]
                if changed_leaves(base,config)!=expected:raise ValueError("non-isolated parameter perturbation")
                case=args.output/("seed_"+str(seed)+"_"+condition["id"])
                case.mkdir()
                child=copy.deepcopy(run);child.update(run_id=case.name,role="synthetic_sensitivity_case",publications_completed=0,
                    inputs=[{"asset_id":"fixed_synthetic_observations","relative_path":"seed_"+str(seed),"sha256":fingerprint}])
                replay.atomic_json(case/"run.json",child)
                case_started=time.monotonic()
                try:
                    diagnostics=replay.write_replay(case,events,config,"synthetic",origin,end,child,started+900)
                    with (case/"estimate.csv").open() as stream:rows=list(csv.DictReader(stream))
                    for row in rows:
                        row["valid"]=row["valid"]=="1"
                        for key in ("x_m","y_m","yaw_rad"):row[key]=float(row[key]) if row[key] else None
                        row["state_epoch_ns"]=int(row["state_epoch_ns"]) if row["state_epoch_ns"] else None
                        row["pose_covariance"]=json.loads(row["pose_covariance"]) if row["pose_covariance"] else None
                    if reference is None:reference=copy.deepcopy(rows)
                    for ref,row in zip(reference,rows):
                        if row["method_id"]=="independent" and row["vehicle_id"]=="car1":
                            if [ref[k] for k in ("x_m","y_m","yaw_rad","pose_covariance")] != [row[k] for k in ("x_m","y_m","yaw_rad","pose_covariance")]:
                                raise ValueError("cross-vehicle isolation failed")
                        if condition["id"].startswith(("uwb_clock","lever")) and row["method_id"]=="odom_only":
                            if [ref[k] for k in ("x_m","y_m","yaw_rad")] != [row[k] for k in ("x_m","y_m","yaw_rad")]:
                                raise ValueError("range-only perturbation changed odometry baseline")
                    delta={m:[] for m in interface.model.METHODS}
                    for ref,row in zip(reference,rows):
                        if ref["valid"] and row["valid"]:
                            if ref["state_epoch_ns"]!=row["state_epoch_ns"]:raise ValueError("comparison state times differ")
                            delta[row["method_id"]].append(float(np.hypot(row["x_m"]-ref["x_m"],row["y_m"]-ref["y_m"])))
                    metrics=synthetic.evaluate(rows,truth)
                    record={"seed":seed,"condition":condition["id"],"changed_leaves":[list(p) for p in changed_leaves(base,config)],
                        "observation_sha256":fingerprint,"metrics_generated_truth_only":metrics,
                        "xy_change_from_reference_m":{m:{"rows":len(v),"rmse":float(np.sqrt(np.mean(np.square(v)))) if v else None,"max":max(v) if v else None} for m,v in delta.items()},
                        "event_status":{m:d["events"] for m,d in diagnostics["methods"].items()}}
                    replay.atomic_json(case/"sensitivity.json",record)
                    replay.finish(case,child,"DONE",case_started)
                except Exception as error:
                    replay.finish(case,child,"FAILED",case_started,error);raise
                summary.append(record)
                replay.atomic_json(args.output/"sensitivity_summary.json",{"scope":protocol["scope"],"runs":summary})
            if events!=before:raise ValueError("shared observation fixture was mutated")
            print("seed",seed,"seven isolated conditions complete; observation SHA",fingerprint,flush=True)
        if len(summary)!=protocol["run_count"]:raise ValueError("finite sweep incomplete")
        run["inputs"]=[{"asset_id":"synthetic_protocol","relative_path":PROTOCOL.name,"sha256":replay.sha256(PROTOCOL)}]
        run["limitations"]=[protocol["scope"],"base initial XY held fixed during lever/yaw changes","no new reliability strategy","no field replay"]
        replay.finish(args.output,run,"DONE",started)
        return 0
    except (Exception,KeyboardInterrupt) as error:
        if run is not None:replay.finish(args.output,run,"FAILED",started,error)
        print("ERROR: "+str(error),file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
