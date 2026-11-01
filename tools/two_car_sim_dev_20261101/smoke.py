"""Exactly seed7, two 32s development examples. This is not a formal driver."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from common import HERE, dump, git_state, lines, new_output, sha, sources

PLAN = [('nominal', 'M2'), ('nominal', 'M3'), ('nominal', 'M3W025'),
        ('car1_wall_14', 'M2'), ('car1_wall_14', 'M3'), ('car1_wall_14', 'M3W025')]


def smoke(output):
    root = new_output(output)
    (root/'logs').mkdir()
    lock = sources()
    plan = dict(status='IN_PROGRESS', development_only=True, independent_validation=False,
        seed=7, duration_s=32, conditions=['nominal','car1_wall_14'], methods=['M2','M3','M3W025'],
        optimization_cells=6, monitor_comparison=False, source_sha256=lock, **git_state(),
        started_at_utc=datetime.now(timezone.utc).isoformat(), commands=[])
    dump(root/'PLAN.json', plan)
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    def command(name, script, *args):
        if sources() != lock:
            raise ValueError('Frozen development source changed')
        argv = [sys.executable, str(HERE/script), *map(str,args)]
        plan['commands'].append(argv)
        dump(root/'PLAN.json', plan)
        with (root/'logs'/name).open('x') as log:
            subprocess.run(argv, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=150)
    try:
        summaries = []
        for condition in ('nominal','car1_wall_14'):
            inp = root/'inputs'/condition
            command(condition+'-generate.log', 'generate.py', '--spec', HERE/'development_static_moving.json',
                '--condition', condition, '--output', inp)
            runs = {}
            for scenario, method in PLAN:
                if scenario != condition:
                    continue
                run = root/'runs'/condition/method
                runs[method] = run
                command(condition+'-'+method+'-run.log', 'run.py', '--events', inp/'events.jsonl.gz',
                    '--config', inp/'config.json', '--method', method, '--output', run)
                command(condition+'-'+method+'-readback.log', 'readback.py', '--run', run,
                    '--events', inp/'events.jsonl.gz', '--output', root/(condition+'-'+method+'-READBACK.json'))
                args = [] if method == 'M2' else ['--reference-run', root/'runs'/condition/'M2']
                if condition != 'nominal':
                    args += ['--nominal-run', root/'runs'/'nominal'/method, '--nominal-input', root/'inputs'/'nominal']
                command(condition+'-'+method+'-evaluate.log', 'evaluate.py', '--run', run, '--input', inp,
                    '--output', root/(condition+'-'+method+'-EVALUATION.json'), *args)
                meta = json.loads((run/'run.json').read_text())
                summary = json.loads((run/'summary.json').read_text())
                summaries.append(dict(condition=condition,method=method,
                    **{k:meta[k] for k in ('elapsed_s','process_cpu_s','process_peak_rss_kib')}, **summary))
            controls = [list(lines(runs[m]/'updates.jsonl.gz')) for m in ('M2','M3','M3W025')]
            for rows in controls[1:]:
                if [r['bins'] for r in rows] != [r['bins'] for r in controls[0]]:
                    raise ValueError('Baseline input bins differ')
                if [r['monitor']['B1']['raw_local'] for r in rows] != [r['monitor']['B1']['raw_local'] for r in controls[0]]:
                    raise ValueError('B1 input/statistic differs by estimator')
        dump(root/'RESOURCE_SUMMARY.json', summaries)
        plan.update(status='DONE', shared_bins_and_raw_B1='PASS', B1_threshold='INCOMPLETE', B2_8D='INCOMPLETE', formal_matrix_executed=False)
    except BaseException as error:
        plan.update(status='FAILED', error=type(error).__name__+': '+str(error))
        raise
    finally:
        plan['files'] = {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and p.name != 'PLAN.json'}
        dump(root/'PLAN.json', plan)
    return plan


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    result = smoke(a.output)
    print(json.dumps({k:result[k] for k in ('status','seed','conditions','optimization_cells','formal_matrix_executed')}))
