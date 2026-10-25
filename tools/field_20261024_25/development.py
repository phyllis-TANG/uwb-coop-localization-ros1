#!/usr/bin/env python3
"""Development-only directed range/arrival diagnostics, without truth or fitting."""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys
import time

import bag_decoder as bag
from normalize import SESSION, TAGS, WALLS, new_run, finish_run
from run_nightly import atomic_json, sha256

CONFIG=Path(__file__).with_name("development_config.json")
DEVELOPMENT={"T08","T10","T12","T14"}


def validate_trials(trials):
    if set(trials)!=DEVELOPMENT or len(trials)!=4:
        raise ValueError("only the four whole development bags are permitted")


def peer_asof(left,right,max_age):
    """One diagnostic pair per left sample; earlier right may be reused.

    Arrival-time proximity is not physical simultaneity. These pairs must never
    become independent same-time localization factors or bias-calibration data.
    """
    left,right=sorted(left),sorted(right)
    j=0
    latest=None
    out=[]
    for t,value in left:
        while j<len(right) and right[j][0]<=t:
            latest=right[j]
            j+=1
        if latest is not None and t-latest[0]<=max_age:
            out.append({"receive_epoch_ns":t,"other_receive_epoch_ns":latest[0],
                        "age_ns":t-latest[0],"car1_minus_car2_m":value-latest[1]})
    return out


def link_summary(rows,frames):
    rows=sorted(rows)
    return {"valid_entries":len(rows),"raw_frame_denominator":frames,
        "valid_frame_fraction":len(rows)/frames if frames else None,
        "distance_m":bag.stats([r[1] for r in rows]),
        "fp_rssi_db":bag.stats([r[2] for r in rows if r[2] is not None]),
        "rx_rssi_db":bag.stats([r[3] for r in rows if r[3] is not None]),
        "successive_range_delta_m":bag.stats([b[1]-a[1] for a,b in zip(rows,rows[1:])]),
        "valid_entry_gap_ns":bag.stats([b[0]-a[0] for a,b in zip(rows,rows[1:])])}


def arrival_summary(rows,config):
    # Input is original bag record order; preserve reordering candidates.
    d=[(b[0]-a[0],b[1]-a[1]) for a,b in zip(rows,rows[1:])]
    return {"raw_frames":len(rows),"receipt_delta_ns":bag.stats([r for r,h in d]),
        "header_delta_ns":bag.stats([h for r,h in d]),
        "batch_progress_pairs":sum(0<=r<=config["receipt_batch_max_gap_ns"] and h>=config["header_progress_min_ns"] for r,h in d),
        "large_receipt_small_header_pairs":sum(r>100_000_000 and 0<h<=30_000_000 for r,h in d),
        "interpretation":"arrival scheduling candidates; no RF-loss or fixed-delay inference"}


def verify_normalized(root):
    r=json.loads((root/"run.json").read_text())
    bag.require(r["status"]=="DONE" and r["role"]=="sandbox_normalization","normalization must be DONE")
    for item in r["outputs"]:
        p=Path(item["relative_path"])
        bag.require(not p.is_absolute() and ".." not in p.parts,"unsafe normalized output path")
        bag.require(sha256(root/p)==item["sha256"],"normalized artifact hash mismatch: "+str(p))
    bag.require(r["config_sha256"]["manifest.json"]==sha256(SESSION/"manifest.json"),"manifest changed since normalization")
    bag.require(r["config_sha256"]["geometry.json"]==sha256(SESSION/"geometry.json"),"geometry changed since normalization")
    return r


