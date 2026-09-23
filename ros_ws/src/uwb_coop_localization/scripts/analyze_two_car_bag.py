#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Compare reciprocal UWB measurements from two cars in one or two bags.

The tool is read-only.  Pairing uses rosbag reception time; header timestamps
are reported as diagnostics and are never silently shifted.  Python 2.7
compatibility is required by ROS Melodic.
"""

from __future__ import division, print_function

import argparse
import csv
import hashlib
import json
import math
import os
import sys


def _finite(value):
    return not (math.isnan(value) or math.isinf(value))


def percentile(values, percent):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percent / 100.0
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _csv_open(path):
    if sys.version_info[0] < 3:
        return open(path, "wb")
    return open(path, "w", newline="")


def extract_range(message, source_id, target_id):
    """Return a finite source-to-target range or None."""
    if getattr(message, "tag_id", None) != source_id:
        return None
    for measurement in getattr(message, "ranges", []):
        if getattr(measurement, "anchor_id", None) != target_id:
            continue
        value = float(measurement.range)
        return value if _finite(value) else None
    return None


def read_range_records(path, topic, source_id, target_id):
    try:
        import rosbag
    except ImportError:
        raise RuntimeError("rosbag is unavailable; source ROS Melodic first")

    records = []
    with rosbag.Bag(path, "r") as bag:
        for index, (_, message, bag_stamp) in enumerate(
                bag.read_messages(topics=[topic])):
            header = getattr(message, "header", None)
            stamp = getattr(header, "stamp", None)
            header_time = stamp.to_sec() if stamp is not None else None
            bag_time = bag_stamp.to_sec()
            records.append({
                "message_index": index,
                "bag_time_s": bag_time,
                "header_time_s": header_time,
                "bag_header_offset_s": (
                    bag_time - header_time if header_time is not None else None),
                "range_m": extract_range(message, source_id, target_id),
            })
    return records


def read_truth_records(path, topic):
    try:
        import rosbag
    except ImportError:
        raise RuntimeError("rosbag is unavailable; source ROS Melodic first")

    records = []
    with rosbag.Bag(path, "r") as bag:
        for index, (_, message, bag_stamp) in enumerate(
                bag.read_messages(topics=[topic])):
            value = float(message.data)
            if _finite(value):
                records.append({
                    "message_index": index,
                    "bag_time_s": bag_stamp.to_sec(),
                    "range_m": value,
                })
    return records


def pair_by_bag_time(left, right, tolerance_s):
    """Return one-to-one nearest pairs within a bag-time tolerance."""
    if tolerance_s < 0.0:
        raise ValueError("pairing tolerance must be non-negative")
    candidates = []
    first_right = 0
    for left_index, left_row in enumerate(left):
        lower = left_row["bag_time_s"] - tolerance_s
        upper = left_row["bag_time_s"] + tolerance_s
        while (first_right < len(right) and
               right[first_right]["bag_time_s"] < lower):
            first_right += 1
        right_index = first_right
        while (right_index < len(right) and
               right[right_index]["bag_time_s"] <= upper):
            delta = (right[right_index]["bag_time_s"] -
                     left_row["bag_time_s"])
            candidates.append((abs(delta), left_index, right_index))
            right_index += 1

    used_left = set()
    used_right = set()
    selected = []
    for _, left_index, right_index in sorted(candidates):
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        selected.append((left_index, right_index))
    selected.sort()
    return selected


def build_pairs(car1, car2, tolerance_s):
    indices = pair_by_bag_time(car1, car2, tolerance_s)
    rows = []
    for pair_index, (car1_index, car2_index) in enumerate(indices):
        first = car1[car1_index]
        second = car2[car2_index]
        first_range = first["range_m"]
        second_range = second["range_m"]
        both_usable = first_range is not None and second_range is not None
        header_delta = None
        if (first["header_time_s"] is not None and
                second["header_time_s"] is not None):
            header_delta = second["header_time_s"] - first["header_time_s"]
        rows.append({
            "pair_index": pair_index,
            "pair_time_s": (first["bag_time_s"] + second["bag_time_s"]) / 2.0,
            "elapsed_pair_time_s": 0.0,
            "car1_message_index": first["message_index"],
            "car2_message_index": second["message_index"],
            "car1_bag_time_s": first["bag_time_s"],
            "car2_bag_time_s": second["bag_time_s"],
            "bag_time_delta_s": second["bag_time_s"] - first["bag_time_s"],
            "car1_header_time_s": first["header_time_s"],
            "car2_header_time_s": second["header_time_s"],
            "header_time_delta_s": header_delta,
            "car1_bag_header_offset_s": first["bag_header_offset_s"],
            "car2_bag_header_offset_s": second["bag_header_offset_s"],
            "car1_range_m": first_range,
            "car2_range_m": second_range,
            "car1_usable": int(first_range is not None),
            "car2_usable": int(second_range is not None),
            "both_usable": int(both_usable),
            "reciprocal_difference_m": (
                second_range - first_range if both_usable else None),
            "reciprocal_abs_difference_m": (
                abs(second_range - first_range) if both_usable else None),
            "reciprocal_mean_m": (
                (first_range + second_range) / 2.0 if both_usable else None),
            "truth_range_m": None,
            "car1_error_m": None,
            "car2_error_m": None,
            "reciprocal_mean_error_m": None,
        })
    if rows:
        start = rows[0]["pair_time_s"]
        for row in rows:
            row["elapsed_pair_time_s"] = row["pair_time_s"] - start
    return rows


def attach_constant_truth(rows, truth_distance_m):
    if truth_distance_m < 0.0 or not _finite(truth_distance_m):
        raise ValueError("truth distance must be a finite non-negative value")
    for row in rows:
        _attach_truth(row, truth_distance_m)


def attach_topic_truth(rows, truth_records, tolerance_s):
    pseudo_records = [dict(bag_time_s=row["pair_time_s"]) for row in rows]
    for pair_index, truth_index in pair_by_bag_time(
            pseudo_records, truth_records, tolerance_s):
        _attach_truth(rows[pair_index], truth_records[truth_index]["range_m"])


def _attach_truth(row, truth_range_m):
    row["truth_range_m"] = truth_range_m
    if row["car1_range_m"] is not None:
        row["car1_error_m"] = row["car1_range_m"] - truth_range_m
    if row["car2_range_m"] is not None:
        row["car2_error_m"] = row["car2_range_m"] - truth_range_m
    if row["reciprocal_mean_m"] is not None:
        row["reciprocal_mean_error_m"] = (
            row["reciprocal_mean_m"] - truth_range_m)


def _describe(summary, prefix, unit, values):
    finite = [value for value in values if value is not None and _finite(value)]
    summary[prefix + "_count"] = len(finite)
    summary[prefix + "_mean" + unit] = (
        sum(finite) / len(finite) if finite else None)
    summary[prefix + "_median" + unit] = percentile(finite, 50)
    summary[prefix + "_p95" + unit] = percentile(finite, 95)
    summary[prefix + "_min" + unit] = min(finite) if finite else None
    summary[prefix + "_max" + unit] = max(finite) if finite else None


def _describe_errors(summary, prefix, errors):
    finite = [value for value in errors if value is not None and _finite(value)]
    absolute = [abs(value) for value in finite]
    summary[prefix + "_count"] = len(finite)
    summary[prefix + "_bias_m"] = (
        sum(finite) / len(finite) if finite else None)
    summary[prefix + "_mae_m"] = (
        sum(absolute) / len(absolute) if absolute else None)
    summary[prefix + "_rmse_m"] = (
        math.sqrt(sum(value * value for value in finite) / len(finite))
        if finite else None)
    summary[prefix + "_abs_error_p95_m"] = percentile(absolute, 95)
    summary[prefix + "_abs_error_max_m"] = (
        max(absolute) if absolute else None)


def summarize_pairs(car1, car2, rows):
    both = sum(row["both_usable"] for row in rows)
    car1_only = sum(row["car1_usable"] and not row["car2_usable"]
                    for row in rows)
    car2_only = sum(row["car2_usable"] and not row["car1_usable"]
                    for row in rows)
    neither = len(rows) - both - car1_only - car2_only
    summary = {
        "car1_frames": len(car1),
        "car2_frames": len(car2),
        "car1_usable_frames": sum(row["range_m"] is not None for row in car1),
        "car2_usable_frames": sum(row["range_m"] is not None for row in car2),
        "paired_frames": len(rows),
        "unpaired_car1_frames": len(car1) - len(rows),
        "unpaired_car2_frames": len(car2) - len(rows),
        "car1_paired_percent": (
            100.0 * len(rows) / len(car1) if car1 else None),
        "car2_paired_percent": (
            100.0 * len(rows) / len(car2) if car2 else None),
        "both_usable_pairs": both,
        "car1_only_usable_pairs": car1_only,
        "car2_only_usable_pairs": car2_only,
        "neither_usable_pairs": neither,
        "both_usable_percent": 100.0 * both / len(rows) if rows else None,
    }
    _describe(summary, "bag_time_delta", "_s",
              [row["bag_time_delta_s"] for row in rows])
    _describe(summary, "header_time_delta", "_s",
              [row["header_time_delta_s"] for row in rows])
    _describe(summary, "reciprocal_abs_difference", "_m",
              [row["reciprocal_abs_difference_m"] for row in rows])
    _describe_errors(summary, "car1_truth",
                     [row["car1_error_m"] for row in rows])
    _describe_errors(summary, "car2_truth",
                     [row["car2_error_m"] for row in rows])
    _describe_errors(summary, "reciprocal_mean_truth",
                     [row["reciprocal_mean_error_m"] for row in rows])
    return summary


PAIR_FIELDS = [
    "pair_index", "pair_time_s", "elapsed_pair_time_s",
    "car1_message_index", "car2_message_index",
    "car1_bag_time_s", "car2_bag_time_s", "bag_time_delta_s",
    "car1_header_time_s", "car2_header_time_s", "header_time_delta_s",
    "car1_bag_header_offset_s", "car2_bag_header_offset_s",
    "car1_usable", "car2_usable", "both_usable",
    "car1_range_m", "car2_range_m", "reciprocal_difference_m",
    "reciprocal_abs_difference_m", "reciprocal_mean_m", "truth_range_m",
    "car1_error_m", "car2_error_m", "reciprocal_mean_error_m",
]


def write_pairs_csv(path, rows):
    with _csv_open(path) as stream:
        writer = csv.DictWriter(stream, fieldnames=PAIR_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_text(path, result):
    with open(path, "w") as stream:
        for key in ["car1_bag", "car1_sha256", "car2_bag", "car2_sha256",
                    "car1_topic", "car2_topic", "pair_tolerance_s",
                    "truth_source"]:
            stream.write("%s: %s\n" % (key, result[key]))
        for key in sorted(result["summary"]):
            stream.write("%s: %s\n" % (key, result["summary"][key]))
        stream.write("pairing_basis: bag reception time\n")
        stream.write("timestamp_correction: none\n")
        stream.write("filtering: none\n")


def plot_pairs(path, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    times = [row["elapsed_pair_time_s"] for row in rows]
    nan = float("nan")
    figure, axes = pyplot.subplots(3, 1, figsize=(13, 10), sharex=True)
    axes[0].plot(times, [row["car1_range_m"] if row["car1_range_m"] is not None
                         else nan for row in rows], label="Car1 UWB", linewidth=0.8)
    axes[0].plot(times, [row["car2_range_m"] if row["car2_range_m"] is not None
                         else nan for row in rows], label="Car2 UWB", linewidth=0.8)
    if any(row["truth_range_m"] is not None for row in rows):
        axes[0].plot(times, [row["truth_range_m"] if row["truth_range_m"] is not None
                             else nan for row in rows], "k--", label="Truth")
    axes[0].set_ylabel("Range (m)")
    axes[0].legend()

    axes[1].plot(times, [row["reciprocal_abs_difference_m"]
                         if row["reciprocal_abs_difference_m"] is not None
                         else nan for row in rows], linewidth=0.8)
    axes[1].set_ylabel("|Car2 - Car1| (m)")

    axes[2].plot(times, [1000.0 * row["header_time_delta_s"]
                         if row["header_time_delta_s"] is not None
                         else nan for row in rows], linewidth=0.8)
    axes[2].set_ylabel("Header delta (ms)")
    axes[2].set_xlabel("Elapsed paired bag time (s)")
    for axis in axes:
        axis.grid(True, alpha=0.3)
    figure.suptitle("Two-car reciprocal UWB comparison")
    figure.tight_layout(rect=[0, 0, 1, 0.97])
    figure.savefig(path, dpi=150)
    pyplot.close(figure)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("car1_bag", help="bag containing the Car1 range topic")
    parser.add_argument("--car2-bag", help="optional separate Car2 bag")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--car1-topic", default="/car1/uwb/ranges")
    parser.add_argument("--car2-topic", default="/car2/uwb/ranges")
    parser.add_argument("--car1-id", default="node_0")
    parser.add_argument("--car2-id", default="node_1")
    parser.add_argument("--pair-tolerance-s", type=float, default=0.03)
    parser.add_argument("--truth-topic")
    parser.add_argument("--truth-tolerance-s", type=float, default=0.03)
    parser.add_argument("--truth-distance-m", type=float)
    args = parser.parse_args(argv)

    car2_path = args.car2_bag or args.car1_bag
    for path in [args.car1_bag, car2_path]:
        if not os.path.isfile(path):
            parser.error("bag does not exist: %s" % path)
    if args.pair_tolerance_s < 0.0 or args.truth_tolerance_s < 0.0:
        parser.error("time tolerances must be non-negative")
    if args.truth_topic and args.truth_distance_m is not None:
        parser.error("choose either --truth-topic or --truth-distance-m")

    car1 = read_range_records(
        args.car1_bag, args.car1_topic, args.car1_id, args.car2_id)
    car2 = read_range_records(
        car2_path, args.car2_topic, args.car2_id, args.car1_id)
    if not car1 or not car2:
        print("ERROR: both car range topics must contain messages", file=sys.stderr)
        return 2
    rows = build_pairs(car1, car2, args.pair_tolerance_s)
    if not rows:
        print("ERROR: no messages paired within %.6f s" %
              args.pair_tolerance_s, file=sys.stderr)
        return 2

    truth_source = "none"
    if args.truth_distance_m is not None:
        try:
            attach_constant_truth(rows, args.truth_distance_m)
        except ValueError as error:
            parser.error(str(error))
        truth_source = "constant:%.12g_m" % args.truth_distance_m
    elif args.truth_topic:
        truth = read_truth_records(args.car1_bag, args.truth_topic)
        if not truth:
            print("ERROR: truth topic contains no finite messages: %s" %
                  args.truth_topic, file=sys.stderr)
            return 2
        attach_topic_truth(rows, truth, args.truth_tolerance_s)
        if not any(row["truth_range_m"] is not None for row in rows):
            print("ERROR: no truth messages paired within %.6f s" %
                  args.truth_tolerance_s, file=sys.stderr)
            return 2
        truth_source = "topic:%s" % args.truth_topic

    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)
    result = {
        "car1_bag": os.path.basename(args.car1_bag),
        "car1_sha256": sha256_file(args.car1_bag),
        "car2_bag": os.path.basename(car2_path),
        "car2_sha256": sha256_file(car2_path),
        "car1_topic": args.car1_topic,
        "car2_topic": args.car2_topic,
        "pair_tolerance_s": args.pair_tolerance_s,
        "truth_source": truth_source,
        "summary": summarize_pairs(car1, car2, rows),
    }
    write_pairs_csv(os.path.join(args.output_dir, "paired_measurements.csv"), rows)
    write_summary_text(os.path.join(args.output_dir, "summary.txt"), result)
    with open(os.path.join(args.output_dir, "summary.json"), "w") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    plot_pairs(os.path.join(args.output_dir, "two_car_comparison.png"), rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
