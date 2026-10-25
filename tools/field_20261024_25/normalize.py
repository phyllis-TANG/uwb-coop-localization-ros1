#!/usr/bin/env python3
"""Loss-preserving field observations and clock diagnostics; no ROS or estimation.

Raw and bridge entries both remain traceable, but only raw is primary. Canonical
time is explicitly bag *arrival* relative to the first record, not synchronized
measurement time. All epoch arithmetic is integer arithmetic before conversion.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import csv
import datetime as dt
import json
import math
from pathlib import Path
import subprocess
import sys
import time

import audit_bags as audit
import bag_decoder as bag
import prepare
from run_nightly import atomic_json, git_info, sha256

ROOT = Path(__file__).resolve().parents[2]
SESSION = ROOT / "docs/field_tests/20261024_25"
TAGS = {"car1": "node_1", "car2": "node_0"}
WALLS = {"node_2", "node_3", "node_8", "node_10"}
COMMON = ["experiment_id", "vehicle_id", "source_asset_id", "source_file_sha256",
          "topic", "record_index", "header_seq", "frame_id", "receive_epoch_ns",
          "header_epoch_ns", "time_mapping_id", "canonical_time_s"]
COLUMNS = {
    "ranges": COMMON + ["source", "link_index", "device_local_time_ms", "device_system_time_ms",
        "device_clock_id", "device_local_time_encoding", "tag_id", "target_id", "link_kind",
        "range_m", "range_status", "fp_rssi_db", "rx_rssi_db", "quality", "quality_status",
        "raw_frame_id", "bridge_frame_id", "pairing_status", "primary_observation", "valid", "invalid_reason"],
    "frames": COMMON + ["source", "frame_observation_id", "raw_sequence", "tag_id", "entry_count",
        "missing_target_ids", "duplicate_target_ids", "raw_frame_id", "bridge_frame_id", "pairing_status",
        "device_local_time_ms", "device_system_time_ms", "device_clock_id", "device_local_time_encoding"],
    "odom": COMMON + ["child_frame_id", "position_x", "position_y", "position_z",
        "position_z_semantics", "orientation_x", "orientation_y", "orientation_z", "orientation_w",
        "linear_x", "linear_y", "linear_z", "angular_x", "angular_y", "angular_z",
        "pose_covariance", "twist_covariance", "nonfinite_fields"],
    "imu": COMMON + ["orientation_x", "orientation_y", "orientation_z", "orientation_w",
        "angular_velocity_x", "angular_velocity_y", "angular_velocity_z", "linear_acceleration_x",
        "linear_acceleration_y", "linear_acceleration_z", "orientation_covariance",
        "angular_velocity_covariance", "linear_acceleration_covariance", "nonfinite_fields"],
    "commands": COMMON + ["linear_x", "linear_y", "linear_z", "angular_x", "angular_y", "angular_z", "nonfinite_fields"],
}


def finite(value):
    return value if value is not None and math.isfinite(value) else None


def unsigned(value, bits):
    bag.require(isinstance(value, int) and 0 <= value < 2**bits, "invalid unsigned device time")
    return value


def device_diagnostics(values, bits):
    delta = [int(b)-int(a) for a,b in zip(values, values[1:])]
    wraps = sum(a > .9*2**bits and b < .1*2**bits for a,b in zip(values, values[1:]))
    return {"encoding_bits": bits, "raw_delta_ms": bag.stats(delta),
            "nonpositive": sum(d <= 0 for d in delta), "possible_wraps": wraps,
            "reset_or_reorder_candidates": sum(d < 0 for d in delta)-wraps,
            "automatic_unwrap_applied": False, "epoch_mapping": None,
            "epoch_mapping_reason": "device and ROS clocks are not calibrated"}


def interval_diagnostics(values):
    delta = [int(b)-int(a) for a,b in zip(values, values[1:])]
    return {"delta_ns": bag.stats(delta), "backwards": sum(d < 0 for d in delta),
            "duplicates": sum(d == 0 for d in delta), "gaps_over_100ms": sum(d>100_000_000 for d in delta)}


def flatten_numeric(result, prefix, value):
    if isinstance(value, dict):
        for key, item in value.items():
            flatten_numeric(result, prefix + "_" + key if prefix else key, item)
    elif isinstance(value, list):
        result[prefix] = [finite(v) for v in value]
    else:
        result[prefix] = finite(value)


def convert(records, experiment, input_hash, origin):
    """records: (original bag record index, receipt int ns, topic, decoded message).

    This is the single conversion path used by the CLI and behavioral fixtures.
    It never interpolates, adjusts clocks, aligns room frames, or replaces NaNs.
    """
    tables = {name: [] for name in COLUMNS}
    timings = defaultdict(list)
    by_key = defaultdict(lambda: {"raw": [], "bridge": []})
    for index, receive, topic, original in records:
        parts = topic.split("/")
        if len(parts)<3 or parts[1] not in TAGS:
            continue
        car = parts[1]
        source = ("raw" if topic.endswith(("/uwb/frame3", "/nlink_linktrack_nodeframe3"))
                  else "bridge" if topic.endswith("/uwb/ranges") else None)
        message = audit.validate_frame3(original["data"]) if topic.endswith("/uwb/frame3") else original
        h = audit.rawstamp(message) if topic.endswith("/uwb/frame3") else bag.stamp(message) if "header" in message else None
        header = message.get("header", {})
        common = dict(experiment_id=experiment, vehicle_id=car, source_asset_id="bags",
            source_file_sha256=input_hash, topic=topic, record_index=index,
            header_seq=header.get("seq"), frame_id=header.get("frame_id",message.get("frame_id")),
            receive_epoch_ns=int(receive), header_epoch_ns=h,
            time_mapping_id="bag_receive_origin_"+experiment, canonical_time_s=(int(receive)-int(origin))/1e9)
        timings[topic].append((int(receive), h))
        if source:
            frame = dict(common, source=source, frame_observation_id=f"{experiment}:{index}",
                         raw_sequence=message.get("sequence"))
            if source == "raw":
                c1 = car == "car1"
                frame.update(tag_id="node_"+str(message["node_id" if c1 else "id"]),
                    device_local_time_ms=unsigned(message["local_time_ms" if c1 else "local_time"],32 if c1 else 64),
                    device_system_time_ms=unsigned(message["system_time_ms" if c1 else "system_time"],32),
                    device_clock_id=experiment+":"+car+":device_unmapped",
                    device_local_time_encoding="packet_uint32" if c1 else "schema_uint64_packet_width_unverified")
                nodes = [dict(target_id="node_"+str(n["node_id" if c1 else "id"]),
                    range_m=n["distance_m" if c1 else "dis"], fp_rssi_db=n["fp_rssi_db" if c1 else "fp_rssi"],
                    rx_rssi_db=n["rx_rssi_db" if c1 else "rx_rssi"], quality=None) for n in message["nodes"]]
            else:
                frame.update(tag_id=message["tag_id"], device_local_time_ms=None, device_system_time_ms=None,
                             device_clock_id=None, device_local_time_encoding=None)
                nodes = [dict(target_id=n["anchor_id"],range_m=n["range"],quality=n["quality"],
                              fp_rssi_db=None,rx_rssi_db=None) for n in message["ranges"]]
            bag.require(frame["tag_id"]==TAGS[car],"topic/tag vehicle identity mismatch")
            counts = Counter(n["target_id"] for n in nodes)
            expected = WALLS | {TAGS["car2" if car=="car1" else "car1"]}
            frame.update(entry_count=len(nodes), missing_target_ids=sorted(expected-counts.keys()),
                         duplicate_target_ids=sorted(k for k,v in counts.items() if v>1))
            tables["frames"].append(frame)
            entries = []
            for li,node in enumerate(nodes):
                value = node["range_m"]
                valid = math.isfinite(value) and value>0
                why = "" if valid else "nonfinite_range" if not math.isfinite(value) else "nonpositive_range"
                r = dict(common,source=source,link_index=li,
                    **{k:frame[k] for k in ["tag_id","device_local_time_ms","device_system_time_ms","device_clock_id","device_local_time_encoding"]},
                    **{k:finite(v) if k!="target_id" else v for k,v in node.items()},
                    link_kind="wall" if node["target_id"] in WALLS else "peer" if node["target_id"] in expected else "unknown",
                    range_status=why or "finite_positive_unvalidated_accuracy",
                    quality_status="unavailable_in_raw" if source=="raw" else "nonfinite_unknown" if finite(node["quality"]) is None else "reported",
                    primary_observation=source=="raw",valid=valid,invalid_reason=why)
                entries.append(r)
                tables["ranges"].append(r)
            by_key[(car,h)][source].append((frame,entries))
        else:
            r = dict(common)
            if topic.endswith("/odom"):
                kind="odom"
                flatten_numeric(r,"",message["pose"]["pose"])
                flatten_numeric(r,"",message["twist"]["twist"])
                r.update(child_frame_id=message["child_frame_id"],
                    pose_covariance=[finite(v) for v in message["pose"]["covariance"]],
                    twist_covariance=[finite(v) for v in message["twist"]["covariance"]],
                    position_z_semantics="driver_yaw_related_not_height" if car=="car2" else "source_odom_z_not_antenna_height")
            elif topic.endswith("/imu"):
                kind="imu"
                for key,value in message.items():
                    if key!="header": flatten_numeric(r,key,value)
            elif topic.endswith("/cmd_vel"):
                kind="commands"
                flatten_numeric(r,"",message)
            else:
                continue
            r["nonfinite_fields"] = [k for k,v in r.items() if (v is None or isinstance(v,list) and None in v)
                                      and k not in COMMON]
            tables[kind].append(r)
    for sources in by_key.values():
        raw,bridge = sources["raw"],sources["bridge"]
        ambiguous = len(raw)>1 or len(bridge)>1
        status = "ambiguous_header" if ambiguous else "raw_only" if not bridge else "bridge_only" if not raw else "paired_equal"
        if status=="paired_equal":
            left,right=raw[0][1],bridge[0][1]
            # Match complete ordered entry lists, never collapse duplicate targets.
            equal=len(left)==len(right) and all(a["target_id"]==b["target_id"] and a["range_m"] is not None
                and b["range_m"] is not None and abs(a["range_m"]-b["range_m"])<=1e-7 for a,b in zip(left,right))
            if not equal:status="paired_mismatch"
        for source,items in sources.items():
            for f,entries in items:
                pair = {"raw_frame_id":raw[0][0]["frame_observation_id"] if len(raw)==1 else None,
                        "bridge_frame_id":bridge[0][0]["frame_observation_id"] if len(bridge)==1 else None,
                        "pairing_status":status}
                if ambiguous:
                    pair["raw_frame_id"] = f["frame_observation_id"] if source=="raw" else None
                    pair["bridge_frame_id"] = f["frame_observation_id"] if source=="bridge" else None
                f.update(pair)
                for r in entries:r.update(pair)
    diag={"origin_receive_epoch_ns":int(origin), "canonical_time_definition":"(receive_epoch_ns-origin_receive_epoch_ns)/1e9; arrival only",
          "topics":{},"devices":{}, "clock_policy":"No fixed delay, cross-device subtraction, automatic unwrap, or video mapping applied."}
    for topic,rows in timings.items():
        receive=[t for t,h in rows]
        headers=[h for t,h in rows if h is not None]
        differences=[t-h for t,h in rows if h is not None]
        diag["topics"][topic]={"messages":len(rows),"receive":interval_diagnostics(receive),
            "header":interval_diagnostics(headers), "receive_minus_header_ns":bag.stats(differences),
            "negative_receive_minus_header_count":sum(d<0 for d in differences),
            "difference_interpretation":"diagnostic only; header host clock relationship uncalibrated"}
    for car in TAGS:
        frames=[f for f in tables["frames"] if f["vehicle_id"]==car and f["source"]=="raw"]
        diag["devices"][car]={key:device_diagnostics([f["device_"+key+"_time_ms"] for f in frames],bits)
            for key,bits in [("local",32 if car=="car1" else 64),("system",32)]}
    return tables,diag


def csv_value(value):
    if isinstance(value,(list,dict)):return json.dumps(value,allow_nan=False,separators=(",",":"))
    if isinstance(value,bool):return int(value)
    return value


def write_table(path, rows, columns):
    with Path(path).open("x",newline="",encoding="utf-8") as stream:
        w=csv.DictWriter(stream,fieldnames=columns,extrasaction="raise")
        w.writeheader()
        for row in rows:w.writerow({k:csv_value(row.get(k)) for k in columns})


def new_run(output, role, configs, argv):
    """Exclusive output creation doubles as run ownership; never steal old locks."""
    output=prepare.validate_data_root(output)
    output.mkdir(parents=True,exist_ok=False)
    git=git_info()
    sources={str(p.relative_to(ROOT)):sha256(p) for p in sorted(Path(__file__).parent.glob("*.py"))}
    packages=subprocess.run([sys.executable,"-m","pip","freeze"],capture_output=True,text=True,check=True).stdout
    (output/"python_packages.txt").write_text(packages)
    run={"schema_version":1,"run_id":output.name,"role":role,"status":"IN_PROGRESS",
         "created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"code_commit":git["head"],
         "branch":git["branch"],"worktree_dirty":bool(git["status_porcelain"]),"source_sha256":sources,
         "config_sha256":{p.name:sha256(p) for p in configs},"inputs":[],"command_argv":argv,
         "environment":{"python":sys.version,"packages_file":"python_packages.txt"},
         "outputs":[],"blocked_reasons":[],"limitations":[],"completed_experiments":[]}
    atomic_json(output/"run.json",run)
    return run


def finish_run(output,run,status,started,error=None):
    run.update(status=status,elapsed_s=time.monotonic()-started,
               finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    if error:run["error"]=str(error)
    run["outputs"]=[{"relative_path":str(p.relative_to(output)),"sha256":sha256(p)}
                    for p in sorted(output.rglob("*")) if p.is_file() and p.name!="run.json"]
    atomic_json(output/"run.json",run)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    started=time.monotonic()
    run=None
    try:
        run=new_run(args.output,"sandbox_normalization",[SESSION/"manifest.json",SESSION/"geometry.json"],
                    [sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        manifest,_=__import__("run_nightly").validate_configuration()
        planned=audit.input_plan(args.data_root,manifest)
        run["inputs"]=[{"asset_id":"bags","experiment_id":r["id"],"relative_path":r["relative_path"],"sha256":h} for r,p,h in planned]
        atomic_json(args.output/"run.json",run)
        counts={}
        diagnostics={"schema_version":1,"experiments":{}}
        with ExitStack() as stack:
            writers={}
            for kind,columns in COLUMNS.items():
                stream=stack.enter_context((args.output/(kind+".csv")).open("x",newline="",encoding="utf-8"))
                writers[kind]=csv.DictWriter(stream,fieldnames=columns)
                writers[kind].writeheader()
            for row,path,h in planned:
                print("Normalize "+row["id"],flush=True)
                connections,raw=bag.load_bag(path)
                bag.require(len(raw)==row["expected_messages"],"message count mismatch")
                dec={i:bag.Decoder(c["type"],c["definition"]) for i,c in connections.items()}
                records=[(index,t,connections[i]["topic"],dec[i].decode(blob,connections[i]["type"])) for index,(i,t,blob) in enumerate(raw)]
                origin=min(t for i,t,blob in raw)
                tables,diag=convert(records,row["id"],h,origin)
                actual=Counter(topic for i,t,topic,msg in records)
                bag.require(dict(actual)==row["topic_message_counts"],"topic counts mismatch")
                # Reconcile every source frame/entry before releasing the checkpoint.
                for kind in ("odom","imu","commands"):
                    suffix="/cmd_vel" if kind=="commands" else "/"+kind
                    bag.require(len(tables[kind])==sum(n for t,n in actual.items() if t.endswith(suffix)),"export count mismatch: "+kind)
                for kind,entries in tables.items():
                    for entry in entries:writers[kind].writerow({k:csv_value(entry.get(k)) for k in COLUMNS[kind]})
                counts[row["id"]]={k:len(v) for k,v in tables.items()}
                counts[row["id"]].update(decoded_messages=len(raw),range_primary=sum(r["primary_observation"] for r in tables["ranges"]),
                    pairing=dict(Counter(f["pairing_status"] for f in tables["frames"])),
                    empty_frames=sum(f["entry_count"]==0 for f in tables["frames"]),
                    invalid_entries=sum(not r["valid"] for r in tables["ranges"]),
                    range_entry_reconciliation="one output row per raw/bridge input entry; empty frames in frames.csv")
                diag["split"]=row["split"]
                diagnostics["experiments"][row["id"]]=diag
                run["completed_experiments"].append(row["id"])
                atomic_json(args.output/"counts.json",counts)
                atomic_json(args.output/"time_diagnostics.json",diagnostics)
                atomic_json(args.output/"run.json",run)
        report=["# 标准化观测验收", "", "八包只做格式/时间/健康检查，留出划分保持不变。无定位误差计算。", "",
            "| 包 | ranges | frames | odom | imu | commands |", "|---|---:|---:|---:|---:|---:|"]
        for trial,c in counts.items():report.append("| "+trial+" | "+" | ".join(str(c[k]) for k in COLUMNS)+" |")
        report += ["", "所有 epoch ns 保持整数；record_index 是原 bag 消息记录顺序（0起），不是按时间重排的序号。",
            "每个 raw 和 bridge 距离条目保留一行，精确 header+车辆配对。primary_observation=1 仅用于 raw；bridge 从不重复计入。",
            "frames.csv 保留空帧、缺目标和重复目标。距离非有限写空并给原因；非正有限原值保留且 valid=0。",
            "quality=NaN 写空并标 unknown。SI 单位沿原 schema；Car1 packet 24-bit signed mm 已由校验器核对并转 m。",
            "Car1 时间为 packet uint32；Car2 local_time 按嵌入 uint64 原值保存，packet 宽度未独立验证，不做符号重释。",
            "Car2 odom.z 原值保留，标 driver_yaw_related_not_height。协方差原数组保留，非有限项用 null 并列字段名。",
            "canonical_time_s 仅为同包首条接收时刻起算的到达时间；不是跨车采样同步。设备/视频没有经验证时间映射。",
            "receive-header 仅作未校准时钟诊断，不解释为网络延迟；不作固定延迟修正，不从接收间隔断言无线掉包。",
            "每表计数和逐包输入核对在 counts.json，时钟重置/回绕候选在 time_diagnostics.json；不插值或删去异常。",
            "CSV 数组列为严格 JSON，空数值为空字符串；JSON 不输出 NaN/Infinity。", ""]
        (args.output/"normalization_report.md").write_text("\n".join(report),encoding="utf-8")
        finish_run(args.output,run,"DONE",started)
        return 0
    except (Exception,KeyboardInterrupt) as error:
        if run is not None:finish_run(args.output,run,"FAILED",started,error)
        print("ERROR: "+str(error),file=sys.stderr)
        return 2


if __name__=="__main__":sys.exit(main())
