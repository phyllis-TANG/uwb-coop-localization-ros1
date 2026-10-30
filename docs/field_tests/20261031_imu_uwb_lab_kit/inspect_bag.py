#!/usr/bin/env python3
"""Read-only ROS1/ROS2 IMU screening; never declares calibration success."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from rosbags.highlevel import AnyReader


def inspect(args):
    report = {"bag": str(args.bag.resolve()), "screening_only": True,
              "static_interval_basis": "seconds since bag receipt start; operator-confirmed only",
              "imu": {}}
    with args.bag.open('rb') as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    report['sha256'] = digest.hexdigest()
    with AnyReader([args.bag]) as reader:
        report['topics'] = [{"topic": c.topic, "type": c.msgtype, "count": c.msgcount}
                            for c in reader.connections]
        topics = sorted({c.topic for c in reader.connections if c.msgtype == 'sensor_msgs/msg/Imu'})
        if args.topic:
            missing = set(args.topic) - set(topics)
            if missing:
                raise ValueError(f'IMU topics not present: {sorted(missing)}')
            topics = args.topic
        if not topics:
            raise ValueError('No sensor_msgs/Imu topics found')
        for topic in topics:
            values, frames = [], set()
            for c, ns, raw in reader.messages(connections=[c for c in reader.connections if c.topic == topic]):
                m = reader.deserialize(raw, c.msgtype)
                q = m.orientation
                quat = np.array([q.x, q.y, q.z, q.w], dtype=float)
                norm = float(np.linalg.norm(quat))
                heading = np.nan
                # -1 means orientation is not provided; do not infer yaw from it.
                if np.isfinite(norm) and norm > 1e-12 and m.orientation_covariance[0] != -1:
                    x, y, z, w = quat / norm
                    heading = np.arctan2(2 * (w*z + x*y), 1 - 2 * (y*y + z*z))
                receipt = (ns - reader.start_time) * 1e-9
                header = m.header.stamp.sec + m.header.stamp.nanosec * 1e-9
                w = m.angular_velocity
                a = m.linear_acceleration
                values.append([receipt, header, norm, heading, w.x, w.y, w.z, a.x, a.y, a.z])
                frames.add(m.header.frame_id)
            data = np.asarray(values)
            if not len(data):
                report['imu'][topic] = {'count': 0}
                continue
            dt = np.diff(data[:, 0])
            dh = np.diff(data[:, 1])
            span = data[-1, 0] - data[0, 0]
            valid_norms = data[np.isfinite(data[:, 2]), 2]
            item = {'count': len(data), 'frames': sorted(frames),
                    'receipt_span_s': float(span),
                    'receipt_rate_hz': float((len(data)-1)/span) if span > 0 else None,
                    'max_receipt_gap_s': float(dt.max()) if len(dt) else None,
                    'receipt_gaps_over_0p2s': int((dt > .2).sum()),
                    'header_nonincreasing_count': int((dh <= 0).sum()),
                    'zero_header_count': int((data[:, 1] == 0).sum()),
                    'invalid_or_unreported_orientation_count': int((~np.isfinite(data[:, 3])).sum()),
                    'nonfinite_gyro_accel_rows': int((~np.isfinite(data[:, 4:]).all(axis=1)).sum()),
                    'quaternion_norm_range': [float(valid_norms.min()), float(valid_norms.max())] if len(valid_norms) else None}
            if args.static_start is not None:
                subset = data[(data[:, 0] >= args.static_start) & (data[:, 0] <= args.static_end)]
                finite = subset[np.isfinite(subset[:, 4:7]).all(axis=1)]
                result = {'requested_interval_s': [args.static_start, args.static_end], 'sample_count': len(subset),
                          'warning': 'Stationarity must be independently confirmed; this is not a calibrated bias.'}
                if len(finite):
                    result['gyro_xyz_mean_deg_s'] = np.degrees(finite[:, 4:7].mean(axis=0)).tolist()
                    result['gyro_xyz_std_deg_s'] = np.degrees(finite[:, 4:7].std(axis=0)).tolist()
                if len(subset) >= 2 and np.isfinite(subset[:, 3]).all():
                    heading = np.unwrap(subset[:, 3])
                    result['yaw_first_to_last_deg'] = float(np.degrees(heading[-1] - heading[0]))
                result['covers_requested_interval_within_0p2s'] = bool(len(subset) and subset[0, 0] <= args.static_start+.2 and subset[-1, 0] >= args.static_end-.2)
                item['operator_declared_static'] = result
            report['imu'][topic] = item
    # Replace any accidental non-finite numeric values with null in strict JSON.
    def clean(value):
        if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list): return [clean(v) for v in value]
        if isinstance(value, float) and not np.isfinite(value): return None
        return value
    return clean(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bag', type=Path)
    parser.add_argument('--topic', action='append', help='Select IMU topic; repeat for multiple topics')
    parser.add_argument('--static-start', type=float)
    parser.add_argument('--static-end', type=float)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if (args.static_start is None) != (args.static_end is None):
        parser.error('Provide both --static-start and --static-end')
    if args.static_start is not None:
        if not np.isfinite([args.static_start, args.static_end]).all() or not 0 <= args.static_start < args.static_end:
            parser.error('Static interval must be finite and satisfy 0 <= start < end')
        if not args.topic:
            parser.error('Static screening requires explicit --topic to avoid treating a moving car as stationary')
    if args.output.resolve() == args.bag.resolve():
        parser.error('Output must not overwrite input bag')
    result = inspect(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    print(f"Wrote {args.output}: {len(result['imu'])} IMU topics; screening only.")


if __name__ == '__main__':
    main()
