"""Read-only PR88 imports, with its generic common module scoped explicitly."""
import importlib.util
import sys
import types
from support import ROOT, sources

sources()


def load(name, path, aliases=None):
    saved = {k:sys.modules.get(k) for k in (aliases or {})}
    try:
        sys.modules.update(aliases or {})
        spec = importlib.util.spec_from_file_location(name, ROOT/path)
        value = importlib.util.module_from_spec(spec)
        sys.modules[name] = value
        spec.loader.exec_module(value)
        return value
    finally:
        for k,v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


old_common = load('_mechanism_old_common','tools/two_car_sim_dev_20261101/common.py')
generator = load('_mechanism_generator','tools/two_car_sim_dev_20261101/generate.py',{'common':old_common})
adapter = load('_mechanism_adapter','tools/two_car_sim_dev_20261101/adapter.py',{'common':old_common})


def clone(function, **bindings):
    namespace = dict(function.__globals__)
    namespace.update(bindings)
    return types.FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)
