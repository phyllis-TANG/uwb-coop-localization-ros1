#!/usr/bin/env python3
"""Descriptive paired development report; includes every completed condition."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path
import statistics
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from io_utils import dump,gzread,sha,utc

SELECTED=("odom_only","independent","joint","huber","gate_cap","shadow_only","gate_cap_shadow")


def csv_write(path,rows):
    if not rows:return
    with path.open("x",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)


def summarize(results,verification,output):
    if output.exists():raise FileExistsError(output)
    output.mkdir(parents=True)
    p=json.loads((results/"frozen_protocol.json").read_text());inventory=json.loads((results/"inventory.json").read_text())
    audit=json.loads(verification.read_text())
    if audit["status"]!="DONE":raise ValueError("independent readback must complete first")
    audited={r["run_id"] for r in audit["runs"]};metrics=[];costs=[];counts=[];paired=[]
    for condition in inventory:
        if condition["status"]!="DONE":continue
        if condition["id"] not in audited:raise ValueError("missing independent audit: "+condition["id"])
        path=results/"runs"/condition["id"];rows=json.loads((path/"metrics.json").read_text());metrics.extend(rows)
        index={(r["method"],r["vehicle_id"],r["phase"]):r for r in rows}
        for row in rows:
            base=index["independent",row["vehicle_id"],row["phase"]]
            paired.append(dict(row,delta_rmse_vs_independent_m=None if row["xy_rmse_m"] is None or base["xy_rmse_m"] is None else row["xy_rmse_m"]-base["xy_rmse_m"]))
        timing=json.loads((path/"compute_cost.json").read_text())
        for method,total in timing["method_process_seconds"].items():
            costs.append(dict(run_id=condition["id"],scenario=condition["scenario"],role=condition["role"],seed=condition["seed"],method=method,total_process_s=total,core_s=timing["method_core_seconds"][method],shadow_s=timing["method_shadow_seconds"][method]))
        for key,value in next(r for r in audit["runs"] if r["run_id"]==condition["id"])["counts"].items():counts.append(dict(run_id=condition["id"],key=key,count=value))
    csv_write(output/"per_car_results.csv",paired);csv_write(output/"compute_cost.csv",costs);csv_write(output/"event_counts.csv",counts)
    groups=defaultdict(list)
    for row in paired:groups[row["scenario"],row["role"],row["method"],row["vehicle_id"],row["phase"]].append(row)
    summary=[]
    for key,rows in sorted(groups.items()):
        valid=[r for r in rows if r["xy_rmse_m"] is not None]
        if not valid:continue
        delta=[r["delta_rmse_vs_independent_m"] for r in valid]
        summary.append(dict(zip(("scenario","role","method","vehicle_id","phase"),key),independent_seeds=len({r["seed"] for r in valid}),
            mean_rmse_m=statistics.mean(r["xy_rmse_m"] for r in valid),max_error_m=max(r["xy_max_m"] for r in valid),
            paired_mean_delta_rmse_m=statistics.mean(delta),paired_min_delta_m=min(delta),paired_max_delta_m=max(delta),
            lower_rmse_seed_count=sum(v<0 for v in delta),above_error_limit_rows=sum(r["over_error_limit_rows"] for r in valid),
            recovery_censored_seed_count=sum(r["recovery_start_delay_s"] is None for r in valid)))
    csv_write(output/"paired_seed_summary.csv",summary)
    summary_index={(r["scenario"],r["role"],r["method"],r["vehicle_id"],r["phase"]):r for r in summary}
    roles=sorted({(r["scenario"],r["role"]) for r in summary});methods=p["methods"]
    fig,axes=plt.subplots(1,2,figsize=(14,8),sharey=True)
    bound=max(abs(r["paired_mean_delta_rmse_m"]) for r in summary if r["phase"]=="fault") or .001
    for ax,car in zip(axes,("car1","car2")):
        values=np.array([[summary_index[scene,role,m,car,"fault"]["paired_mean_delta_rmse_m"] for m in methods] for scene,role in roles])
        image=ax.imshow(values,cmap="coolwarm",vmin=-bound,vmax=bound,aspect="auto")
        ax.set_xticks(range(len(methods)),methods,rotation=65,ha="right");ax.set_yticks(range(len(roles)),[s+" / "+r for s,r in roles]);ax.set_title(car+": paired fault RMSE delta vs independent (m)")
    fig.colorbar(image,ax=axes.ravel().tolist(),label="negative = lower synthetic error",fraction=.025);fig.subplots_adjust(left=.26,bottom=.27,right=.91,wspace=.08)
    fig.savefig(output/"paired_fault_delta.png",dpi=160);plt.close(fig)
    # Plot selection is fixed before reading outcomes: first development seed, car1 role.
    selected_seed=p["development_seeds"][0]
    selected_path=results/"runs"/f"peer_bias__car1__{selected_seed}"
    if selected_path.exists():
        ticks=list(gzread(selected_path/"states.jsonl.gz"));run=json.loads((selected_path/"run.json").read_text());origin=run["origin_epoch_ns"]
        truth={(r["vehicle_id"],r["state_epoch_ns"]):r["pose"] for r in gzread(selected_path/"truth.jsonl.gz")}
        fig,axes=plt.subplots(1,2,figsize=(12,5))
        for ax,car in zip(axes,("car1","car2")):
            targets=[pose for (c,t),pose in sorted(truth.items()) if c==car];ax.plot([v[0] for v in targets],[v[1] for v in targets],"k--",label="truth")
            for method in SELECTED:
                poses=[t["methods"][method]["vehicles"][car]["pose"] for t in ticks];poses=[v for v in poses if v is not None]
                ax.plot([v[0] for v in poses],[v[1] for v in poses],label=method,lw=.9)
            ax.set_aspect("equal",adjustable="datalim");ax.set_title(car+": published anchor trajectory");ax.set_xlabel("room X (m)");ax.set_ylabel("room Y (m)");ax.legend(fontsize=7)
        fig.tight_layout();fig.savefig(output/"peer_bias_trajectory.png",dpi=160);plt.close(fig)
        fig,axes=plt.subplots(4,1,figsize=(12,10),sharex=True)
        for ax,car in zip(axes[:2],("car1","car2")):
            for method in SELECTED:
                tx=[];ey=[]
                for tick in ticks:
                    state=tick["methods"][method]["vehicles"][car];stamp=state.get("state_epoch_ns")
                    if not state["valid"] or stamp is None:continue
                    tx.append((stamp-origin)/1e9);ey.append(float(np.linalg.norm(np.array(state["pose"][:2])-truth[car,stamp][:2])))
                ax.plot(tx,ey,label=method,lw=.9)
            ax.set_ylabel(car+" XY error (m)");ax.legend(fontsize=7,ncol=4)
        observations={m:[] for m in ("joint","huber","gate_cap_shadow")}
        for event in gzread(selected_path/"events.jsonl.gz"):
            for method in observations:
                decision=event["methods"][method]["decision"]
                if decision.get("reliability"):
                    d=decision["reliability"];observations[method].append(((decision["measurement_epoch_ns"]-origin)/1e9,d))
        for method,records in observations.items():
            if records:axes[2].plot([r[0] for r in records],[r[1]["z"] for r in records],label=method,lw=.9)
        axes[2].axhline(p["policy"]["gate_z"],c="k",ls="--");axes[2].axhline(-p["policy"]["gate_z"],c="k",ls="--");axes[2].set_ylabel("peer normalized innovation");axes[2].legend(fontsize=7)
        for i,car in enumerate(("car1","car2")):
            delta=[np.linalg.norm(np.array(t["methods"]["gate_cap_shadow"]["output_delta"])[3*i:3*i+2]) for t in ticks]
            axes[3].plot([(t["publish_receive_epoch_ns"]-origin)/1e9 for t in ticks],delta,label=car+" held shift")
        axes[3].set_ylabel("shadow output shift (m)");axes[3].set_xlabel("seconds; errors use state time, held shift uses publication time");axes[3].legend(fontsize=7)
        for ax in axes:ax.axvspan(p["fault_start_s"],p["fault_end_s"],color="red",alpha=.08);ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(output/"peer_bias_error_monitor.png",dpi=160);plt.close(fig)
    key_tables=[]
    for scene in ("normal","weak_wall_correct_peer","peer_bias","weak_wall_peer_bias","coherent_fault"):
        for role in sorted({r["role"] for r in summary if r["scenario"]==scene}):
            for car in ("car1","car2"):
                rows=[summary_index[scene,role,m,car,"fault"] for m in ("independent","joint","huber","gate_cap","gate_cap_shadow")]
                key_tables.append(dict(scenario=scene,role=role,vehicle=car,**{r["method"]:r["mean_rmse_m"] for r in rows}))
    csv_write(output/"key_findings.csv",key_tables)
    report=["# A端六维因果EKF开发证据", "", "本报告由已完成单元和独立逐行回读生成；全部为合成开发结果，无实包精度或盲测主张。", "", f"计划{len(inventory)}行；完成{sum(r['status']=='DONE' for r in inventory)}个实际输入，去重{sum(r['status']=='DEDUPLICATED' for r in inventory)}行；每角色/场景为5个配对种子。", "", "| 场景 / 墙故障角色 / 评价车 | independent | joint | Huber | gate+cap | gate+cap+shadow |", "|---|---:|---:|---:|---:|---:|"]
    for row in key_tables:report.append("| "+row["scenario"]+" / "+row["role"]+" / "+row["vehicle"]+" | "+" | ".join(f"{row[m]:.6f}" for m in ("independent","joint","huber","gate_cap","gate_cap_shadow"))+" |")
    report.extend(["", "表中为故障时段逐车平均XY RMSE，单位m；normal行的同名时段没有故障。所有方法、全部阶段和负结果见per_car_results.csv及paired_seed_summary.csv。", "", "固定单向Car1→Car2；角色是墙支持/故障车辆，不能解释为反向peer更新。自洽故障下错误墙信息可能同时误导shadow，限幅只约束相对输出，不能约束真实误差。gate可拒绝正确peer而损失弱车协同；Huber或原联合可更优。", "", "非反馈组额外使用输出保持/失效策略；shadow_only为该策略控制组。PSD仅说明数值性质。计算时间分列core/shadow，非优化Python诊断框架，不能直接换算车载实时性能。", "", "T10参数就绪与参考批准另列BLOCKED；未对整包留出进行定位回放。三类图分别为真值/发布轨迹、误差/监测时间序列、配对分车故障代价矩阵。"])
    (output/"REPORT.md").write_text("\n".join(report)+"\n")
    dump(output/"report_run.json",dict(schema_version=1,status="DONE",created_at_utc=utc(),verification_sha256=sha(verification),inventory_sha256=sha(results/"inventory.json"),metric_rows=len(metrics),summary_rows=len(summary),plot_selection=dict(seed=selected_seed,role="car1",scenario="peer_bias"),outputs=[dict(relative_path=p.name,sha256=sha(p)) for p in sorted(output.iterdir()) if p.is_file()]))
    return dict(metric_rows=len(metrics),summary_rows=len(summary),actual_runs=len(audited))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--results",type=Path,required=True);parser.add_argument("--verification",type=Path,required=True);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv);print(json.dumps(summarize(args.results,args.verification,args.output)));return 0


if __name__=="__main__":sys.exit(main())
