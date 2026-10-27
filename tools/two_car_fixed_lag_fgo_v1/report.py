#!/usr/bin/env python3
"""Independent readback of the preregistered synthetic D0/D1 matrix.

No estimator, frontend, residual or Jacobian code is imported.  Error metrics
come from immutable publications and the separately stored synthetic truth.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

import numpy as np


SEEDS = (101, 211, 307)
SCENARIOS = ("nominal", "peer_bias", "wall_bias", "peer_gap")
ARMS = ("D0", "D1")
CARS = ("car1", "car2")
SCOPES = ("all_finite", "joint_common_valid")
WINDOWS = {"all": (None, None), "pre": (3., 24.), "fault": (24., 38.),
           "recovery": (38., 48.), "late": (48., 63.)}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    with Path(path).open() as stream:
        return json.load(stream, parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON " + x)))


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def checked_path(root, relative):
    p = (root / relative).resolve()
    if p != root and root not in p.parents:
        raise ValueError("artifact path escapes matrix directory: " + str(relative))
    return p


def boolean(value):
    if value in (True, "True", "true", "1", 1):
        return True
    if value in (False, "False", "false", "0", 0, "", None):
        return False
    raise ValueError("invalid boolean " + str(value))


def number(value):
    if value is None or value == "":
        return None
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("nonfinite CSV number")
    return x


def rms(values):
    values = list(values)
    return math.sqrt(sum(x*x for x in values)/len(values)) if values else None


def diff(a, b):
    return a-b if a is not None and b is not None else None


def fmt(value, digits=4):
    return "—" if value is None else f"{value:.{digits}f}"


def in_window(t, name):
    lower, upper = WINDOWS[name]
    return lower is None or (lower <= t and (t <= upper if name == "late" else t < upper))


def write_csv(path, rows, fields):
    with Path(path).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def verify_hash(path, expected, issues, label):
    if not path.is_file():
        issues.append(label + ": missing " + str(path))
        return False
    actual = sha(path)
    if actual != expected:
        issues.append(label + ": SHA mismatch " + str(path))
        return False
    return True


def read_cell(matrix_root, cell):
    """Keep failed/incomplete cells and their partial publications visible."""
    issues = []
    key = (cell.get("seed"), cell.get("scenario"), cell.get("arm"))
    result = {"seed": key[0], "scenario": key[1], "arm": key[2],
              "matrix_status": cell.get("status"), "run_status": None,
              "issues": issues, "rows": {}, "truth": {}, "summary": {}, "run": {},
              "input_relative_path": cell.get("input_relative_path"),
              "run_relative_path": cell.get("run_relative_path")}
    try:
        run_root = checked_path(matrix_root, cell["run_relative_path"])
        input_root = checked_path(matrix_root, cell["input_relative_path"])
    except (KeyError, TypeError, ValueError) as error:
        issues.append(str(error))
        return result
    if (run_root / "run.json").is_file():
        run = load(run_root / "run.json")
        result["run"] = run
        result["run_status"] = run.get("status")
        if run.get("status") != cell.get("status"):
            issues.append("matrix/run status disagreement")
        for output in run.get("outputs", []):
            verify_hash(checked_path(run_root, output["relative_path"]), output["sha256"], issues, "run.outputs")
        if run.get("status") == "DONE" and not run.get("outputs"):
            issues.append("DONE run has no output hashes")
        config_sha = run.get("config_sha256")
        if config_sha:
            verify_hash(input_root / "config.json", config_sha, issues, "input config")
            verify_hash(run_root / "config.json", config_sha, issues, "saved config")
        elif run.get("status") == "DONE":
            issues.append("DONE run has no config SHA")
        for item in run.get("inputs", []):
            verify_hash(checked_path(input_root, item["relative_path"]), item["sha256"], issues, "run input")
        if run.get("status") == "DONE" and not run.get("inputs"):
            issues.append("DONE run has no input hashes")
        result["run_json_sha256"] = sha(run_root / "run.json")
        if cell.get("run_manifest_sha256"):
            verify_hash(run_root / "run.json", cell["run_manifest_sha256"], issues, "matrix run manifest")
        if cell.get("events_sha256"):
            verify_hash(input_root / "events.jsonl.gz", cell["events_sha256"], issues, "matrix events")
        if cell.get("config_sha256"):
            verify_hash(input_root / "config.json", cell["config_sha256"], issues, "matrix config")
        if run.get("timing_mode") != "virtual":
            issues.append("unexpected timing mode")
    else:
        issues.append("missing run.json; cell retained")
    if (input_root / "input_manifest.json").is_file():
        manifest = load(input_root / "input_manifest.json")
        result["input_manifest_sha256"] = sha(input_root / "input_manifest.json")
        for relative, digest in manifest.get("files", {}).items():
            verify_hash(checked_path(input_root, relative), digest, issues, "input manifest")
        result["last_receive_epoch_ns"] = manifest.get("last_receive_epoch_ns")
    else:
        issues.append("missing input_manifest.json")
    if (run_root / "summary.json").is_file():
        result["summary"] = load(run_root / "summary.json")
    elif cell.get("status") == "DONE":
        issues.append("DONE cell missing summary.json")
    if (input_root / "truth.jsonl").is_file():
        with (input_root / "truth.jsonl").open() as stream:
            for line in stream:
                row = json.loads(line)
                ns = row["state_epoch_ns"]
                if type(ns) is not int or ns in result["truth"]:
                    issues.append("duplicate/noninteger truth time")
                    continue
                result["truth"][ns] = row
    else:
        issues.append("missing separate truth input")
    if (run_root / "published.csv").is_file():
        with (run_root / "published.csv").open(newline="") as stream:
            for raw in csv.DictReader(stream):
                ns, car = int(raw["state_epoch_ns"]), raw["vehicle_id"]
                if car not in CARS or (ns, car) in result["rows"]:
                    issues.append("unexpected vehicle or duplicate publication")
                    continue
                row = dict(raw)
                row["state_epoch_ns"] = ns
                row["state_time_s"] = float(raw["state_time_s"])
                row["accepted_graph"] = boolean(raw.get("accepted_graph"))
                row["valid"] = boolean(raw.get("valid"))
                row["finite_output"] = boolean(raw.get("finite_output"))
                row["peer_factor_used"] = boolean(raw.get("peer_factor_used"))
                for field in ("antenna_x_m", "antenna_y_m", "antenna_z_m", "yaw_rad", "peer_median_m"):
                    row[field] = number(raw.get(field))
                coords = [row[field] for field in ("antenna_x_m", "antenna_y_m", "antenna_z_m", "yaw_rad")]
                row["finite"] = row["finite_output"] and all(value is not None for value in coords)
                if row["accepted_graph"] != row["valid"]:
                    issues.append("accepted_graph/valid mismatch")
                if ns not in result["truth"]:
                    issues.append("publication has no exact-time independent truth")
                if row["finite"] and ns in result["truth"]:
                    truth = result["truth"][ns]["cars"][car]
                    delta = np.asarray(coords[:3])-np.asarray(truth["antenna_xyz_m"])
                    row["position_error_m"] = float(np.linalg.norm(delta[:2]))
                    yaw_error = coords[3]-truth["pose"][2]
                    row["yaw_error_rad"] = math.atan2(math.sin(yaw_error), math.cos(yaw_error))
                result["rows"][(ns, car)] = row
    elif cell.get("status") == "DONE":
        issues.append("DONE cell missing published.csv")
    times = {ns for ns, _ in result["rows"]}
    for ns in times:
        if not all((ns, car) in result["rows"] for car in CARS):
            issues.append("joint timestamp missing vehicle row")
    last_receive, origin = result.get("last_receive_epoch_ns"), result["run"].get("epoch_origin_ns")
    if last_receive is not None and origin is not None and result["run_status"] == "DONE":
        expected_times = {ns for ns in result["truth"] if ns > origin and ns+1_000_000_000 <= last_receive}
        if times != expected_times:
            issues.append("DONE publications do not cover expected 1Hz release grid")
    return result


def row_times(cell, car, accepted=False):
    return {ns for (ns, vehicle), row in cell["rows"].items()
            if vehicle == car and row.get("finite") and ns in cell["truth"]
            and (not accepted or row["accepted_graph"])}


def vehicle_metric(cell, car, times, window):
    rows = [cell["rows"][(ns, car)] for ns in sorted(times)
            if (ns, car) in cell["rows"] and in_window(cell["rows"][(ns, car)]["state_time_s"], window)]
    return {"n": len(rows), "position_rmse_m": rms(row["position_error_m"] for row in rows),
            "yaw_rmse_rad": rms(row["yaw_error_rad"] for row in rows),
            "yaw_rmse_deg": rms(math.degrees(row["yaw_error_rad"]) for row in rows),
            "position_mean_m": float(np.mean([row["position_error_m"] for row in rows])) if rows else None,
            "position_max_m": max((row["position_error_m"] for row in rows), default=None)}


def pair_metric(cell, times, window):
    relative_errors, separation_errors = [], []
    for ns in sorted(times):
        if not in_window(cell["rows"][(ns, "car1")]["state_time_s"], window):
            continue
        rows = [cell["rows"][(ns, car)] for car in CARS]
        xyz = [np.array([row["antenna_x_m"], row["antenna_y_m"], row["antenna_z_m"]]) for row in rows]
        true_xyz = [np.asarray(cell["truth"][ns]["cars"][car]["antenna_xyz_m"]) for car in CARS]
        predicted, reference = xyz[1]-xyz[0], true_xyz[1]-true_xyz[0]
        relative_errors.append(float(np.linalg.norm(predicted[:2]-reference[:2])))
        separation_errors.append(float(np.linalg.norm(predicted)-np.linalg.norm(reference)))
    return {"n": len(relative_errors), "relative_xy_vector_rmse_m": rms(relative_errors),
            "separation_3d_rmse_m": rms(separation_errors),
            "separation_signed_mean_m": float(np.mean(separation_errors)) if separation_errors else None}


def collect_metrics(cells):
    vehicle_rows, pair_rows, delta_rows = [], [], []
    common = {}
    registered_pairs = sorted({(seed, scenario) for seed, scenario, _ in cells})
    for seed, scenario in registered_pairs:
        present = [cells.get((seed, scenario, arm)) for arm in ARMS]
        common[(seed, scenario)] = set.intersection(*(row_times(c, car, True)
            for c in present for car in CARS)) if all(present) else set()
    # Development fixtures are retained in diagnostics, not mistaken for formal cells.
    for key, cell in sorted(cells.items()):
        seed, scenario, arm = key
        common_times = common.get((seed, scenario), set())
        for scope, window in itertools.product(SCOPES, WINDOWS):
            prefix = dict(seed=seed, scenario=scenario, arm=arm, scope=scope, window=window)
            for car in CARS:
                times = row_times(cell, car) if scope == "all_finite" else common_times
                vehicle_rows.append(dict(prefix, vehicle_id=car, **vehicle_metric(cell, car, times, window)))
            times = (row_times(cell, "car1") & row_times(cell, "car2")) if scope == "all_finite" else common_times
            pair_rows.append(dict(prefix, **pair_metric(cell, times, window)))
    for seed, scenario in registered_pairs:
        if not all((seed, scenario, arm) in cells for arm in ARMS):
            continue
        d0, d1 = (cells[(seed, scenario, arm)] for arm in ARMS)
        for scope, window in itertools.product(SCOPES, WINDOWS):
            base = dict(seed=seed, scenario=scenario, scope=scope, window=window)
            # All-finite pairwise deltas also use common timestamps for fairness.
            times = (set.intersection(*(row_times(c, car) for c in (d0, d1) for car in CARS))
                     if scope == "all_finite" else common[(seed, scenario)])
            for car in CARS:
                a, b = [vehicle_metric(c, car, times, window) for c in (d0, d1)]
                for metric in ("position_rmse_m", "yaw_rmse_deg"):
                    delta_rows.append(dict(base, comparison="D1_minus_D0", arm="D1-D0", vehicle_id=car,
                        metric=metric, n=a["n"], value_D0=a[metric], value_D1=b[metric], delta=diff(b[metric], a[metric])))
            a, b = [pair_metric(c, times, window) for c in (d0, d1)]
            for metric in ("relative_xy_vector_rmse_m", "separation_3d_rmse_m"):
                delta_rows.append(dict(base, comparison="D1_minus_D0", arm="D1-D0", vehicle_id="pair",
                    metric=metric, n=a["n"], value_D0=a[metric], value_D1=b[metric], delta=diff(b[metric], a[metric])))
            if scenario == "nominal" or not all((seed, "nominal", arm) in cells for arm in ARMS):
                continue
            nominal = [cells[(seed, "nominal", arm)] for arm in ARMS]
            # Fault-vs-normal propagation has an identical epoch set across all
            # four runs, so failure coverage cannot create a favorable delta.
            times &= set.intersection(*(row_times(c, "car2", scope == "joint_common_valid") for c in nominal))
            propagation = {}
            for arm, faulty, normal in zip(ARMS, (d0, d1), nominal):
                a, b = [vehicle_metric(c, "car2", times, window) for c in (normal, faulty)]
                propagation[arm] = diff(b["position_rmse_m"], a["position_rmse_m"])
                delta_rows.append(dict(base, comparison="fault_minus_nominal_same_epochs", arm=arm, vehicle_id="car2",
                    metric="position_rmse_m", n=a["n"], nominal=a["position_rmse_m"], faulty=b["position_rmse_m"],
                    delta=propagation[arm]))
            delta_rows.append(dict(base, comparison="propagation_D1_minus_D0", arm="D1-D0", vehicle_id="car2",
                metric="fault_minus_nominal_position_rmse_m", n=a["n"], value_D0=propagation["D0"],
                value_D1=propagation["D1"], delta=diff(propagation["D1"], propagation["D0"])))
    return vehicle_rows, pair_rows, delta_rows, common


def cell_diagnostic(cell):
    rows = cell["rows"]
    times = sorted({ns for ns, _ in rows})
    samples = [rows[(ns, "car1")] for ns in times if (ns, "car1") in rows]
    statuses = Counter(row["status"] for row in samples)
    available = sum(row["peer_median_m"] is not None for row in samples)
    used = sum(row["peer_factor_used"] for row in samples)
    return {k: cell[k] for k in ("seed", "scenario", "arm", "matrix_status", "run_status", "issues",
            "run_relative_path", "input_relative_path")} | {
        "publication_timestamps": len(times), "publication_vehicle_rows": len(rows),
        "status_counts": dict(statuses), "accepted_timestamps": sum(row["accepted_graph"] for row in samples),
        "finite_timestamps": sum(row["finite"] for row in samples),
        "warmup_timestamps": sum(n for status, n in statuses.items() if "warmup" in status),
        "failure_or_fallback_timestamps": sum(n for status, n in statuses.items()
            if "fail" in status or "error" in status or "missing" in status),
        "peer_available_timestamps": available, "peer_availability_fraction": available/len(samples) if samples else None,
        "peer_factor_timestamps": used, "peer_factor_fraction": used/len(samples) if samples else None,
        "peer_factor_semantics": "added factor, including warmup; not necessarily an accepted correction",
        "missing_peer_timestamps": len(samples)-available,
        "elapsed_s": cell["run"].get("elapsed_s"),
        "update_wall_total_s": cell["summary"].get("update_wall_total_s"),
        "update_wall_p95_s": cell["summary"].get("update_wall_p95_s"),
        "peak_scalar_variables": cell["summary"].get("peak_scalar_variables"),
        "sensor_peaks": cell["summary"].get("sensor_peaks"),
        "peer_buffer_peak": cell["summary"].get("peer_buffer_peak"),
        "marginalizations": cell["summary"].get("marginalizations"),
        "run_json_sha256": cell.get("run_json_sha256"),
        "input_manifest_sha256": cell.get("input_manifest_sha256"),
    }


def plot_errors(cells, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    generated = []
    for scenario in SCENARIOS:
        fig, axes = plt.subplots(3, 2, figsize=(11, 8), sharex=True, sharey=False, squeeze=False)
        for row, seed in enumerate(SEEDS):
            for col, car in enumerate(CARS):
                axis = axes[row, col]
                for arm, color in (("D0", "#2563a6"), ("D1", "#d87520")):
                    cell = cells.get((seed, scenario, arm))
                    if cell:
                        publications = sorted((v for (_, vehicle), v in cell["rows"].items() if vehicle == car), key=lambda r: r["state_epoch_ns"])
                        axis.plot([v["state_time_s"] for v in publications],
                                  [v.get("position_error_m", np.nan) for v in publications],
                                  color=color, label=arm, linewidth=1.2)
                        failed = [v for v in publications if v.get("finite") and not v["accepted_graph"]]
                        axis.scatter([v["state_time_s"] for v in failed], [v["position_error_m"] for v in failed],
                                     color=color, marker="x", s=17)
                if scenario != "nominal":
                    axis.axvspan(24, 38, color="#b85353", alpha=.13)
                axis.axvline(48, color="#777777", linestyle=":", linewidth=.7)
                axis.set_title(f"seed {seed}, {car}", fontsize=10)
                axis.set_ylabel("antenna XY error (m)")
                axis.grid(alpha=.2)
                if axis.get_legend_handles_labels()[0]: axis.legend(fontsize=8)
                if row == 2: axis.set_xlabel("state time (s), virtual replay")
        fig.suptitle(f"{scenario}: immutable publications; x = warmup/fallback", fontsize=12)
        fig.tight_layout(rect=(0, 0, 1, .97))
        name = f"error_timeseries_{scenario}.png"
        fig.savefig(output/name, dpi=150)
        plt.close(fig)
        generated.append(name)
    fig, axes = plt.subplots(3, 3, figsize=(13, 8), sharex=True, squeeze=False)
    for row, seed in enumerate(SEEDS):
        for col, scenario in enumerate(SCENARIOS[1:]):
            axis = axes[row, col]
            for arm, color in (("D0", "#2563a6"), ("D1", "#d87520")):
                fault, normal = cells.get((seed, scenario, arm)), cells.get((seed, "nominal", arm))
                if fault and normal:
                    epochs = sorted(row_times(fault, "car2") & row_times(normal, "car2"))
                    axis.plot([fault["rows"][(ns, "car2")]["state_time_s"] for ns in epochs],
                        [fault["rows"][(ns, "car2")]["position_error_m"]-normal["rows"][(ns, "car2")]["position_error_m"] for ns in epochs],
                        label=arm, color=color, linewidth=1.2)
            axis.axvspan(24, 38, color="#b85353", alpha=.13)
            axis.axhline(0, color="#777777", linewidth=.6)
            axis.axvline(48, color="#777777", linestyle=":", linewidth=.7)
            axis.set_title(f"seed {seed}, {scenario}", fontsize=9)
            axis.grid(alpha=.2)
            if axis.get_legend_handles_labels()[0]: axis.legend(fontsize=8)
            if col == 0: axis.set_ylabel("Car2 fault − nominal XY error (m)")
            if row == 2: axis.set_xlabel("state time (s), virtual replay")
    fig.suptitle("Car2 synchronized fault propagation / loss-of-peer effect", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, .97))
    name = "car2_fault_propagation.png"
    fig.savefig(output/name, dpi=150)
    plt.close(fig)
    generated.append(name)
    return generated


def markdown_report(metrics, output):
    lines = ["# 双车固定窗口 D0/D1 合成对照", "", f"状态：**{metrics['status']}**。",
        f"正式预登记24组，索引{metrics['indexed_cells']}组，DONE {metrics['done_cells']}组，"
        f"FAILED/其他{metrics['indexed_cells']-metrics['done_cells']}组；"
        f"SHA/结构问题{len(metrics['issues'])}项。", "",
        "回放均为 **virtual**：接收截止/1s等待由事件时钟驱动，计算耗时实测；不代表ROS或车载端到端实时性。"
        "这里只评价独立保存的合成真值，没有使用视频或实包全轨迹参考。", "",
        "`all_finite`保留暖启动与数值回退；`joint_common_valid`仅含同seed/场景两臂两车共同accepted时刻。"
        "均使用原房间坐标和准确整数ns关联，不做事后刚体对齐。"
        "XY为天线中心二维欧氏误差，yaw为wrapped角误差；相对位置为两天线XY向量误差，间距为三维斜距误差。", "",
        "## 每seed主结果（全部有限发布）", "",
        "|seed|场景|臂|Car1 XY RMSE m|Car1 yaw RMSE °|Car2 XY RMSE m|Car2 yaw RMSE °|相对XY RMSE m|间距RMSE m|n C1/C2/pair|",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---|"]
    for cell in metrics["cells"]:
        base = (cell["seed"], cell["scenario"], cell["arm"])
        rows = [r for r in metrics["vehicle_metrics"] if (r["seed"], r["scenario"], r["arm"]) == base and r["scope"] == "all_finite" and r["window"] == "all"]
        lookup = {r["vehicle_id"]: r for r in rows}
        pair = next((r for r in metrics["pair_metrics"] if (r["seed"], r["scenario"], r["arm"]) == base and r["scope"] == "all_finite" and r["window"] == "all"), {})
        a, b = lookup.get("car1", {}), lookup.get("car2", {})
        lines.append(f"|{base[0]}|{base[1]}|{base[2]}|{fmt(a.get('position_rmse_m'))}|{fmt(a.get('yaw_rmse_deg'))}|{fmt(b.get('position_rmse_m'))}|{fmt(b.get('yaw_rmse_deg'))}|{fmt(pair.get('relative_xy_vector_rmse_m'))}|{fmt(pair.get('separation_3d_rmse_m'))}|{a.get('n',0)}/{b.get('n',0)}/{pair.get('n',0)}|")
    lines += ["", "## 正常代价及故障传播（共同有效时刻）", "",
        "下表为每seed的D1−D0位置RMSE差；正值表示加入peer后误差更大。"
        "故障行另给Car2相对同seed正常场景、相同epoch的RMSE增量，再比较D1−D0；"
        "墙链故障直接污染Car1，Car2增量展示向另一车传播。peer缺测行表示约束损失/恢复效应。", "",
        "|seed|场景|窗口|Car1 ΔRMSE m|Car2 ΔRMSE m|Car2 故障增量D0 m|Car2 故障增量D1 m|",
        "|---|---|---|---:|---:|---:|---:|"]
    for seed, scenario in itertools.product(SEEDS, SCENARIOS):
        for window in (("all",) if scenario == "nominal" else ("fault", "recovery", "late")):
            rows = [r for r in metrics["paired_deltas"] if r["seed"] == seed and r["scenario"] == scenario and r["window"] == window and r["scope"] == "joint_common_valid"]
            vehicle_delta = {r["vehicle_id"]: r["delta"] for r in rows if r["comparison"] == "D1_minus_D0" and r["metric"] == "position_rmse_m"}
            propagation = {r["arm"]: r["delta"] for r in rows if r["comparison"] == "fault_minus_nominal_same_epochs"}
            lines.append(f"|{seed}|{scenario}|{window}|{fmt(vehicle_delta.get('car1'))}|{fmt(vehicle_delta.get('car2'))}|{fmt(propagation.get('D0'))}|{fmt(propagation.get('D1'))}|")
    lines += ["", "## 完整性、缺测及计算量", "",
        "|seed|场景|臂|状态|发布时刻|accepted|warmup|失败/回退|peer可用/加入|耗时s|更新p95s|峰值标量|",
        "|---|---|---|---|---:|---:|---:|---:|---|---:|---:|---:|"]
    for c in metrics["cells"]:
        lines.append(f"|{c['seed']}|{c['scenario']}|{c['arm']}|{c['run_status'] or c['matrix_status']}|{c['publication_timestamps']}|{c['accepted_timestamps']}|{c['warmup_timestamps']}|{c['failure_or_fallback_timestamps']}|{c['peer_available_timestamps']}/{c['peer_factor_timestamps']}|{fmt(c['elapsed_s'],3)}|{fmt(c['update_wall_p95_s'],4)}|{c['peak_scalar_variables']}|")
    lines += ["", "peer加入次数包括暖启动，表示向活动图加入了因子，不等同于accepted纠正次数。缺测后仍保留过去peer形成的相关先验；恢复时不清除该历史信息。", "", f"累计cell耗时：{fmt(metrics['total_cell_elapsed_s'],3)}s。所有失败/缺失cell均保留在metrics.json，未删选seed。",
        "共同有效时间覆盖及逐车pre/fault/recovery/late完整指标见 `per_seed_vehicle.csv`、"
        "`per_seed_pair.csv`；正常代价/同期故障增量见 `paired_deltas.csv`。", "",
        "误差传播同期图：", ""]
    lines += [f"![{name}]({name})" for name in metrics["figures"]]
    lines += ["", "## 限制与核验", "",
        "权重为预登记工程值；3个seed仅作描述性对照，不代表现场泛化精度。"
        "拟合peer残差变小不能独立证明定位更准，本报告的误差来自单独真值文件。"
        "固定外参和精确合成时钟不是历史安装/跨车同步的验收；未运行历史两包或任何留出包。", "",
        "读取器没有导入graph/frontend/replay。核验matrix索引、每run输出哈希、实际输入与配置SHA、"
        "独立真值/标签manifest和D0/D1输入字节同一性。", ""]
    if metrics["issues"]:
        lines += ["核验问题（报告不会据此宣称24组完成）：", ""]
        lines += ["- " + issue for issue in metrics["issues"]]
    else:
        lines += ["全部登记SHA及24组索引一致。"]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n")


def report(matrix_root, output):
    matrix_root, output = Path(matrix_root).resolve(), Path(output).resolve()
    repo = Path(__file__).resolve().parents[2]
    if output == repo or repo in output.parents:
        raise ValueError("report outputs must be outside Git")
    output.mkdir(parents=True, exist_ok=False)
    matrix = load(matrix_root / "matrix.json")
    expected = set(itertools.product(SEEDS, SCENARIOS, ARMS))
    indexed, cells, issues = [], {}, []
    for cell in matrix.get("cells", []):
        key = (cell.get("seed"), cell.get("scenario"), cell.get("arm"))
        indexed.append(key)
        if key in cells:
            issues.append("duplicate cell index " + repr(key))
            continue
        try:
            cells[key] = read_cell(matrix_root, cell)
        except (Exception, KeyboardInterrupt) as error:
            issues.append("cell readback error " + repr(key) + ": " + type(error).__name__ + ": " + str(error))
            cells[key] = {"seed": key[0], "scenario": key[1], "arm": key[2],
                "matrix_status": cell.get("status"), "run_status": None,
                "issues": [str(error)], "rows": {}, "truth": {}, "summary": {}, "run": {},
                "run_relative_path": cell.get("run_relative_path"), "input_relative_path": cell.get("input_relative_path")}
    actual = set(indexed)
    if matrix.get("source_sha256"):
        for relative, digest in matrix["source_sha256"].items():
            verify_hash(checked_path(matrix_root, "source/"+relative), digest, issues, "frozen source archive")
        for key, cell in cells.items():
            if cell["run_status"] == "DONE" and cell["run"].get("source_sha256") != matrix["source_sha256"]:
                issues.append("run source lock differs from frozen matrix: "+repr(key))
    elif actual == expected:
        issues.append("formal matrix missing source SHA lock")
    if matrix.get("test_receipt_sha256"):
        verify_hash(matrix_root/"foundation_test_receipt.json", matrix["test_receipt_sha256"], issues, "foundation test receipt")
    for key in sorted(expected-actual): issues.append("missing formal cell " + repr(key))
    for key in sorted(actual-expected): issues.append("unregistered formal cell " + repr(key))
    if len(indexed) != 24: issues.append(f"expected exactly24 indexed cells, got {len(indexed)}")
    for key, cell in cells.items():
        issues.extend(repr(key) + ": " + issue for issue in cell["issues"])
    for seed, scenario in itertools.product(SEEDS, SCENARIOS):
        pair = [cells.get((seed, scenario, arm)) for arm in ARMS]
        if all(pair):
            paths = [c["input_relative_path"] for c in pair]
            if paths[0] != paths[1]:
                issues.append(f"paired input roots differ: seed{seed} {scenario}")
            identities = [[(i.get("relative_path"), i.get("sha256")) for i in c["run"].get("inputs", [])] for c in pair]
            if identities[0] != identities[1] or not identities[0]:
                issues.append(f"D0/D1 input SHA identity mismatch/missing: seed{seed} {scenario}")
            if pair[0]["run"].get("config_sha256") != pair[1]["run"].get("config_sha256"):
                issues.append(f"D0/D1 config SHA mismatch: seed{seed} {scenario}")
    vehicle_rows, pair_rows, delta_rows, common = collect_metrics(cells)
    diagnostics = [cell_diagnostic(c) for _, c in sorted(cells.items())]
    done = sum(c["run_status"] == "DONE" and c["matrix_status"] == "DONE" for c in diagnostics)
    complete = len(indexed) == 24 and actual == expected and done == 24 and not issues and matrix.get("status") == "DONE"
    figures = plot_errors(cells, output)
    metrics = {"schema_version": 1, "status": "DONE" if complete else "INCOMPLETE",
        "role": "independent_synthetic_publication_readback", "matrix_sha256": sha(matrix_root / "matrix.json"),
        "report_source_sha256": sha(__file__), "timing_mode": "virtual", "expected_cells": 24,
        "indexed_cells": len(indexed), "done_cells": done, "issues": issues,
        "failed_or_incomplete_cells": [{k: c[k] for k in ("seed", "scenario", "arm", "matrix_status", "run_status")}
            for c in diagnostics if c["run_status"] != "DONE" or c["matrix_status"] != "DONE"],
        "common_valid_times": [{"seed": seed, "scenario": scenario, "n": len(times),
            "state_epoch_ns": sorted(times)} for (seed, scenario), times in sorted(common.items())],
        "total_cell_elapsed_s": sum(c["elapsed_s"] or 0 for c in diagnostics),
        "cells": diagnostics, "vehicle_metrics": vehicle_rows, "pair_metrics": pair_rows,
        "paired_deltas": delta_rows, "figures": figures,
        "definitions": {"all_finite": "all finite immutable outputs including warmup/fallback",
            "joint_common_valid": "same seed/scenario D0/D1 x car1/car2 accepted intersection",
            "pair_delta_all_finite": "finite epoch intersection of both methods and both cars",
            "propagation": "Car2 faulty RMSE minus same-seed nominal RMSE on identical epochs",
            "windows_s": {"all": "all actual published times", "pre": "[3,24)", "fault": "[24,38)",
                "recovery": "[38,48)", "late": "[48,63]"},
            "reference": "independent synthetic room truth; no fitted alignment"}}
    dump(output / "metrics.json", metrics)
    write_csv(output / "per_seed_vehicle.csv", vehicle_rows,
        ["seed", "scenario", "arm", "scope", "window", "vehicle_id", "n", "position_rmse_m", "yaw_rmse_rad", "yaw_rmse_deg", "position_mean_m", "position_max_m"])
    write_csv(output / "per_seed_pair.csv", pair_rows,
        ["seed", "scenario", "arm", "scope", "window", "n", "relative_xy_vector_rmse_m", "separation_3d_rmse_m", "separation_signed_mean_m"])
    write_csv(output / "paired_deltas.csv", delta_rows,
        ["seed", "scenario", "scope", "window", "comparison", "arm", "vehicle_id", "metric", "n", "value_D0", "value_D1", "nominal", "faulty", "delta"])
    markdown_report(metrics, output)
    dump(output / "report_manifest.json", {"status": metrics["status"], "matrix_sha256": metrics["matrix_sha256"],
        "report_source_sha256": metrics["report_source_sha256"],
        "files": {str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()}})
    return metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        metrics = report(args.matrix, args.output)
        print(json.dumps({k: metrics[k] for k in ("status", "indexed_cells", "done_cells", "total_cell_elapsed_s")}))
        return 0 if metrics["status"] == "DONE" else 1
    except Exception as error:
        print(type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
