"""Read-only 8D reuse; fixed weight covers solve AND QR marginalization.

Function namespaces are cloned, as in the existing 6D weight adapter. No
global monkeypatch or frozen source mutation. M2/M3 keep their original path.
B1 reuses only the pure four-anchor function; B2 is explicitly incomplete.
"""
import copy
import importlib.util
import sys
import types
import numpy as np
from common import CARS, ROOT, sources

sources()
sys.path.insert(1, str(ROOT/'tools/two_car_imu_fgo'))
import core
from frontend import JointReplay

spec = importlib.util.spec_from_file_location('_sim_dev_b1', ROOT/'tools/cooperative_integrity_baselines_20261029/monitors.py')
b1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b1)
METHODS = ('M2', 'M3', 'M3W025')


class WeightedObjective(core.Objective):
    def evaluate(self, flat):
        residual, jacobian = super().evaluate(flat)
        residual, jacobian = residual.copy(), jacobian.copy()
        n = len(self.peers)
        if n:
            residual[-n:] *= .5
            jacobian[-n:] *= .5
        return residual, jacobian


def clone(function, **bindings):
    namespace = dict(function.__globals__)
    namespace.update(bindings)
    return types.FunctionType(function.__code__, namespace, function.__name__, function.__defaults__, function.__closure__)


weighted_eliminate = clone(core.eliminate, Objective=WeightedObjective)
weighted_update = clone(core.WindowGraph.update, Objective=WeightedObjective, eliminate=weighted_eliminate)


class WeightedGraph(core.WindowGraph):
    def __init__(self, config):
        super().__init__(config, True)

    def update(self, *args):
        row = weighted_update(self, *args)
        for detail in row['marginalization_details']:
            detail['peer_cost_weight'] = .25
        return row


def unknown(reason):
    return dict(status='unknown', alarm=False, available=False, calibrated=False, reason=reason)


def monitor(row, config):
    # Exact same immutable arrived bins as the estimator. No truth/labels.
    raw = {car:b1.four_anchor(row['bins'][car]['observations'], config['models'][car],
                             row['bins'][car]['sample_counts'], 'engineering_0.2m') for car in CARS}
    return dict(B1=dict(raw_local=raw,
        local={c:unknown('B1_THRESHOLD_NOT_CALIBRATED_FOR_NEW_DESIGN') for c in CARS},
        network=unknown('B1_NETWORK_BUDGET_NOT_CALIBRATED')),
        B2=dict(local={c:unknown('B2_8D_HISTORY_AND_SHARED_NOISE_NOT_ADAPTED') for c in CARS},
                network=unknown('B2_8D_HISTORY_AND_SHARED_NOISE_NOT_ADAPTED')))


def replay(config, method, sink, origin_ns):
    if method not in METHODS:
        raise ValueError('Only 8D methods are exposed; no 6D/8D monitor comparison')
    def publish(row):
        row['method_id'] = method
        row['peer_cost_weight'] = dict(M2=0., M3=1., M3W025=.25)[method]
        row['monitor'] = monitor(row, config)
        sink(copy.deepcopy(row))
    result = JointReplay(config, 'M2' if method == 'M2' else 'M3', publish, origin_ns)
    if method == 'M3W025':
        result.graph = WeightedGraph(config)
    return result
