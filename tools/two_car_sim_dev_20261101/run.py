"""One explicit development replay; sensor/config only, no evaluator imports."""
import argparse
import collections
import csv
import gzip
import json
from pathlib import Path
import platform
import resource
import sys
import time
import numpy as np
import scipy
from common import DEVELOPMENT_SEED, dump, git_state, lines, new_output, sha, sources
from adapter import METHODS, replay
from configuration import validate
from replay import COLUMNS, csv_rows


def run(events_path, config_path, method, output, max_seconds=120):
    config = json.loads(Path(config_path).read_text())
    validate(config)
    lock = sources()
    root = new_output(output)
    started, cpu = time.perf_counter(), time.process_time()
    info = dict(status='IN_PROGRESS', development_only=True, independent_validation=False,
        method_id=method, **git_state(), source_sha256=lock, input_sha256=sha(events_path),
        config_sha256=sha(config_path), command_argv=sys.argv,
        timing_mode='receipt_order_virtual_offline_not_real_robot_latency',
        timing_scope='update_wall_s/virtual worker are estimator only; process elapsed/CPU include B1 and I/O after imports',
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform()))
    dump(root/'config.json', config)
    dump(root/'run.json', info)
    counts = collections.Counter()
    durations = []
    try:
        with gzip.open(root/'updates.jsonl.gz', 'xt') as journal, gzip.open(root/'input_decisions.jsonl.gz', 'xt') as decisions, (root/'published.csv').open('x', newline='') as out:
            writer = csv.DictWriter(out, fieldnames=COLUMNS)
            writer.writeheader()
            def sink(row):
                counts[row['status']] += 1
                durations.append(row['update_wall_s'])
                journal.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')
                for r in csv_rows(row, config):
                    writer.writerow(r)
            engine = None
            for raw in lines(events_path):
                if time.perf_counter()-started > max_seconds:
                    raise TimeoutError('Development replay time cap')
                # Run guard reads neutral opaque identity, never a fault label.
                if raw.get('case_id', '').split('_')[:3] != ['synthetic', 'dev', f'seed{DEVELOPMENT_SEED}']:
                    raise ValueError('Only the exposed development seed7 input is enabled')
                if engine is None:
                    engine = replay(config, method, sink, raw['receive_epoch_ns'])
                    info['epoch_origin_ns'] = raw['receive_epoch_ns']
                decision = engine.ingest(raw)
                decisions.write(json.dumps(dict(record_index=raw['record_index'], decision=decision,
                    angular_decision=engine.last_angular_decision))+'\n')
            if engine is None:
                raise ValueError('Empty input')
            engine.finish()
        dump(root/'final_active_graph.json', engine.graph.snapshot())
        dump(root/'summary.json', dict(publications=engine.output_count, status_counts=dict(counts),
            marginalizations=engine.graph.marginalizations, peak_solve_states=engine.graph.peak_solve_states,
            peak_transient_states=engine.graph.peak_transient_states,
            angular_buffer_peaks={c:b.peak for c, b in engine.angular.items()},
            update_wall_total_s=sum(durations), update_wall_p95_s=float(np.percentile(durations, 95)) if durations else None))
        if sources() != lock:
            raise ValueError('Source changed during execution')
        info['status'] = 'DONE'
    except BaseException as error:
        info.update(status='FAILED', error=type(error).__name__+': '+str(error))
        raise
    finally:
        info.update(elapsed_s=time.perf_counter()-started, process_cpu_s=time.process_time()-cpu,
            process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            rss_scope='process peak including imports; Linux KiB; not incremental graph memory')
        info['outputs'] = {p.name:sha(p) for p in root.iterdir() if p.name != 'run.json'}
        dump(root/'run.json', info)
    return info


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events', required=True, type=Path)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--method', choices=METHODS, required=True)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    result = run(a.events, a.config, a.method, a.output)
    print(json.dumps({k:result[k] for k in ('status', 'method_id', 'elapsed_s', 'process_cpu_s', 'process_peak_rss_kib')}))
