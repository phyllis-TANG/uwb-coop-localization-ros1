#!/usr/bin/env python3
"""Read-only parameter/clock evidence audit and pending configuration preparation.

No estimator is run. Only the four development bags' normalized records are
summarized; clock distributions describe recorded stamps, never calibrated delay.
"""
import argparse
from bisect import bisect_left
from collections import defaultdict
import copy
import csv
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import time

import numpy as np

import interface
sys.path.insert(0,str(interface.BASELINE))
import replay

HERE=Path(__file__).resolve().parent
CONTRACT=HERE/"interface_contract.json"


def stats(values):
    if not values:return {"n":0}
    x=np.asarray(values,dtype=float)
    return {"n":len(values),"min":float(x.min()),"median":float(np.median(x)),"p05":float(np.quantile(x,.05)),"p95":float(np.quantile(x,.95)),"max":float(x.max())}


def pending(source,candidates=None):
    return {"status":"pending","value":None,"source":source,"source_kind":"unknown",
            "uncertainty":None,"uncertainty_reason":"not independently measured", "candidate_records":candidates or []}


def templates(geometry,manifest,first_odom):
    out={}
    candidate={"T08":{"car1":[1.5,4.,-np.pi/2],"car2":[2.,2.,np.pi/2]},
        "T10":{"car1":[1.5,4.,-np.pi/2],"car2":[2.98,3.07,None]},
        "T12":{"car1":[None,None,0.],"car2":[None,None,np.pi/2]},
        "T14":{"car1":[1.5,4.,-np.pi/2],"car2":[2.,2.,np.pi/2]}}
    for trial in interface.DEVELOPMENT:
        bag=next(r for r in manifest["formal_bags"] if r["id"]==trial)
        t={"schema_version":1,"experiment_id":trial,"source_bag_sha256":bag["sha256"],"vehicles":{},"clock_groups":{},
            "experiment_notes":["initial XY/headings below are candidate records, not per-bag surveyed starts", "T12 actual initial XY unknown; no T13/endpoint substitution"] if trial=="T12" else ["confirm actual first-pose placement and heading; do not promote nominal guidance to measurement"]}
        for car in interface.model.CARS:
            c=candidate[trial][car]
            label="carried T09 manual endpoint plus assumed unchanged placement; not newly measured T10 start" if trial=="T10" and car=="car2" else "nominal route guidance; actual per-bag confirmation pending"
            cc={"antenna_body_xy_m":pending("physical odometry/base origin to antenna XY not established"),
                "antenna_height_m":{"status":"provided","value":geometry["mounts"][car]["antenna_reference_height_m"],
                    "source":"geometry.json mounts."+car+".antenna_reference_height_m; SESSION_LOG_ARCHIVE.md section "+("54" if car=="car1" else "55"),
                    "source_kind":"operator_record","uncertainty_m":None,"uncertainty_reason":"operator approximate height; instrument uncertainty not reported",
                    "applicability":"same mounting state assumed; no per-run fresh Z survey"},
                "initial_antenna_xy_room_m":pending("actual start at bound source record pending",[{"value":c[:2],"classification":label}]),
                "initial_body_yaw_room_rad":pending("actual body heading at same bound source record pending",[{"value":c[2],"classification":"planned body heading; not marker orientation"}]),
                "initial_record_binding":{"status":"pending","source_file_sha256":bag["sha256"],"record_index":None,"header_epoch_ns":None,"receive_epoch_ns":None,
                    "source":"first accepted odometry record must be explicitly confirmed after clock-model validation",
                    "first_arrived_candidate":first_odom.get((trial,car)),
                    "video_trace":{"video_sha256":None,"frame_index":None,"pts_ticks":None,"time_base_num":None,"time_base_den":None,"time_mapping_id":None}},
                "ros_clock_group_id":car+"_ros_host","sample_time_adjustments":{}}
            for topic in ("odom","uwb"):
                cc["sample_time_adjustments"][topic]={"status":"pending","offset_ns":None,"uncertainty_ns":None,"semantics":None,
                    "source":"sampling-to-header relation not calibrated; no receipt-header median correction"}
            t["vehicles"][car]=cc
            t["clock_groups"][car+"_ros_host"]={"status":"pending","source_origin_ns":None,"destination_origin_ns":None,
                "rate_numerator":None,"rate_denominator":None,"uncertainty_ns":None,"valid_source_interval_ns":[None,None],
                "source":"host/recorder clock relation and ROS time mode pending; NTP status is not a millisecond bound",
                "source_kind":"unknown","deployment_grouping_status":"host grouping from session topology; per-node binary/time-mode confirmation still required"}
        out[trial]=t
    return out


