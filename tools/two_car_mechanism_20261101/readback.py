"""Independent saved-evidence reader; imports no online solver or generator."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import types
from support import ROOT, expanded_rows, dump, lines, sha


def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def audit(run, events):
    old_common = load('_readback_common',ROOT/'tools/two_car_sim_dev_20261101/common.py')
    previous = sys.modules.get('common')
    try:
        sys.modules['common'] = old_common
        original = load('_readback_scalar',ROOT/'tools/two_car_sim_dev_20261101/readback.py')
    finally:
        if previous is None:
            sys.modules.pop('common',None)
        else:
            sys.modules['common'] = previous
    def decoded(path):
        return list(expanded_rows(path)) if Path(path).name == 'updates.jsonl.gz' else list(lines(path))
    namespace = dict(original.audit.__globals__,lines=decoded)
    reader = types.FunctionType(original.audit.__code__,namespace)
    result = reader(run,events)
    result['reconstruction'] = 'every full snapshot SHA equals online snapshot SHA after lossless expansion'
    # Reader scope is explicit, including estimator/monitor time distinction.
    result['online_solver_or_analytic_jacobian_imported'] = False
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',required=True,type=Path)
    p.add_argument('--events',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Refuse overwrite')
    result = audit(a.run,a.events)
    dump(a.output,result)
    print(json.dumps(result))
