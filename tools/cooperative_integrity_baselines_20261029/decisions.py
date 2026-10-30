"""Frozen monitor-only alarm/availability; this module never reads truth/labels."""
import math
from scipy.stats import chi2
from common import SPEC


def declare(ready, alarm, main_ok, reason):
    ready = bool(ready and main_ok)
    return dict(computable=ready, alarm=bool(ready and alarm),
                available=bool(ready and not alarm), reason=reason if ready else 'UNKNOWN')


def network(local):
    # A known local alarm is broadcast even if the other local test is unknown.
    any_alarm = any(d['alarm'] for d in local)
    ready = all(d['computable'] for d in local)
    return dict(computable=ready, alarm=any_alarm,
                available=bool(ready and not any_alarm), reason='NETWORK_OR' if ready else 'NETWORK_PARTIAL_UNKNOWN')


def declarations(monitor, main_ok):
    result = {}
    b0 = monitor['b0']; ready = b0['state'] in ('accepted','rejected')
    result['B0'] = [declare(ready, b0.get('engineering_q') is not None and b0['engineering_q'] > 3,
                            main_ok,b0['reason']) for _ in range(2)]
    for alpha in SPEC['alpha_sensitivity']:
        for noise in SPEC['b1_noise_sensitivity']:
            local = []
            for car in ('car1','car2'):
                test = monitor['b1'][noise][car]
                local.append(declare(test['computable'], test['statistic'] is not None and
                    test['statistic'] > chi2.ppf(1-alpha,2), main_ok,test['reason']))
            result[f'B1_local|{noise}|a={alpha}'] = local
            result[f'B1_network|{noise}|a={alpha}'] = [network(local).copy() for _ in range(2)]
        for scale in SPEC['b2_covariance_scale_sensitivity']:
            local = []
            threshold = float(chi2.ppf(1-alpha/3,2))
            for ci in range(2):
                tests = [monitor['ss'][group][ci] for group in SPEC['source_groups']]
                ready = all(t['computable'] for t in tests)
                alarm = any(t['computable'] and t['statistic']/scale**2 > threshold for t in tests)
                local.append(declare(ready,alarm,main_ok,'ALL_THREE_SOURCE_TESTS'))
            result[f'B2_local|scale={scale}|a={alpha}'] = local
            result[f'B2_network|scale={scale}|a={alpha}'] = [network(local).copy() for _ in range(2)]
    return result


def primary_names():
    return ['B0', 'B1_local|engineering_0.2m|a=0.01', 'B1_network|engineering_0.2m|a=0.01',
            'B2_local|scale=1.0|a=0.01', 'B2_network|scale=1.0|a=0.01']
