#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Offline analysis for UwbRangeArray rosbag recordings.

The script is intentionally read-only: it only opens bags for reading and
writes derived CSV, JSON, text, and PNG artifacts to a separate output
directory.  Python 2.7 compatibility is required by ROS Melodic.
"""

from __future__ import division, print_function

import argparse
import csv
import hashlib
import json
import math
import os
import sys


TOPIC = "/uwb/ranges"


def _finite(value):
    return not (math.isnan(value) or math.isinf(value))


def percentile(values, percent):
    """Return a linearly interpolated percentile (NumPy's linear method)."""
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


def summarize_records(records):
    """Summarize extracted records without filtering or spike removal.

    Jump statistics require two consecutive ROS messages to both contain a
    usable target range.  A missing-target message breaks the sequence; values
    on opposite sides of it are never paired.  The definition is emitted in
    every summary.
    """
    frame_count = len(records)
    valid = [row["range_m"] for row in records if row["range_m"] is not None]
    no_usable = frame_count - len(valid)
    bag_times = [row["bag_time_s"] for row in records]
    offsets = [row["bag_header_offset_s"] for row in records
               if row["bag_header_offset_s"] is not None]
    jumps = [abs(records[index]["range_m"] - records[index - 1]["range_m"])
             for index in range(1, len(records))
             if records[index - 1]["range_m"] is not None and
             records[index]["range_m"] is not None]

    summary = {
        "frames": frame_count,
        "usable_target_frames": len(valid),
        "no_usable_target": no_usable,
        "valid_frame_percent": (
            100.0 * len(valid) / frame_count if frame_count else None),
        "duration_s": None,
        "frequency_hz": None,
        "mean_m": None,
        "median_m": None,
        "std_m": None,
        "min_m": None,
        "max_m": None,
        "bag_header_offset_mean_s": None,
        "bag_header_offset_median_s": None,
        "bag_header_offset_min_s": None,
        "bag_header_offset_max_s": None,
        "jump_definition": "consecutive_ros_messages_with_usable_target",
        "jump_count": len(jumps),
        "jump_median_m": percentile(jumps, 50),
        "jump_p95_m": percentile(jumps, 95),
        "jump_p99_m": percentile(jumps, 99),
        "jump_max_m": max(jumps) if jumps else None,
        "jump_gt_0_10_percent": (
            100.0 * sum(value > 0.10 for value in jumps) / len(jumps)
            if jumps else None),
        "jump_gt_0_25_percent": (
            100.0 * sum(value > 0.25 for value in jumps) / len(jumps)
            if jumps else None),
    }
    if len(bag_times) >= 2:
        duration = bag_times[-1] - bag_times[0]
        summary["duration_s"] = duration
        if duration > 0.0:
            summary["frequency_hz"] = (frame_count - 1) / duration
    if valid:
        mean = sum(valid) / len(valid)
        summary.update({
            "mean_m": mean,
            "median_m": percentile(valid, 50),
            "std_m": math.sqrt(
                sum((value - mean) ** 2 for value in valid) / len(valid)),
            "min_m": min(valid),
            "max_m": max(valid),
        })
    if offsets:
        summary.update({
            "bag_header_offset_mean_s": sum(offsets) / len(offsets),
            "bag_header_offset_median_s": percentile(offsets, 50),
            "bag_header_offset_min_s": min(offsets),
            "bag_header_offset_max_s": max(offsets),
        })
    return summary


def extract_target_range(message, tag_id, target_id):
    """Return the finite target range, or None when no usable target exists."""
    if getattr(message, "tag_id", None) != tag_id:
        return None
    for measurement in getattr(message, "ranges", []):
        if getattr(measurement, "anchor_id", None) != target_id:
            continue
        value = float(measurement.range)
        return value if _finite(value) else None
    return None


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def read_bag(path, topic, tag_id, target_id):
    try:
        import rosbag
    except ImportError:
        raise RuntimeError("rosbag is unavailable; source the ROS Melodic environment")

    records = []
    with rosbag.Bag(path, "r") as bag:
        for index, (_, message, bag_stamp) in enumerate(
                bag.read_messages(topics=[topic])):
            bag_time = bag_stamp.to_sec()
            header = getattr(message, "header", None)
            header_stamp = getattr(header, "stamp", None)
            header_time = header_stamp.to_sec() if header_stamp is not None else None
            records.append({
                "message_index": index,
                "bag_time_s": bag_time,
                "elapsed_bag_time_s": 0.0,
                "header_time_s": header_time,
                "bag_header_offset_s": (
                    bag_time - header_time if header_time is not None else None),
                "range_m": extract_target_range(message, tag_id, target_id),
            })
    if records:
        first_time = records[0]["bag_time_s"]
        for row in records:
            row["elapsed_bag_time_s"] = row["bag_time_s"] - first_time
    return records


def _csv_open(path):
    if sys.version_info[0] < 3:
        return open(path, "wb")
    return open(path, "w", newline="")


def write_records_csv(path, records):
    fields = ["message_index", "bag_time_s", "elapsed_bag_time_s",
              "header_time_s", "bag_header_offset_s", "target_usable",
              "range_m"]
    with _csv_open(path) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in records:
            output = dict(row)
            output["target_usable"] = int(row["range_m"] is not None)
            writer.writerow(output)


def write_summary_text(path, result):
    summary = result["summary"]
    with open(path, "w") as stream:
        stream.write("bag_file: %s\n" % result["bag_file"])
        stream.write("sha256: %s\n" % result["sha256"])
        for key in sorted(summary):
            stream.write("%s: %s\n" % (key, summary[key]))
        stream.write("quality_note: quality is NaN and is not analyzed\n")
        stream.write("time_basis: bag reception time\n")
        stream.write("filtering: none\n")


def plot_result(path, title, records):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    valid_x = [row["elapsed_bag_time_s"] for row in records
               if row["range_m"] is not None]
    valid_y = [row["range_m"] for row in records
               if row["range_m"] is not None]
    missing_x = [row["elapsed_bag_time_s"] for row in records
                 if row["range_m"] is None]
    figure, axes = pyplot.subplots(figsize=(12, 5))
    axes.plot(valid_x, valid_y, linewidth=0.8, label="Raw range")
    if valid_y and missing_x:
        floor = min(valid_y)
        axes.plot(missing_x, [floor] * len(missing_x), "|", color="red",
                  markersize=12, label="No usable target range")
    axes.set_title(title)
    axes.set_xlabel("Elapsed bag reception time (s)")
    axes.set_ylabel("Range (m)")
    axes.grid(True, alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    pyplot.close(figure)


def plot_comparison(path, plot_inputs):
    """Plot all recordings without joining their independent time axes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    columns = 2 if len(plot_inputs) > 1 else 1
    rows = int(math.ceil(len(plot_inputs) / float(columns)))
    figure, axes = pyplot.subplots(rows, columns, figsize=(14, 4.5 * rows),
                                   squeeze=False)
    for index, (title, records) in enumerate(plot_inputs):
        axis = axes[index // columns][index % columns]
        valid_x = [row["elapsed_bag_time_s"] for row in records
                   if row["range_m"] is not None]
        valid_y = [row["range_m"] for row in records
                   if row["range_m"] is not None]
        missing_x = [row["elapsed_bag_time_s"] for row in records
                     if row["range_m"] is None]
        axis.plot(valid_x, valid_y, linewidth=0.7, label="Raw range")
        if valid_y and missing_x:
            axis.plot(missing_x, [min(valid_y)] * len(missing_x), "|",
                      color="red", markersize=10,
                      label="No usable target range")
        axis.set_title(title)
        axis.set_xlabel("Elapsed bag reception time (s)")
        axis.set_ylabel("Range (m)")
        axis.grid(True, alpha=0.3)
        axis.legend()
    for index in range(len(plot_inputs), rows * columns):
        axes[index // columns][index % columns].set_visible(False)
    figure.suptitle("UWB raw ranges: node_1 to node_0")
    figure.tight_layout(rect=[0, 0.03, 1, 0.97])
    figure.savefig(path, dpi=150)
    pyplot.close(figure)


def verify_expected(results, expectation_path):
    with open(expectation_path, "r") as stream:
        expectations = json.load(stream)
    failures = []
    by_name = dict((result["experiment"], result) for result in results)
    for name, expected in expectations["experiments"].items():
        if name not in by_name:
            failures.append("%s: input bag not provided" % name)
            continue
        actual = by_name[name]["summary"]
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            tolerance = expectations.get("float_tolerance", 0.00015)
            if isinstance(expected_value, int):
                matches = actual_value == expected_value
            else:
                matches = (actual_value is not None and
                           abs(actual_value - expected_value) <= tolerance)
            if not matches:
                failures.append("%s.%s expected %s, got %s" %
                                (name, key, expected_value, actual_value))
    return failures


def experiment_name(path):
    return os.path.splitext(os.path.basename(path))[0].split("_")[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bags", nargs="+", help="input rosbag files")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--topic", default=TOPIC)
    parser.add_argument("--tag-id", default="node_1")
    parser.add_argument("--target-id", default="node_0")
    parser.add_argument("--expectations", help="optional baseline JSON")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.output_dir):
        os.makedirs(args.output_dir)
    results = []
    plot_inputs = []
    for bag_path in args.bags:
        if not os.path.isfile(bag_path):
            parser.error("bag does not exist: %s" % bag_path)
        name = experiment_name(bag_path)
        records = read_bag(bag_path, args.topic, args.tag_id, args.target_id)
        result = {
            "experiment": name,
            "bag_file": os.path.basename(bag_path),
            "sha256": sha256_file(bag_path),
            "topic": args.topic,
            "tag_id": args.tag_id,
            "target_id": args.target_id,
            "summary": summarize_records(records),
        }
        results.append(result)
        plot_inputs.append((name, records))
        prefix = os.path.join(args.output_dir, os.path.splitext(
            os.path.basename(bag_path))[0])
        write_records_csv(prefix + ".csv", records)
        write_summary_text(prefix + "_summary.txt", result)
        plot_result(prefix + ".png", name, records)

    plot_comparison(os.path.join(args.output_dir, "ranges_comparison.png"),
                    plot_inputs)

    with open(os.path.join(args.output_dir, "summary.json"), "w") as stream:
        json.dump({"results": results}, stream, indent=2, sort_keys=True)
        stream.write("\n")
    summary_fields = ["experiment", "bag_file", "sha256", "frames",
                      "usable_target_frames", "no_usable_target",
                      "valid_frame_percent", "frequency_hz", "mean_m",
                      "median_m", "std_m", "min_m", "max_m",
                      "bag_header_offset_mean_s", "jump_median_m",
                      "jump_p95_m", "jump_p99_m", "jump_gt_0_10_percent",
                      "jump_gt_0_25_percent", "jump_max_m"]
    with _csv_open(os.path.join(args.output_dir, "summary.csv")) as stream:
        writer = csv.DictWriter(stream, fieldnames=summary_fields)
        writer.writeheader()
        for result in results:
            row = dict((key, result.get(key, result["summary"].get(key)))
                       for key in summary_fields)
            writer.writerow(row)

    if args.expectations:
        failures = verify_expected(results, args.expectations)
        if failures:
            for failure in failures:
                print("BASELINE FAIL: %s" % failure, file=sys.stderr)
            return 2
        print("Baseline verification passed for all supplied experiments")
    return 0


if __name__ == "__main__":
    sys.exit(main())
