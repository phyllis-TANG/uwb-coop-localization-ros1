"""PR52 policies on PR53's unchanged T10 hypotheses; no accuracy interface."""
import argparse
import csv
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent
sys.path.insert(0, str(PARENT / 't10_exploratory'))
import pilot
sys.path.insert(0, str(PARENT / 'causal_reliability'))
from engine import Candidate, METHODS
import model

PROTOCOL = HERE / 'protocol.json'
COLUMNS = list(pilot.replay.ESTIMATE_COLUMNS) + ['covariance_reason']


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()


def write(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
        f.write('\n')


def append(stream, value):
    stream.write(json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':'))+'\n')


def lock_sources():
    paths = [PROTOCOL, pilot.PROTOCOL]
    for name in ('t10_reliability_bridge', 't10_exploratory', 'causal_reliability', 'causal_baselines', 't10_closure', 'parameter_clock_prep'):
        paths += sorted((PARENT/name).glob('*.py'))
    paths += [PARENT/x for x in ('development.py', 'prepare.py', 'run_nightly.py', 'normalize.py')]
    return {str(p.relative_to(ROOT)): sha(p) for p in paths}


def protocol():
    p = json.loads(PROTOCOL.read_text())
    original = json.loads(pilot.PROTOCOL.read_text())
    frozen = PARENT.parent.parent/'docs/field_tests/20261024_25/causal_reliability_20261027/frozen_protocol.json'
    policy = json.loads(frozen.read_text())['policy']
    if p['experiment_id'] != 'T10' or p['bag_sha256'] != pilot.closure.BAG_SHA:
        raise ValueError('T10 successful development retry only; holdouts refused')
    if p['pr53_protocol_sha256'] != sha(pilot.PROTOCOL) or p['profiles'] != original['profiles']:
        raise ValueError('PR53 hypotheses/profiles changed')
    if p['policy'] != policy or list(METHODS) != p['methods']:
        raise ValueError('PR52 policy/method set changed')
    return p, original


def snapshot_rows(tick, index, snapshots, origin, config_sha):
    rows = []
    for method, item in sorted(snapshots.items()):
        for car, s in item['vehicles'].items():
            pose = s['pose']
            rows.append(dict(experiment_id='T10', method_id=method, vehicle_id=car,
                canonical_time_s=(tick-origin)/1e9, frame_id=s['frame_id'],
                x_m=pose[0] if pose else None, y_m=pose[1] if pose else None, z_m=None,
                yaw_rad=pose[2] if pose else None, valid=int(s['valid']), diagnostic_id=index,
                source_version='PR52_PR53_T10_exploratory_bridge', config_version=config_sha,
                reference_version='none_not_accepted', publish_receive_epoch_ns=tick,
                state_epoch_ns=s.get('state_epoch_ns'), source_header_epoch_ns=s.get('source_header_epoch_ns'),
                source_receive_epoch_ns=s.get('source_receive_epoch_ns'), source_record_index=s.get('source_record_index'),
                pose_reference_point='base_footprint', fallback_status=s['fallback_status'], receipt_age_ns=s.get('receipt_age_ns'),
                pose_covariance=json.dumps(s['covariance'], allow_nan=False) if s['covariance'] is not None else '',
                covariance_reason=s.get('output_covariance_reason')))
    return rows