def number(value):return float(value) if value else None


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--normalized",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    started=time.monotonic()
    run=None
    try:
        run=new_run(args.output,"sandbox_development_diagnostics",[CONFIG,SESSION/"manifest.json",SESSION/"geometry.json"],
                    [sys.executable,__file__]+(list(argv) if argv is not None else sys.argv[1:]))
        config=json.loads(CONFIG.read_text())
        validate_trials(config["development_experiments"])
        provenance=verify_normalized(args.normalized)
        run["inputs"]=[{"asset_id":"normalization","relative_path":"run.json","sha256":sha256(args.normalized/"run.json")},
                       *[dict(i) for i in provenance["outputs"] if i["relative_path"] in ("ranges.csv","frames.csv","time_diagnostics.json")]]
        atomic_json(args.output/"run.json",run)
        frame_counts=Counter()
        frame_times=defaultdict(list)
        origins={}
        time_diag=json.loads((args.normalized/"time_diagnostics.json").read_text())
        for trial in DEVELOPMENT:origins[trial]=time_diag["experiments"][trial]["origin_receive_epoch_ns"]
        with (args.normalized/"frames.csv").open(newline="") as stream:
            for r in csv.DictReader(stream):
                if r["experiment_id"] not in DEVELOPMENT or r["source"]!="raw":continue
                key=(r["experiment_id"],r["vehicle_id"])
                frame_counts[key]+=1
                frame_times[key].append((int(r["receive_epoch_ns"]),int(r["header_epoch_ns"])))
        links=defaultdict(list)
        invalid=Counter()
        with (args.normalized/"ranges.csv").open(newline="") as stream:
            for r in csv.DictReader(stream):
                if r["experiment_id"] not in DEVELOPMENT or r["source"]!="raw":continue
                key=(r["experiment_id"],r["vehicle_id"],r["target_id"])
                if r["valid"]!="1":invalid[key]+=1;continue
                links[key].append((int(r["receive_epoch_ns"]),float(r["range_m"]),number(r["fp_rssi_db"]),number(r["rx_rssi_db"])))
        result={"schema_version":1,"config":config,"experiments":{}}
        windows=[]
        report=["# 开发包观测诊断", "", "只分析 T08/T10/T12/T14；未读取留出包定位误差。", "",
            "同一包首条 bag 接收时间起算，1s固定窗。仅 raw 有向条目；不使用 bridge 重复计量。",
            "双向差使用 Car1 时刻之前最近的 Car2 到达，最大年龄30ms；允许重复配对，非独立同步样本。", "",
            "| 包 | C1 peer有效帧% | C2 peer有效帧% | 双向差中位m | 差P05/P95 m |", "|---|---:|---:|---:|---|"]
        for trial in sorted(DEVELOPMENT):
            exp={"links":{},"arrival":{},"peer_asof":{}}
            for car in TAGS:
                exp["arrival"][car]=arrival_summary(frame_times[(trial,car)],config)
                targets=WALLS|{TAGS["car2" if car=="car1" else "car1"]}
                for target in sorted(targets):
                    key=(trial,car,target)
                    rows=links[key]
                    exp["links"][car+"->"+target]=link_summary(rows,frame_counts[(trial,car)])
                    exp["links"][car+"->"+target]["invalid_entries"]=invalid[key]
                    # Include all frame-supported windows, including zero-entry windows.
                    bins=defaultdict(list)
                    denominators=Counter((t-origins[trial])//config["window_ns"] for t,h in frame_times[(trial,car)])
                    for r in rows:bins[(r[0]-origins[trial])//config["window_ns"]].append(r)
                    for w in range(max(denominators,default=-1)+1):
                        summary=link_summary(bins[w],denominators[w])
                        windows.append(dict(experiment_id=trial,vehicle_id=car,target_id=target,
                            window_start_s=w*config["window_ns"]/1e9,raw_frames=denominators[w],
                            valid_entries=len(bins[w]),valid_frame_fraction=summary["valid_frame_fraction"],
                            range_median_m=summary["distance_m"].get("median"),fp_rssi_median_db=summary["fp_rssi_db"].get("median")))
            pairs=peer_asof([(r[0],r[1]) for r in links[(trial,"car1","node_0")]],
                [(r[0],r[1]) for r in links[(trial,"car2","node_1")]],config["peer_asof_max_age_ns"])
            exp["peer_asof"]={"pairs":len(pairs),"age_ns":bag.stats([r["age_ns"] for r in pairs]),
                "signed_car1_minus_car2_m":bag.stats([r["car1_minus_car2_m"] for r in pairs]),
                "causal_arrival_only":True,"sampling_sync_validated":False}
            # Per-pair large results remain outside Git, one file per development bag.
            if pairs:
                from normalize import write_table
                write_table(args.output/(trial+"_peer_asof.csv"),pairs,list(pairs[0]))
            result["experiments"][trial]=exp
            a=exp["links"]["car1->node_0"]["valid_frame_fraction"]
            b=exp["links"]["car2->node_1"]["valid_frame_fraction"]
            d=exp["peer_asof"]["signed_car1_minus_car2_m"]
            report.append(f"| {trial} | {100*a:.2f} | {100*b:.2f} | {d.get('median',float('nan')):.4f} | {d.get('p05',float('nan')):.4f}/{d.get('p95',float('nan')):.4f} |")
            run["completed_experiments"].append(trial)
            atomic_json(args.output/"development_diagnostics.json",result)
            atomic_json(args.output/"run.json",run)
        from normalize import write_table
        write_table(args.output/"link_windows.csv",windows,list(windows[0]))
        report += ["", "development_diagnostics.json 保存每条墙链路/peer的覆盖、RSSI、距离及相邻条目变化、接收间隔和批处理候选。",
            "link_windows.csv 保留零条目窗；分母为实际 raw 帧数，无帧窗覆盖率为空。",
            "这些差值同时受时钟、异步测量、动态运动和测距偏差影响，不用于校准或阈值选择。",
            "T14 的材料、位置和实际时段仍未知；不标整包NLOS，不按脚本sleep反造遮挡窗。",
            "raw两向并非独立同分布重复；统计量不等于定位误差、RF丢包率或物理故障归因。", ""]
        (args.output/"development_report.md").write_text("\n".join(report),encoding="utf-8")
        run["limitations"]=["arrival proximity is not sample synchronization","no accepted independent localization reference"]
        finish_run(args.output,run,"DONE",started)
        return 0
    except (Exception,KeyboardInterrupt) as e:
        if run is not None:finish_run(args.output,run,"FAILED",started,e)
        print("ERROR: "+str(e),file=sys.stderr)
        return 2


if __name__=="__main__":sys.exit(main())
