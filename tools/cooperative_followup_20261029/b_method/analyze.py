#!/usr/bin/env python3
"""Two exact surrogate explanations + compact PR72 table arithmetic only.

No FGO, sensor adapter, optimizer, random generator or external dependency.
Truth/health are used after a single calculation from online inputs.
"""
import argparse
import csv
from decimal import Decimal
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DOCS = ROOT/'docs/research/cooperative_followup_20261029/b_method'
PROBE = ROOT/'docs/field_tests/20261024_25/cooperative_influence_probe_20261028'
BASE = '0ef38e8b84dc88cb7b0e26fea595ac05c5162676'
PR72 = '1cc7713a7e48776474788a07a1b41040f9df9330'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write('\n')


def q(value):
    return dict(exact=str(value), decimal=float(value))


def clip(value, budget):
    return max(-budget, min(budget, value))


def outputs(m, r, weight, gamma, budget):
    """Only declared online observations/design weights; no world argument."""
    delta = r-(m[1]-m[0])
    transfer = gamma*delta/(weight+2*gamma)
    joint = (m[0]-transfer, m[1]+transfer)
    clipped = tuple(ref+clip(x-ref, budget) for x, ref in zip(joint, m))
    bounded_t = clip(transfer, budget)
    bounded = (m[0]-bounded_t, m[1]+bounded_t)
    return {'I': m, 'J_closed_form': joint, 'C_output_clip': clipped,
            'K_equal_precision_box_closed_form': bounded}


def derivatives(x, m, r, weight, gamma):
    residual = x[1]-x[0]-r
    return (weight*(x[0]-m[0])-gamma*residual,
            weight*(x[1]-m[1])+gamma*residual)


def exact_analysis(config):
    m = tuple(map(F, config['observed_local_positions_m']))
    r, weight, gamma, budget = map(F, (config['observed_signed_peer_m'],
        config['local_precision'][0], config['peer_weight'], config['budget_m']))
    assert list(map(F, config['local_precision'])) == [weight, weight]
    assert weight > 0 and gamma >= 0 and budget >= 0
    # Calculate once from online observations, before consulting any truth.
    out = outputs(m, r, weight, gamma, budget)
    assert set(out) == set(config['methods'])
    assert all(g == 0 for g in derivatives(out['J_closed_form'], m, r, weight, gamma))
    determinant = weight*(weight+2*gamma)
    assert weight+gamma > 0 and determinant > 0  # Sylvester, strictly convex.
    bounded = out['K_equal_precision_box_closed_form']
    assert bounded == out['C_output_clip']
    assert all(abs(x-ref) <= budget for x,ref in zip(bounded,m))
    gradient = derivatives(bounded, m, r, weight, gamma)
    signs = []
    for x, ref, g in zip(bounded, m, gradient):
        d = x-ref
        valid = (d == -budget and g >= 0) or (d == budget and g <= 0) or (-budget < d < budget and g == 0)
        assert valid
        signs.append(dict(position=q(x), reference=q(ref), displacement=q(d), gradient=q(g), box_kkt=True))
    explanations = []
    truth = []
    for world in config['worlds']:
        x = tuple(map(F, world['evaluation_true_positions_m']))
        bias = tuple(map(F, world['evaluation_local_biases_m']))
        assert tuple(a+b for a,b in zip(x,bias)) == m
        assert x[1]-x[0] == r and r > 0
        assert sum(b != 0 for b in bias) == 1
        assert all(abs(b) <= F('3/10') for b in bias)
        accurate = [i for i,b in enumerate(bias) if b == 0]
        assert world['evaluation_accurate_local_source'] == 'car'+str(accurate[0]+1)
        truth.append(x)
        records = []
        for method, estimate in out.items():
            actual_delta = tuple(a-b for a,b in zip(estimate,m))
            error = tuple(a-b for a,b in zip(estimate,x))
            for i in range(2):
                assert abs(abs(error[i])-abs(bias[i])) <= abs(actual_delta[i])
            if method.startswith(('C_', 'K_')):
                assert all(abs(v) <= budget for v in actual_delta)
                assert all(abs(abs(error[i])-abs(bias[i])) <= budget for i in range(2))
            records.append(dict(method=method, antenna_positions_m=[q(v) for v in estimate],
                actual_change_from_private_reference_m=[q(v) for v in actual_delta],
                signed_truth_error_m=[q(v) for v in error],
                absolute_truth_error_m=[q(abs(v)) for v in error],
                help_signed_m=[q(abs(bias[i])-abs(error[i])) for i in range(2)],
                budget_holds=[abs(v) <= budget for v in actual_delta],
                peer_residual_m=q(estimate[1]-estimate[0]-r)))
        explanations.append(dict(world=world['id'], true_positions_m=[q(v) for v in x],
            biases_m=[q(v) for v in bias], accurate_source=world['evaluation_accurate_local_source'],
            reconstructed_online_observations=dict(m_m=[q(v) for v in m], peer_m=q(r)), outputs=records))
    assert len(explanations) == config['world_count'] == 2
    assert explanations[0]['accurate_source'] != explanations[1]['accurate_source']
    assert explanations[0]['reconstructed_online_observations'] == explanations[1]['reconstructed_online_observations']
    shift = tuple(b-a for a,b in zip(*truth))
    assert shift[0] == shift[1] == F('3/10')
    # Any common constant translation cancels from each car's motion increment.
    # Zero healthy motion in A forces delta2=0; in B forces delta1=0.
    # With uniform healthy budget B both deltas must lie in [-B,B].
    minimum_peer_gap = max(F(0), abs(r-(m[1]-m[0]))-2*budget)
    assert minimum_peer_gap == abs(bounded[1]-bounded[0]-r)
    return dict(status='PASS', scope='exact two-world surrogate, not raw-anchor or real accuracy validation',
        world_count=2, outputs_computed_from_online_information_once=True,
        online_health_or_truth_used=False, worlds=explanations,
        exact_checks=['identical local and peer observations', 'opposite accurate source',
            'translation cancels in common per-car motion increments', 'one signed biased source per world',
            'joint stationarity and SPD', 'box KKT', 'box equals cheap output clipping',
            'actual one-dimensional antenna budget', 'truth error change triangle inequality',
            'residual lower bound under protection of either potentially accurate source'],
        hessian_determinant=q(determinant), constrained_gradient_and_kkt=signs,
        minimum_peer_residual_if_both_potentially_accurate_cars_protected=q(minimum_peer_gap),
        uniform_zero_harm_requires_both_displacements_zero=True,
        no_2D_candidate_or_new_method_validated=True)


