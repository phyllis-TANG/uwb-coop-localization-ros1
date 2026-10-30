"""Audit seed101 input identity without executing an estimator or rewriting a lock.

The Decimal backend is a scoped diagnostic, not a replacement runtime kernel.
It independently reconstructs the registered truth bytes. Native failures stay
visible. No assertion, seed, hash or frozen source is changed.
"""
import argparse
from contextlib import contextmanager
from decimal import Decimal, localcontext
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
from types import SimpleNamespace
import numpy as np

PI = Decimal('3.14159265358979323846264338327950288419716939937510582097494459230781640628620899862803482534211706798214808651328230664709384460955058223172535940812848111745028410270193852110555964462294895493038196')
CONDITIONS = ('nominal', 'peer_bias', 'car1_common_wall_bias')

@lru_cache(maxsize=65536)
def trig(value, cosine=False, precision=120):
    if not math.isfinite(value) or abs(value) > 64:
        raise ValueError('Diagnostic backend is restricted to finite |argument| <= 64')
    with localcontext() as context:
        context.prec = precision
        x = Decimal.from_float(float(value)) % (2 * PI)
        term = total = Decimal(1) if cosine else x
        for k in range(1, precision):
            term *= -x*x / Decimal((2*k-1 if cosine else 2*k)*(2*k if cosine else 2*k+1))
            total += term
        return float(total)

@contextmanager
def decimal_math(simulate, precision=120):
    saved = simulate.math
    namespace = dict(vars(math))
    namespace.update(sin=lambda x: trig(x, False, precision),
                     cos=lambda x: trig(x, True, precision))
    simulate.math = SimpleNamespace(**namespace)
    try:
        yield
    finally:
        simulate.math = saved

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)

def sha(payload):
    return hashlib.sha256(payload).hexdigest()

def truth_payload(rows):
    return ('\n'.join(canonical(row) for row in rows)+'\n').encode('utf-8')

def differences(native, reference):
    found = []
    for a,b in zip(native,reference):
        assert a['state_epoch_ns'] == b['state_epoch_ns'] and a['time_s'] == b['time_s']
        for car in ('car1', 'car2'):
            for field in ('pose', 'antenna_xyz_m'):
                for index,(x,y) in enumerate(zip(a['cars'][car][field],b['cars'][car][field])):
                    if x != y:
                        found.append(dict(time_s=a['time_s'],car=car,field=field,index=index,
                                          native=x,reference=y,absolute_difference=abs(x-y)))
    assert len(native) == len(reference)
    return found

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New directory; old evidence is never overwritten')
    parser.add_argument('--baseline-index', type=Path, help='PR81 results/RUN_INDEX.json; canonical events comparison only')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    root = args.repo.resolve()
    sys.path.insert(0, str(root/'tools/integrity_validation_20261030'))
    import experiment
    import inputs
    import common
    sim = experiment.simulate
    locks = {str(p.relative_to(root)): sha(p.read_bytes()) for p in
             (Path(sim.__file__), sim.CONFIG, Path(inputs.__file__), Path(experiment.__file__))}
    index_path = root/'docs/field_tests/20261024_25/cooperative_peer_gate_probe_20261028/review/input_index.json'
    locks[str(index_path.relative_to(root))] = sha(index_path.read_bytes())
    old_runs = json.loads(args.baseline_index.read_text())['runs'] if args.baseline_index else []
    native_truth = None
    cases = []
    precision_truth = {}
    for mode in ('native', 'decimal120', 'decimal160'):
        context = decimal_math(sim,int(mode[7:])) if mode != 'native' else decimal_math_native(sim)
        with context:
            for condition in CONDITIONS:
                config,events,truth,new_receipt = experiment.make(101,condition)
                payload = truth_payload(truth)
                if native_truth is None:
                    native_truth = truth
                    (args.output/'truth_native.jsonl').write_bytes(payload)
                strict_pass, actual = False, None
                try:
                    old_config,old_events,old_truth,actual = inputs.make(condition)
                    assert old_config == config and old_events == events and old_truth == truth
                    strict_pass = True
                except AssertionError as error:
                    tb = error.__traceback__
                    while tb.tb_next: tb = tb.tb_next
                    actual = tb.tb_frame.f_locals.get('actual')
                    if actual is None: raise
                delta = differences(native_truth,truth)
                old = next((r['input'] for r in old_runs if r.get('scenario')==condition), None)
                # Some historical manifests name the case with a different key.
                if old is None:
                    old = next((r['input'] for r in old_runs if condition in (r.get('scenario'),r.get('case'),r.get('name'))), None)
                cases.append(dict(mode=mode,condition=condition,strict_original_adapter_and_pairing_pass=strict_pass,
                                  config_file_sha256=actual['config_sha256'],
                                  registered_config_equal=actual['registered_config_bytes_equal'],
                                  truth_file_sha256=sha(payload),truth_array_sha256=sha(canonical(truth).encode()),
                                  registered_truth_equal=actual['registered_truth_bytes_equal'],
                                  events_array_sha256=sha(canonical(events).encode()),
                                  prior_canonical_events_equal=(sha(canonical(events).encode())==old['canonical_events_sha256']) if old else None,
                                  event_count=len(events),native_truth_differences=delta,
                                  original_archive_readback=False))
                if mode != 'native':
                    precision_truth.setdefault(mode,payload)
                    assert precision_truth[mode] == payload
    assert precision_truth['decimal120'] == precision_truth['decimal160']
    (args.output/'truth_registered_reconstruction.jsonl').write_bytes(precision_truth['decimal120'])
    assert locks == {path: sha((root/path).read_bytes()) for path in locks}
    report = dict(platform=platform.platform(),python=platform.python_version(),numpy=np.__version__,
                  repo_snapshot=str(root),source_sha256=locks,scope='input generation and adapter identity only; no estimator run',
                  precision120_160_truth_bytes_equal=True,source_files_unchanged=True,cases=cases,
                  limits='Scoped independent arithmetic reconstructs truth, not the missing original event archive or original Linux execution. Native test behavior is unchanged.')
    (args.output/'IDENTITY_AUDIT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([dict(mode=r['mode'],condition=r['condition'],strict_pass=r['strict_original_adapter_and_pairing_pass'],truth_match=r['registered_truth_equal'],event_match=r['prior_canonical_events_equal']) for r in cases]))
    assert all(r['strict_original_adapter_and_pairing_pass'] for r in cases if r['mode'] != 'native')

@contextmanager
def decimal_math_native(simulate):
    yield

if __name__ == '__main__':
    main()
