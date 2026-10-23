#!/usr/bin/env python3
"""Raw UWB, reciprocal peer, Odom and clock diagnostics; no graph fitting."""
import argparse
import collections
import json
from pathlib import Path
import sys

import numpy as np
import scipy

from run_two_car_updated_comparison import write_csv, write_json
from two_car_updated_comparison import CARS, PEERS, TAGS, read_bag, sha256, unique_positive_ranges
from two_car_stationary_confidence import read_odom_motion

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT/'docs/field_tests/two_car_range_diagnostics_20261023'


def raw_metadata(path):
    from rosbags.highlevel import AnyReader
    rows, quality, tags = {c: [] for c in CARS}, collections.defaultdict(list), collections.defaultdict(set)
    with AnyReader([Path(path)]) as reader:
        connections = [c for c in reader.connections if c.topic in {'/'+car+'/uwb/ranges' for car in CARS}]
        for connection, ns, raw in reader.messages(connections=connections):
            car = connection.topic.split('/')[1]
            msg = reader.deserialize(raw, connection.msgtype)
            receipt = ns*1e-9-reader.start_time*1e-9
            header = msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9-reader.start_time*1e-9
            valid, duplicates = unique_positive_ranges((v.anchor_id, v.range) for v in msg.ranges)
            rows[car].append(dict(receipt_s=receipt, header_s=header, seq=int(msg.header.seq),
                                 values=valid, duplicate_groups=duplicates))
            tags[car].add(msg.tag_id)
            for v in msg.ranges:
                quality[car+'/'+v.anchor_id].append(float(v.quality))
    return rows, {key: dict(samples=len(v), finite_quality_samples=int(np.isfinite(v).sum()))
                  for key, v in quality.items()}, {car: sorted(v) for car, v in tags.items()}


