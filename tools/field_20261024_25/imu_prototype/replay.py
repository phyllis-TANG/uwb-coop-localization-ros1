#!/usr/bin/env python3
"""Contract CLI: causal JSONL replay of legacy or optional four-state/car modes."""
import argparse
from collections import Counter
import copy
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import time

from configuration import mode_of, validate
from imu_filter import make_filter
from legacy import CARS, ESTIMATE_COLUMNS
from io_utils import append, clean, dump, external_path, git_state, gzip_writer, outputs, packages, read_jsonl, sha, sources, utc

EXTRA_COLUMNS = ['motion_mode', 'imu_mode_status', 'gyro_bias_rad_s', 'gyro_bias_variance',
    'last_imu_record_index', 'last_imu_header_epoch_ns', 'last_imu_receive_epoch_ns',
    'last_velocity_record_index', 'last_velocity_header_epoch_ns', 'last_velocity_receive_epoch_ns', 'assumption_profile_id',
    'gyro_bias_estimated', 'unobserved_motion_gap', 'bias_semantics', 'state_dimension']


def event_key(event):
    row = event['row']
    return row['receive_epoch_ns'], row['record_index'], row.get('link_index') or 0


def validate_events(events, config):
    ids = set()
    for event in events:
        if set(event) != {'kind', 'row'} or event['kind'] not in ('odom', 'imu', 'range') or not isinstance(event['row'], dict):
            raise ValueError('invalid event wrapper')
        row = event['row']
        for field in ('experiment_id', 'vehicle_id', 'source_file_sha256', 'topic', 'record_index', 'receive_epoch_ns', 'header_epoch_ns'):
            if field not in row:
                raise ValueError('missing event identity: ' + field)
        for field in ('record_index', 'receive_epoch_ns', 'header_epoch_ns'):
            if type(row[field]) is not int:
                raise ValueError('exact integer ns/index required: ' + field)
        if row.get('link_index') is not None and type(row['link_index']) is not int:
            raise ValueError('integer link index required')
        if row['vehicle_id'] not in CARS:
            raise ValueError('unknown vehicle')
        if config['scope'] == 'field' and row['experiment_id'] not in ('T08', 'T10'):
            raise ValueError('field allowlist/whole-bag holdout gate: T08/T10 only')
        ids.add(row['experiment_id'])
    if len(ids) > 1:
        raise ValueError('one input file must not mix experiments/filter histories')
    if len(events) > config['max_events']:
        raise ValueError('event budget exceeded')


def replay_events(events, config, origin=None, end=None, deadline=None):
    validate(config); validate_events(events, config)
    events = sorted(events, key=event_key)
    if not events:
        raise ValueError('no events')
    origin = min(e['row']['receive_epoch_ns'] for e in events) if origin is None else origin
    end = max(e['row']['receive_epoch_ns'] for e in events) if end is None else end
    if type(origin) is not int or type(end) is not int or end < origin:
        raise ValueError('invalid replay interval')
    mode = mode_of(config)
    methods = config.get('imu_prototype', {}).get('fusion_methods', ['independent', 'joint'])
    engines = {m: make_filter(m, config) for m in methods}
    pointer = 0; ticks = list(range(origin, end + 1, config['publish_period_ns']))
    if not ticks or ticks[-1] != end:
        ticks.append(end)
    for index, publication in enumerate(ticks):
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError('replay wall-time deadline')
        decisions = []
        while pointer < len(events) and events[pointer]['row']['receive_epoch_ns'] <= publication:
            if pointer % 64 == 0 and deadline is not None and time.monotonic() > deadline:
                raise TimeoutError('replay event deadline')
            event = events[pointer]
            nonfinite = []; sanitized = clean(event, flags=nonfinite)
            for method, engine in engines.items():
                detail = engine.process(event)
                decisions.append(dict(record_type='event_decision', event_index=pointer, method_id=method, motion_mode=mode,
                    admitted_at_publication_ns=publication, input=sanitized, nonfinite_input_fields=nonfinite,
                    decision=detail, filter_state=engine.full_trace()))
            pointer += 1
        snapshots = {m: e.snapshot(publication) for m, e in engines.items()}
        trace = dict(record_type='publication_snapshot', diagnostic_id=str(index), publish_receive_epoch_ns=publication,
            input_events_consumed=pointer, motion_mode=mode, methods={m: dict(vehicles=snapshots[m],
                filter_state=e.full_trace(), cumulative_event_status=dict(e.counts)) for m, e in engines.items()})
        yield publication, snapshots, decisions, trace, engines


