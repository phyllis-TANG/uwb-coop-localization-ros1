#!/usr/bin/env python3
"""Frozen D0/D1 joint factor graph. Virtual receipt-ordered replay, no ROS."""
import argparse
import collections
import csv
import gzip
import json
from pathlib import Path
import sys
import time
import numpy as np
from frontend import JointReplay
from io_utils import append, dump, environment, git_state, outside, outputs, read_jsonl, sha, sources, utc
from legacy import CARS, antenna

COLUMNS = ['experiment_id', 'method_id', 'vehicle_id', 'state_time_s', 'availability_cutoff_s',
    'state_epoch_ns', 'availability_cutoff_epoch_ns', 'frame_id', 'base_x_m', 'base_y_m', 'yaw_rad',
    'antenna_x_m', 'antenna_y_m', 'antenna_z_m', 'valid', 'finite_output', 'status', 'accepted_graph',
    'peer_median_m', 'reverse_peer_median_m', 'peer_sample_count', 'peer_factor_used',
    'graph_states', 'scalar_variables', 'marginalizations', 'dependency_receipt_max_s',
    'solve_wall_s', 'marginal_wall_s', 'update_wall_s', 'estimated_worker_queue_s', 'timing_mode']


def validate(config):
    reference = json.loads(Path(__file__).with_name('config.json').read_text())
    if config.get('scope') != 'synthetic':
        raise ValueError('BLOCKED: field interface needs independently accepted geometry/clock input contract; holdouts excluded')
    for key in ('replay', 'optimizer', 'frontend', 'fixed_lag_s', 'peer', 'extensions'):
        if config[key] != reference[key]: raise ValueError('Frozen configuration differs: ' + key)
    if set(config['models']) != set(CARS): raise ValueError('Two models required')
    for car in CARS:
        m = config['models'][car]; ref = reference['models'][car]
        for key in ('graph_parameters', 'anchors_xyz_m', 'range_bias_m', 'base_to_antenna_body_xy_m', 'antenna_height_m'):
            if m[key] != ref[key]: raise ValueError('Frozen synthetic model differs: '+car+'/'+key)
        if not np.isfinite(np.r_[m['start_antenna_xyz_m'], m['initial_heading_deg']]).all():
            raise ValueError('Invalid initial prior')


def execute(events, config, arm, sink):
    validate(config); replay = None
    for raw in events:
        if replay is None: replay = JointReplay(config, arm, sink, raw['receive_epoch_ns'])
        replay.ingest(raw)
    if replay is None: raise ValueError('Empty events')
    replay.finish()
    return replay