def describe(values):
    a = np.asarray(values, dtype=float)
    return dict(count=len(a), median=float(np.median(a)), p05=float(np.percentile(a, 5)),
                p95=float(np.percentile(a, 95)), min=float(a.min()), max=float(a.max()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=DOCS/'diagnostic_plan.json')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--dependency-path', type=Path)
    args = parser.parse_args()
    if args.dependency_path: sys.path.append(str(args.dependency_path.resolve()))
    plan = json.loads(args.plan.read_text())
    parent = json.loads((ROOT/plan['parent_protocol_path']).read_text())
    calibration = json.loads((ROOT/'docs/field_tests/two_car_updated_comparison_20261022/results/calibration.json').read_text())
    biases = calibration['applied_biases_m']
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output/'diagnostic_plan.json', plan)
    windows, clocks, peers, summaries = [], [], [], []
    for kind in ['static', 'dynamic']:
        for case in plan[kind+'_cases']:
            print('Diagnosing '+case['id'], flush=True)
            run = read_bag(ROOT/case['path'], case['sha256'])
            metadata, quality, tags = raw_metadata(ROOT/case['path'])
            motion = read_odom_motion(ROOT/case['path'], case['sha256'])
            for car in CARS:
                assert tags[car] == [TAGS[car]]
                assert [(r['receipt_s'], r['values']) for r in metadata[car]] == run['uwb'][car]
                np.testing.assert_array_equal(motion[car][:, :4], run['odom'][car])
            record = dict(id=case['id'], kind=kind, path=case['path'], sha256=case['sha256'],
                duration_s=run['duration_s'], quality=quality, tags=tags,
                timing=run['diagnostics']['timing'], cars={})
            times = np.arange(1., int(np.floor(run['duration_s'])))
            for car in CARS:
                rawrows, odom = metadata[car], motion[car]
                xy = odom[:, 1:3]
                record['cars'][car] = dict(
                    raw_odom_path_m=float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum()),
                    odom_yaw_change_deg=float(np.degrees(np.unwrap(odom[:, 3])[-1]-np.unwrap(odom[:, 3])[0])),
                    twist_linear_max_mps=float(np.linalg.norm(odom[:, 4:6], axis=1).max()),
                    twist_angular_max_radps=float(np.abs(odom[:, 6]).max()), links={})
                for key in list(sorted(parent['anchors_xyz_m']))+[PEERS[car]]:
                    vals = [r['values'][key] for r in rawrows if key in r['values']]
                    head = [r['values'][key] for r in rawrows if key in r['values'] and r['receipt_s'] <= 5.]
                    tail = [r['values'][key] for r in rawrows if key in r['values'] and r['receipt_s'] >= run['duration_s']-5.]
                    geometry = None
                    bias = biases[car].get(key, 0.)
                    if kind == 'static':
                        other = (parent['anchors_xyz_m'][key] if key in parent['anchors_xyz_m']
                                 else case['antenna_xyz_m'][CARS[1-CARS.index(car)]])
                        geometry = float(np.linalg.norm(np.asarray(case['antenna_xyz_m'][car])-other))
                    record['cars'][car]['links'][key] = dict(raw=describe(vals),
                        first_five_median_m=float(np.median(head)) if head else None,
                        last_five_median_m=float(np.median(tail)) if tail else None,
                        applied_bias_m=bias, static_reference_geometry_m=geometry,
                        corrected_median_minus_geometry_m=float(np.median(vals)-bias-geometry) if geometry else None)
                for center in times:
                    rows = [r for r in rawrows if abs(r['receipt_s']-center) <= plan['diagnostic_bin_half_width_s']]
                    o = odom[np.abs(odom[:, 0]-center) <= plan['diagnostic_bin_half_width_s']]
                    if len(rows):
                        offsets = np.asarray([r['receipt_s']-r['header_s'] for r in rows])*1000
                        clocks.append(dict(bag=case['id'], kind=kind, car=car, center_s=float(center),
                            frames=len(rows), receipt_minus_header_median_ms=float(np.median(offsets)),
                            receipt_minus_header_min_ms=float(offsets.min()), receipt_minus_header_max_ms=float(offsets.max()),
                            header_nonincreasing=int(np.sum(np.diff([r['header_s'] for r in rows]) <= 0)),
                            sequence_nonincreasing=int(np.sum(np.diff([r['seq'] for r in rows]) <= 0))))
                    for key in list(sorted(parent['anchors_xyz_m']))+[PEERS[car]]:
                        vals = [r['values'][key] for r in rows if key in r['values']]
                        if len(vals) < plan['minimum_samples_per_link']: continue
                        allstats = record['cars'][car]['links'][key]
                        geometry, bias = allstats['static_reference_geometry_m'], allstats['applied_bias_m']
                        median = float(np.median(vals))
                        windows.append(dict(bag=case['id'], kind=kind, car=car, link=key,
                            center_s=float(center), samples=len(vals), raw_median_m=median,
                            raw_p05_m=float(np.percentile(vals, 5)), raw_p95_m=float(np.percentile(vals, 95)),
                            corrected_median_m=median-bias, static_geometry_m=geometry,
                            corrected_minus_static_geometry_m=median-bias-geometry if geometry else None,
                            odom_xy_path_in_bin_m=float(np.linalg.norm(np.diff(o[:, 1:3], axis=0), axis=1).sum()) if len(o)>1 else 0.,
                            odom_twist_max_mps=float(np.linalg.norm(o[:, 4:6], axis=1).max()) if len(o) else None,
                            odom_yaw_twist_max_radps=float(np.abs(o[:, 6]).max()) if len(o) else None))
            for center in times:
                values = []
                for car in CARS:
                    vals = [r['values'][PEERS[car]] for r in metadata[car]
                            if abs(r['receipt_s']-center) <= plan['diagnostic_bin_half_width_s'] and PEERS[car] in r['values']]
                    values.append(float(np.median(vals)) if len(vals)>=plan['minimum_samples_per_link'] else None)
                peers.append(dict(bag=case['id'], kind=kind, center_s=float(center),
                    car1_to_car2_m=values[0], car2_to_car1_m=values[1],
                    directional_difference_m=values[0]-values[1] if None not in values else None))
            summaries.append(record)
            write_json(args.output/'raw_summary.json', dict(recordings=summaries,
                range_unit='metres from embedded UwbRange definition', quality_note='Finite availability only; no inferred RSSI or NLOS label.',
                no_calibration_or_graph_fit=True))
    write_csv(args.output/'range_windows.csv', windows)
    write_csv(args.output/'clock_windows.csv', clocks)
    write_csv(args.output/'peer_windows.csv', peers)
    write_json(args.output/'diagnostic_manifest.json', dict(
        source_sha256=sha256(Path(__file__)), plan_sha256=sha256(args.plan),
        data_sha256={c['path']: sha256(ROOT/c['path']) for kind in ['static', 'dynamic'] for c in plan[kind+'_cases']},
        range_window_rows=len(windows), clock_rows=len(clocks), peer_rows=len(peers),
        raw_frontend_exactly_verified=True))
    print('Raw diagnostics completed', flush=True)


if __name__ == '__main__': main()