def compact_pr72():
    with (PROBE/'results/metrics.csv').open() as f: rows=list(csv.DictReader(f))
    contrasts=[]
    for period in ('fault', 'recovery'):
        for car in ('car1', 'car2'):
            get=lambda method,scope: next(x for x in rows if
                (x['scenario'],x['method'],x['scope'],x['period'],x['car']) ==
                ('car1_common_wall_bias',method,scope,period,car))
            c,k=get('C004','all_finite'),get('K004','all_finite')
            assert c['denominator']==k['denominator']==c['n']==k['n']
            assert c['n']==('14' if period=='fault' else '10')
            assert get('C004','reference_accepted')['antenna_xy_rmse_m']==c['antenna_xy_rmse_m']
            assert get('K004','reference_accepted')['antenna_xy_rmse_m']==k['antenna_xy_rmse_m']
            difference=Decimal(k['antenna_xy_rmse_m'])-Decimal(c['antenna_xy_rmse_m'])
            contrasts.append(dict(period=period,car=car,n=int(c['n']),scope='all_finite equals reference_accepted here',
                C004_rmse_m=c['antenna_xy_rmse_m'],K004_rmse_m=k['antenna_xy_rmse_m'],
                K_minus_C_m=str(difference),K_minus_C_mm=str(difference*1000),
                interpretation='negative improves, positive worsens; arithmetic on published RMSE only'))
    with (PROBE/'results/costs.csv').open() as f: costs=list(csv.DictReader(f))
    selected=[{k:x[k] for k in ('scenario','method','kind','main_total_s','reference_total_s','clip_total_s','timing_origin')}
              for x in costs if x['method'] in ('U','K004','W025','C004')]
    assert len(selected)==8
    return dict(status='PASS_COMPACT_TABLE_ARITHMETIC_ONLY',contrasts=contrasts,cost_rows=selected,
        original_RMSE_recomputed=False,original_timestep_budget_rechecked=False,
        original_optimizer_or_prior_audit_repeated=False,
        caveat='single exposed seed101/two conditions; main cost has solver-path control U; clipping is derived and J/I costs historical')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    output=a.output.resolve()
    if DOCS not in output.parents: raise ValueError('Small outputs must stay in assigned b_method docs directory')
    if output.exists(): raise FileExistsError(output)
    config_path=HERE/'PROOF_CONFIG.json';config=json.loads(config_path.read_text())
    proof=exact_analysis(config); tables=compact_pr72()
    output.mkdir(parents=True,exist_ok=False)
    dump(output/'exact_worlds.json',proof);dump(output/'pr72_compact_check.json',tables)
    paths=[config_path,HERE/'analyze.py',DOCS/'PREREGISTRATION.md',PROBE/'results/metrics.csv',PROBE/'results/costs.csv']
    dump(output/'run.json',dict(status='DONE',role='B necessary-condition exact arithmetic',
        command_argv=[sys.executable]+sys.argv,code_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        worktree_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
        read_main=BASE,read_PR72_head=PR72,preregistration_commit='d5aa03d',
        source_input_sha256={str(x.relative_to(ROOT)):sha(x) for x in paths},
        python=sys.version,world_count=2,new_FGO_runs=0,new_seeds=0,new_static_2D_configs=0,
        B4_candidate_experiment='NOT_OPENED',outputs={x.name:sha(x) for x in sorted(output.iterdir()) if x.is_file()}))
    print(json.dumps(dict(status='PASS',exact_worlds=2,compact_contrasts=len(tables['contrasts']),new_FGO_runs=0,candidate=None)))


if __name__=='__main__': main()