def run(events_path, config_path, arm, output, max_seconds=600.):
    started = time.perf_counter(); root = outside(output)
    root.mkdir(parents=True, exist_ok=False)
    run_info = dict(schema_version=1, status='IN_PROGRESS', role='two_car_fixed_lag_fgo_v1',
        run_id=root.name, created_at_utc=utc(), method_id=arm, timing_mode='virtual',
        command_argv=sys.argv, **git_state(), environment=environment(), blocked_reasons=[],
        limitations=['virtual reception wait/compute queue; no vehicle end-to-end timing',
                     'synthetic only; no field RMSE/ATE', 'fixed uncertain extrinsics, not calibrated online'])
    dump(root/'run.json', run_info)
    try:
        config = json.loads(Path(config_path).read_text()); validate(config)
        lock = sources()
        run_info.update(source_sha256=lock, config_sha256=sha(config_path),
                        inputs=[dict(asset_id='message_events', relative_path=Path(events_path).name, sha256=sha(events_path))])
        dump(root/'config.json', config); dump(root/'run.json', run_info)
        counters = collections.Counter(); elapsed_updates = []; peer_factors = 0
        with (root/'published.csv').open('x', newline='') as stream, \
             gzip.open(root/'updates.jsonl.gz', 'xt') as journal, \
             gzip.open(root/'input_decisions.jsonl.gz', 'xt') as decisions:
            writer = csv.DictWriter(stream, fieldnames=COLUMNS, lineterminator='\n'); writer.writeheader()
            def sink(row):
                nonlocal peer_factors
                counters[row['status']] += 1; elapsed_updates.append(row['update_wall_s'])
                peer_factors += row['peer_factor_used']
                for i, car in enumerate(CARS):
                    p = None if row['pose'] is None else row['pose'][3*i:3*i+3]
                    xy = None if p is None else antenna(p, config['models'][car]['base_to_antenna_body_xy_m'])
                    out = {k: row.get(k) for k in COLUMNS}
                    out.update(experiment_id=replay.case_id, vehicle_id=car, frame_id='synthetic_room',
                        base_x_m=p[0] if p else None, base_y_m=p[1] if p else None,
                        yaw_rad=p[2] if p else None, antenna_x_m=float(xy[0]) if xy is not None else None,
                        antenna_y_m=float(xy[1]) if xy is not None else None,
                        antenna_z_m=config['models'][car]['antenna_height_m'] if p else None,
                        valid=bool(row['accepted_graph']), finite_output=p is not None)
                    writer.writerow(out)
                append(journal, row)
            replay = None
            for raw in read_jsonl(events_path):
                if time.perf_counter()-started > max_seconds: raise TimeoutError('Bounded replay runtime exceeded')
                if replay is None:
                    replay = JointReplay(config, arm, sink, raw['receive_epoch_ns'])
                    run_info['epoch_origin_ns'] = replay.origin_ns
                reason = replay.ingest(raw)
                append(decisions, dict(record_index=raw['record_index'], receive_epoch_ns=raw['receive_epoch_ns'],
                    header_epoch_ns=raw.get('header_epoch_ns'), source_file_sha256=raw.get('source_file_sha256'),
                    topic=raw.get('topic'), source_observation_id=raw.get('source_observation_id'), decision=reason))
            if replay is None: raise ValueError('Empty events')
            replay.finish()
        dump(root/'final_active_graph.json', replay.graph.snapshot())
        dump(root/'summary.json', dict(method_id=arm, publications=replay.output_count, status_counts=dict(counters),
            counters=dict(replay.counters), frontend_counters={c: dict(replay.binners[c].counters) for c in CARS},
            peak_solve_keyframes=replay.graph.peak_solve_states, peak_transient_keyframes=replay.graph.peak_transient_states,
            peak_scalar_variables=6*replay.graph.peak_solve_states, marginalizations=replay.graph.marginalizations,
            sensor_peaks={c: replay.binners[c].sensor_peaks for c in CARS}, peer_buffer_peak=replay.peer_peak,
            pending_peak=replay.pending_peak, peer_factors=peer_factors,
            update_wall_total_s=float(sum(elapsed_updates)), update_wall_p95_s=float(np.percentile(elapsed_updates, 95)) if elapsed_updates else None,
            elapsed_s=time.perf_counter()-started, timing_mode='virtual'))
        if lock != sources(): raise ValueError('Source changed during run')
        run_info.update(status='DONE', finished_at_utc=utc(), elapsed_s=time.perf_counter()-started, outputs=outputs(root))
        dump(root/'run.json', run_info)
        return run_info
    except (Exception, KeyboardInterrupt) as error:
        run_info.update(status='FAILED', error=type(error).__name__+': '+str(error),
                        elapsed_s=time.perf_counter()-started, outputs=outputs(root))
        dump(root/'run.json', run_info)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events-jsonl', required=True, type=Path); p.add_argument('--config', required=True, type=Path)
    p.add_argument('--arm', choices=['D0', 'D1'], default='D0'); p.add_argument('--output', required=True, type=Path)
    p.add_argument('--max-seconds', type=float, default=600.)
    a = p.parse_args()
    try:
        r = run(a.events_jsonl, a.config, a.arm, a.output, a.max_seconds)
        print(json.dumps({k: r[k] for k in ('status', 'method_id', 'elapsed_s')})); return 0
    except Exception as error:
        print(type(error).__name__+': '+str(error), file=sys.stderr); return 1


if __name__ == '__main__': raise SystemExit(main())
