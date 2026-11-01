"""Sensor/config-only replay of the unchanged PR88 estimators."""
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
from support import METHODS, compact, digest, dump, git_state, lines, new_output, sha, sources, write_lines
from bindings import adapter
from configuration import validate
from replay import COLUMNS, csv_rows


def run(events_path, config_path, method, output, max_seconds=150):
    config = json.loads(Path(config_path).read_text())
    validate(config)
    lock = sources()
    root = new_output(output)
    start, cpu = time.perf_counter(), time.process_time()
    info = dict(status='IN_PROGRESS', method_id=method, **git_state(), source_sha256=lock,
        input_sha256=sha(events_path), config_sha256=sha(config_path), command_argv=sys.argv,
        environment=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__),
        timing_scope='after imports; elapsed/CPU include monitor and IO; original update/virtual queue estimator only',
        snapshot_encoding='lossless history_inputs_v1; SHA of full online snapshot per publication',
        estimator_inputs=['events','config'], online_monitor_claim=False)
    dump(root/'config.json', config)
    dump(root/'run.json', info)
    counts = collections.Counter()
    durations = []
    try:
        with gzip.open(root/'updates.jsonl.gz','xt') as journal, gzip.open(root/'input_decisions.jsonl.gz','xt') as decisions, (root/'published.csv').open('x',newline='') as f:
            writer = csv.DictWriter(f,fieldnames=COLUMNS)
            writer.writeheader()
            def sink(row):
                counts[row['status']] += 1
                durations.append(row['update_wall_s'])
                journal.write(json.dumps(compact(row),sort_keys=True,allow_nan=False)+'\n')
                for value in csv_rows(row,config):
                    writer.writerow(value)
            engine = None
            for event in lines(events_path):
                if time.perf_counter()-start > max_seconds:
                    raise TimeoutError('Frozen per-cell time cap')
                if not event['case_id'].startswith('synthetic_mechanism_seed'):
                    raise ValueError('Controlled mechanism inputs only')
                if engine is None:
                    engine = adapter.replay(config,method,sink,event['receive_epoch_ns'])
                    info['epoch_origin_ns'] = event['receive_epoch_ns']
                decision = engine.ingest(event)
                decisions.write(json.dumps(dict(record_index=event['record_index'],decision=decision,angular_decision=engine.last_angular_decision))+'\n')
            if engine is None:
                raise ValueError('Empty input')
            engine.finish()
        write_lines(root/'final_active_graph.jsonl.gz',[engine.graph.snapshot()])
        dump(root/'summary.json',dict(publications=engine.output_count,status_counts=dict(counts),
            marginalizations=engine.graph.marginalizations,peak_solve_states=engine.graph.peak_solve_states,
            peak_transient_states=engine.graph.peak_transient_states,
            angular_buffer_peaks={c:b.peak for c,b in engine.angular.items()},
            update_wall_total_s=sum(durations),update_wall_p95_s=float(np.percentile(durations,95)) if durations else None))
        if sources() != lock:
            raise ValueError('Execution source changed')
        info['status'] = 'DONE'
    except BaseException as error:
        info.update(status='FAILED',error=type(error).__name__+': '+str(error))
        raise
    finally:
        info.update(elapsed_s=time.perf_counter()-start,process_cpu_s=time.process_time()-cpu,
            process_peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        info['outputs'] = {p.name:sha(p) for p in root.iterdir() if p.name != 'run.json'}
        dump(root/'run.json',info)
    return info


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--events',required=True,type=Path)
    p.add_argument('--config',required=True,type=Path)
    p.add_argument('--method',required=True,choices=METHODS)
    p.add_argument('--output',required=True,type=Path)
    a = p.parse_args()
    r = run(a.events,a.config,a.method,a.output)
    print(json.dumps({k:r[k] for k in ('status','method_id','elapsed_s','process_cpu_s','process_peak_rss_kib')}))