def process(events, config, policy, origin, end, deadline):
    model.validate_config(config)
    if any(e['row']['experiment_id'] != 'T10' or e['row']['source_file_sha256'] != pilot.closure.BAG_SHA for e in events):
        raise ValueError('wrong development bag or holdout input')
    engines = {m: Candidate(m, config, policy) for m in METHODS}
    pointer = 0
    ticks = list(range(origin, end+1, config['publish_period_ns']))
    if ticks[-1] != end: ticks.append(end)
    for tick in ticks:
        if time.monotonic() > deadline: raise TimeoutError('registered bridge deadline')
        bundles = []
        while pointer < len(events) and int(events[pointer]['row']['receive_epoch_ns']) <= tick:
            if pointer % 64 == 0 and time.monotonic() > deadline: raise TimeoutError('event batch deadline')
            event = events[pointer]
            details = {}
            for method, candidate in engines.items():
                decision = candidate.process(event)
                details[method] = dict(decision=decision, feedback_state=candidate.engine.x.tolist(),
                    feedback_covariance=candidate.engine.P.tolist(), shadow_state=candidate.shadow.x.tolist(),
                    shadow_covariance=candidate.shadow.P.tolist())
            bundles.append(dict(event_index=pointer, admitted_at_publication_ns=tick, methods=details))
            pointer += 1
        yield dict(publish_receive_epoch_ns=tick, input_events_consumed=pointer,
            methods={m:c.state_record(tick) for m,c in engines.items()}), bundles


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packet', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    start = time.monotonic()
    p, original = protocol()
    git = lambda *a: subprocess.check_output(['git', *a], cwd=ROOT, text=True).strip()
    if git('status', '--porcelain'): raise ValueError('formal source checkout must be clean')
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or ROOT.is_relative_to(output): raise ValueError('results must be outside checkout')
    packet = pilot.closure.verify_packet(args.packet)
    manifest = json.loads((pilot.closure.SESSION/'manifest.json').read_text())
    selected = next(r for r in manifest['formal_bags'] if r['id']=='T10')
    if selected['sha256'] != p['bag_sha256'] or selected['split'] != 'development': raise ValueError('T10 identity')
    odom = pilot.read_csv(args.packet/'normalized_T10/odom.csv')
    ranges = pilot.read_csv(args.packet/'normalized_T10/ranges.csv')
    origin, end = selected['first_bag_receive_epoch_ns'], selected['last_bag_receive_epoch_ns']
    source_hashes = lock_sources()
    output.mkdir(parents=True, exist_ok=False)
    run = dict(status='IN_PROGRESS', scope='EXPLORATORY_ONLY', code_commit=git('rev-parse','HEAD'),
        worktree_dirty=False, source_sha256=source_hashes, packet=packet, argv=sys.argv,
        origin_epoch_ns=origin, end_epoch_ns=end,
        protocol_sha256=sha(PROTOCOL), field_accuracy_evaluated=False, source_modified_during_run=False,
        environment=dict(python=platform.python_version(), numpy=np.__version__,
            scipy=importlib.metadata.version('scipy'), thread_env={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS')}),
        profiles={})
    write(output/'started.json', run)
    write(output/'protocol.json', p)
    try:
        for profile in p['profiles']:
            directory = output/profile['id']; directory.mkdir()
            config = pilot.configuration(original, profile, odom, ranges, origin)
            write(directory/'config.json', config)
            events, counts, _ = pilot.replay.read_events(args.packet/'normalized_T10','T10',config,manifest)
            canonical = json.dumps(events, sort_keys=True, allow_nan=False, separators=(',', ':'))
            fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
            if profile['id'] == 'nominal':
                with gzip.open(output/'inputs.jsonl.gz', 'xt', compresslevel=3) as f:
                    for event in events: append(f, event)
                run['canonical_input_sha256'] = fingerprint
            elif run['canonical_input_sha256'] != fingerprint: raise ValueError('profile changed immutable input events')
            with gzip.open(directory/'states.jsonl.gz','xt',compresslevel=3) as states, gzip.open(directory/'events.jsonl.gz','xt',compresslevel=3) as journal, (directory/'estimate.csv').open('x', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=COLUMNS); writer.writeheader()
                total_rows = 0
                for index, (tick,bundles) in enumerate(process(events,config,p['policy'],origin,end,start+p['budget_seconds'])):
                    append(states,tick)
                    for bundle in bundles: append(journal,bundle)
                    rows = snapshot_rows(tick['publish_receive_epoch_ns'],index,tick['methods'],origin,sha(directory/'config.json'))
                    writer.writerows(rows); total_rows += len(rows)
            run['profiles'][profile['id']] = dict(status='DONE', input_counts=counts, input_sha256=fingerprint,
                publication_rows=total_rows, publication_count=index+1)
            print(json.dumps(dict(profile=profile['id'],rows=total_rows,elapsed_s=round(time.monotonic()-start,2))),flush=True)
        if lock_sources() != source_hashes or git('status','--porcelain'): raise ValueError('source changed during execution')
        run['status'] = 'DONE_EXPLORATORY_ONLY'
    except BaseException as error:
        run.update(status='FAILED', error=repr(error)); raise
    finally:
        run['elapsed_s'] = time.monotonic()-start
        run['outputs'] = {str(f.relative_to(output)):sha(f) for f in output.rglob('*') if f.is_file()}
        write(output/'run.json',run)


if __name__ == '__main__': main()