def clock_audit(normalized):
    topic_rows=defaultdict(list);devices=defaultdict(list);pair=defaultdict(lambda:{"raw":set(),"bridge":set()});first={}
    pair_receipts=defaultdict(lambda:{"raw":{},"bridge":{}})
    for name in ("odom.csv","imu.csv","commands.csv","frames.csv"):
        with (normalized/name).open(newline="") as stream:
            for row in csv.DictReader(stream):
                trial=row["experiment_id"]
                if trial not in interface.DEVELOPMENT:continue
                car=row["vehicle_id"];receive=int(row["receive_epoch_ns"])
                header=int(row["header_epoch_ns"]) if row["header_epoch_ns"] else None
                key=(trial,car,row["topic"])
                topic_rows[key].append((receive,header))
                if name=="odom.csv":
                    identity={"record_index":int(row["record_index"]),"header_epoch_ns":header,"receive_epoch_ns":receive,
                        "topic":row["topic"],"source_file_sha256":row["source_file_sha256"]}
                    if (trial,car) not in first or receive<first[(trial,car)]["receive_epoch_ns"]:first[(trial,car)]=identity
                if name=="frames.csv":
                    pair[(trial,car)][row["source"]].add(header)
                    pair_receipts[(trial,car)][row["source"]].setdefault(header,receive)
                    if row["source"]=="raw":devices[(trial,car)].append((int(row["device_local_time_ms"]),int(row["device_system_time_ms"])))
    result={"scope":"four development bags only; stamp/source diagnostics, no replay or error evaluation","topics":[],"vehicles":[],
        "policy":"receive-header distributions mix host clock error and processing/transport; never fitted as delay","clock_mapping_status":"pending"}
    for (trial,car,topic),rows in sorted(topic_rows.items()):
        receives=[t for t,h in rows];headers=[h for t,h in rows if h is not None];offsets=[t-h for t,h in rows if h is not None]
        result["topics"].append({"experiment_id":trial,"vehicle_id":car,"topic":topic,"messages":len(rows),
            "receive_delta_ns":stats([b-a for a,b in zip(receives,receives[1:])]),
            "header_delta_ns":stats([b-a for a,b in zip(headers,headers[1:])]),
            "receive_minus_header_ns_diagnostic_only":stats(offsets),"negative_difference_count":sum(v<0 for v in offsets),
            "header_backwards":sum(b<a for a,b in zip(headers,headers[1:]))})
    for trial in interface.DEVELOPMENT:
        for car in interface.model.CARS:
            odom=sorted(h for t,h in topic_rows[(trial,car,"/"+car+"/odom")] if h is not None)
            imu=sorted(h for t,h in topic_rows[(trial,car,"/"+car+"/imu")] if h is not None)
            nearby=[]
            for h in imu:
                j=bisect_left(odom,h)
                candidates=odom[max(0,j-1):min(len(odom),j+1)]
                if candidates:
                    nearest=min(candidates,key=lambda t:abs(t-h))
                    if abs(h-nearest)<=25_000_000:nearby.append(h-nearest)
            frames=devices[(trial,car)];raw=pair[(trial,car)]["raw"];bridge=pair[(trial,car)]["bridge"]
            arrival_delta=[pair_receipts[(trial,car)]["bridge"][h]-pair_receipts[(trial,car)]["raw"][h] for h in raw&bridge]
            result["vehicles"].append({"experiment_id":trial,"vehicle_id":car,"raw_bridge_identical_header_frames":len(raw&bridge),
                "raw_only_header_frames":len(raw-bridge),"bridge_only_header_frames":len(bridge-raw),
                "device_system_delta_ms":stats([b[1]-a[1] for a,b in zip(frames,frames[1:])]),
                "device_local_delta_ms":stats([b[0]-a[0] for a,b in zip(frames,frames[1:])]),
                "bridge_minus_raw_receipt_ns_same_recorder":stats(arrival_delta),
                "receipt_pair_note":"same recorder clock arrival separation, not serial/radio acquisition delay",
                "imu_minus_nearest_odom_header_ns":stats(nearby),
                "nearest_header_pairing":"offline same-host descriptive nearest stamp within 25ms, not proof of common physical sample time"})
    return result,first


