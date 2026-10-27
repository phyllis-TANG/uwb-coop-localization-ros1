#!/usr/bin/env python3
"""Run exactly the preregistered matrix, after a matching source test receipt."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
from io_utils import dump, environment, git_state, outside, sha, sources, utc
from legacy import ROOT
from replay import run
from simulate import SCENARIOS, FORMAL_SEEDS, write_case


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--test-receipt', type=Path, required=True)
    a = p.parse_args(); lock = sources(); state = git_state()
    receipt = json.loads(a.test_receipt.read_text())
    if receipt.get('status') != 'PASS' or receipt.get('source_sha256') != lock:
        raise ValueError('Foundation tests not passed for exact current sources')
    if state['worktree_dirty']: raise ValueError('Commit frozen code/config before formal seeds')
    root = outside(a.output); root.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    cells = [dict(seed=s, scenario=sc, arm=arm, status='NOT_RUN',
                  input_relative_path=f'inputs/{sc}_seed{s}', run_relative_path=f'runs/{sc}_seed{s}__{arm}')
             for s in FORMAL_SEEDS for sc in SCENARIOS for arm in ('D0', 'D1')]
    matrix = dict(schema_version=1, status='IN_PROGRESS', created_at_utc=utc(), **state,
        preregistration_commit='2149658', source_sha256=lock, test_receipt_sha256=sha(a.test_receipt),
        expected_cells=24, seeds=list(FORMAL_SEEDS), scenarios=list(SCENARIOS), cells=cells,
        timing_mode='virtual', environment=environment(), command_argv=sys.argv)
    dump(root/'matrix.json', matrix)
    shutil.copy2(a.test_receipt, root/'foundation_test_receipt.json')
    # Preserve exact execution sources, including imported F0 code and archived reference.
    for name in lock:
        dst = root/'source'/name; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/name, dst)
    spec = 'docs/field_tests/20261024_25/two_car_fixed_lag_fgo_v1/SPEC.md'
    dst = root/'source'/spec; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT/spec, dst)
    for seed in FORMAL_SEEDS:
        for scenario in SCENARIOS:
            input_dir = root/f'inputs/{scenario}_seed{seed}'
            write_case(input_dir, seed, scenario)
            for arm in ('D0', 'D1'):
                cell = next(c for c in cells if (c['seed'], c['scenario'], c['arm']) == (seed, scenario, arm))
                cell.update(status='IN_PROGRESS', events_sha256=sha(input_dir/'events.jsonl.gz'),
                            config_sha256=sha(input_dir/'config.json'))
                dump(root/'matrix.json', matrix)
                try:
                    result = run(input_dir/'events.jsonl.gz', input_dir/'config.json', arm,
                                 root/cell['run_relative_path'], max_seconds=300.)
                    cell.update(status=result['status'], elapsed_s=result['elapsed_s'],
                                run_manifest_sha256=sha(root/cell['run_relative_path']/'run.json'))
                except (Exception, KeyboardInterrupt) as error:
                    cell.update(status='FAILED', error=type(error).__name__+': '+str(error))
                    dump(root/'matrix.json', matrix)
                    if isinstance(error, KeyboardInterrupt): raise
                print(json.dumps(cell), flush=True)
                dump(root/'matrix.json', matrix)
                if sources() != lock: raise RuntimeError('Frozen source changed; stop without retry')
    matrix.update(status='DONE' if all(c['status'] == 'DONE' for c in cells) else 'FAILED',
                  finished_at_utc=utc(), elapsed_s=time.perf_counter()-started)
    dump(root/'matrix.json', matrix)
    return 0 if matrix['status'] == 'DONE' else 1


if __name__ == '__main__': raise SystemExit(main())