def estimate_rows(publication, snapshots, engines, config, origin, diagnostic_id, config_hash, input_hash):
    rows = []; mode = mode_of(config)
    for method, vehicles in snapshots.items():
        for car, state in vehicles.items():
            pose = state['pose']; prov = engines[method].provenance(car)
            row = dict(experiment_id=config.get('experiment_id', 'input_events'), method_id=method, vehicle_id=car,
                canonical_time_s=(publication - origin) / 1e9, frame_id=state['frame_id'],
                x_m=pose[0] if pose is not None else None, y_m=pose[1] if pose is not None else None, z_m=None,
                yaw_rad=pose[2] if pose is not None else None, valid=int(state['valid']), diagnostic_id=str(diagnostic_id),
                source_version=input_hash, config_version=config_hash, reference_version='none_not_read_by_estimator',
                publish_receive_epoch_ns=publication, state_epoch_ns=state.get('state_epoch_ns'),
                source_header_epoch_ns=state.get('source_header_epoch_ns'), source_receive_epoch_ns=state.get('source_receive_epoch_ns'),
                source_record_index=state.get('source_record_index'), pose_reference_point='base_footprint',
                fallback_status=state['fallback_status'], receipt_age_ns=state.get('receipt_age_ns'), pose_covariance=state['covariance'],
                motion_mode=mode, imu_mode_status=prov['imu_mode_status'], gyro_bias_rad_s=prov['gyro_bias_rad_s'],
                gyro_bias_variance=prov['gyro_bias_variance'], assumption_profile_id=config.get('imu_prototype', {}).get('assumption_profile_id', 'legacy_not_used'),
                gyro_bias_estimated=int(prov['gyro_bias_estimated']), unobserved_motion_gap=int(prov['unobserved_motion_gap']),
                bias_semantics=prov.get('bias_semantics', 'legacy_not_used'), state_dimension=6 if mode == 'legacy_odom_pose' else 8)
            for source in ('imu', 'velocity'):
                item = prov['last_' + source]
                for suffix in ('record_index', 'header_epoch_ns', 'receive_epoch_ns'):
                    row['last_' + source + '_' + suffix] = item[suffix] if item else None
            rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--events-jsonl', type=Path, required=True); parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True); parser.add_argument('--max-seconds', type=float, default=600)
    args = parser.parse_args(argv); started = time.monotonic(); run = None
    try:
        if not 0 < args.max_seconds <= 18000:
            raise ValueError('single replay maximum is five hours')
        config = json.loads(args.config.read_text()); validate(config)
        events = list(read_jsonl(args.events_jsonl)); validate_events(events, config)
        if not events:
            raise ValueError('input is empty')
        config = copy.deepcopy(config); config['experiment_id'] = events[0]['row']['experiment_id']
        output = external_path(args.output); output.mkdir(parents=True, exist_ok=False)
        input_hash = sha(args.events_jsonl); config_hash = sha(args.config)
        run = dict(schema_version=1, role='A_imu_causal_prototype', status='IN_PROGRESS', created_at_utc=utc(), **git_state(),
            command_argv=[sys.executable, __file__] + (list(argv) if argv is not None else sys.argv[1:]),
            source_sha256=sources(), config_sha256={'input_config': config_hash},
            inputs=[dict(asset_id='normalized_events', relative_path=args.events_jsonl.name, sha256=input_hash)],
            environment=dict(python=sys.version, packages=packages()), motion_mode=mode_of(config),
            field_accuracy_evaluated=False, publications_completed=0, outputs=[], limitations=[
                'upstream velocity/gyro statistical independence unproved', 'engineering process/gap covariance, not calibrated posterior',
                'missing-motion reanchor preserves uncertainty; no absolute recovery certification', 'no IMU orientation or acceleration observation'])
        dump(output / 'run.json', run); dump(output / 'config.json', config)
        origin = min(e['row']['receive_epoch_ns'] for e in events); counts = Counter(); engines = None
        with (output / 'estimate.csv').open('x', newline='') as csv_stream, gzip_writer(output / 'decisions.jsonl.gz') as journal:
            writer = csv.DictWriter(csv_stream, fieldnames=ESTIMATE_COLUMNS + EXTRA_COLUMNS, lineterminator='\n'); writer.writeheader()
            for tick, snapshots, decisions, trace, engines in replay_events(events, config, deadline=started + args.max_seconds):
                for record in decisions:
                    flags = []; safe = clean(record, flags=flags)
                    if flags:
                        safe['nonfinite_state_fields'] = flags
                    append(journal, safe)
                append(journal, clean(trace))
                rows = estimate_rows(tick, snapshots, engines, config, origin, trace['diagnostic_id'], config_hash, input_hash)
                for row in rows:
                    counts[row['method_id'], row['vehicle_id'], row['valid'], row['fallback_status']] += 1
                    row['pose_covariance'] = json.dumps(row['pose_covariance'], allow_nan=False) if row['pose_covariance'] is not None else None
                    writer.writerow(row)
                run['publications_completed'] += 1
                if run['publications_completed'] % 100 == 0:
                    csv_stream.flush(); journal.flush(); dump(output / 'run.json', run)
        blocked = sorted({reason for e in engines.values() for values in (e.engine.blocked if mode_of(config) == 'legacy_odom_pose' else e.blocked).values() for reason in values})
        summary = dict(schema_version=1, motion_mode=mode_of(config), input_events=len(events), publications=run['publications_completed'],
            estimate_rows=sum(counts.values()), states=[dict(method=m, vehicle_id=c, valid=v, status=s, rows=n) for (m,c,v,s),n in sorted(counts.items())],
            methods={m: dict(events=dict(e.counts), final_filter_state=clean(e.full_trace())) for m,e in engines.items()}, blocked_reasons=blocked,
            field_accuracy_evaluated=False, timestamp_policy='source-state time and receive publication cutoff are separate; no future endpoint integration')
        dump(output / 'summary.json', summary)
        run.update(status='BLOCKED' if blocked else 'DONE', blocked_reasons=blocked, elapsed_s=time.monotonic() - started, finished_at_utc=utc(), outputs=outputs(output))
        dump(output / 'run.json', run)
        print(json.dumps(dict(status=run['status'], motion_mode=run['motion_mode'], publications=run['publications_completed'], elapsed_s=run['elapsed_s'])))
        return 2 if blocked else 0
    except (Exception, KeyboardInterrupt) as error:
        if run is not None:
            run.update(status='FAILED', error_type=type(error).__name__, error=str(error), elapsed_s=time.monotonic() - started, outputs=outputs(args.output))
            dump(args.output / 'run.json', run)
        print(type(error).__name__ + ': ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