def source_audit(data_root,manifest,output):
    asset=next(a for a in manifest["assets"] if a["id"]=="bags")
    archive=data_root/"downloads"/asset["name"]
    if replay.sha256(archive)!=asset["sha256"]:raise ValueError("registered source archive hash mismatch")
    evidence_prefix="uwb_field_20261024/setup_evidence_20261024_030824/"
    names=["car1_uwb_raw_wrapper_v2.py","car1_clock.txt","car2_clock.txt","vm_clock.txt","car2_base_source.tar.gz","car1_uwb_source_20261024_044515.tar.gz","V550_mec_robot.urdf"]
    records=[];excerpts=[]
    with tarfile.open(archive) as outer:
        for name in names:
            blob=outer.extractfile(evidence_prefix+name).read()
            records.append({"relative_path":evidence_prefix+name,"sha256":hashlib.sha256(blob).hexdigest(),"bytes":len(blob)})
            if name.endswith(".txt") or name.endswith("wrapper_v2.py"):
                text=blob.decode("utf-8",errors="replace")
                for n,line in enumerate(text.splitlines(),1):
                    if name.endswith(".txt") or any(k in line for k in ("stamp","original_publisher.publish","raw_publisher.publish")):
                        excerpts.append({"source":evidence_prefix+name,"line":n,"text":line})
            if name.endswith(".tar.gz"):
                import io
                with tarfile.open(fileobj=io.BytesIO(blob)) as inner:
                    targets=["src/wheeltec_robot.cpp","CMakeLists.txt","launch/include/base_serial.launch"] if name.startswith("car2") else ["uwb_linktrack_driver.py"]
                    for member in targets:
                        content=inner.extractfile(member).read()
                        records.append({"relative_path":evidence_prefix+name+"!"+member,"sha256":hashlib.sha256(content).hexdigest(),"bytes":len(content)})
                        text=content.decode("utf-8",errors="replace").splitlines()
                        if member.endswith("wheeltec_robot.cpp"):spans=[(255,280),(287,311),(663,696)]
                        elif member=="uwb_linktrack_driver.py":spans=[(69,111)]
                        else:spans=[(1,len(text))]
                        for lo,hi in spans:
                            for n in range(lo,min(hi,len(text))+1):excerpts.append({"source":evidence_prefix+name+"!"+member,"line":n,"text":text[n-1]})
    bridge=replay.ROOT/"ros_ws/src/uwb_coop_localization/scripts/nlink_frame3_bridge.py"
    records.append({"relative_path":str(bridge.relative_to(replay.ROOT)),"sha256":replay.sha256(bridge),"deployment_match":"pending; source plus exact-header data supports bridge preservation, not nlink acquisition stamping"})
    replay.atomic_json(output/"source_evidence.json",{"registered_archive":asset,"files":records,"excerpts":excerpts,
        "limits":["Car2 vendor source not bound to running binary","Car1 base source and deployed nlink_parser source not found in registered archive","NTP snapshots are from Oct24, not dynamic Oct25 offset measurements"]})
    return records


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--normalized",type=Path,required=True)
    p.add_argument("--data-root",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv);started=time.monotonic();run=None
    try:
        run=replay.create_run(args.output,CONTRACT,[sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        run["role"]="parameter_clock_preparation"
        run["source_sha256"].update({str(x.relative_to(replay.ROOT)):replay.sha256(x) for x in HERE.glob("*.py")})
        receipt=replay.verify_normalized(args.normalized)
        manifest=json.loads((replay.SESSION/"manifest.json").read_text());geometry=json.loads((replay.SESSION/"geometry.json").read_text())
        run["inputs"]=[{"asset_id":"normalized","relative_path":"run.json","sha256":replay.sha256(args.normalized/"run.json")},*receipt["inputs"]]
        records=source_audit(args.data_root,manifest,args.output)
        result,first=clock_audit(args.normalized)
        replay.atomic_json(args.output/"clock_diagnostics.json",result)
        matrix={}
        for trial,t in templates(geometry,manifest,first).items():
            config,ready=interface.compile_template(t)
            replay.atomic_json(args.output/(trial+"_input_template.json"),t)
            replay.atomic_json(args.output/(trial+"_baseline_config.json"),config)
            matrix[trial]=ready
        replay.atomic_json(args.output/"readiness_matrix.json",matrix)
        run["source_records_verified"]=records
        run["limitations"]=["no field estimator replay performed","physical clock mappings remain pending","operator antenna heights retain unknown uncertainty","video/reliability files and processes untouched"]
        replay.finish(args.output,run,"DONE",started)
        return 0
    except (Exception,KeyboardInterrupt) as error:
        if run is not None:replay.finish(args.output,run,"FAILED",started,error)
        print("ERROR: "+str(error),file=sys.stderr);return 1


if __name__=="__main__":sys.exit(main())
