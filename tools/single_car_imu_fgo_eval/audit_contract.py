"""Independent FGO acceptance helpers for an explicit future A log adapter.

Not an optimizer: consumes supplied factor linearizations/records, never computes
a trajectory or selects field parameters. Current fixtures verify these guards,
not an A implementation that has not yet provided a frozen interface.
"""
from collections import Counter
import math
import numpy as np


def heading_sources(record):
    if record['mode'] not in ('F0','F1','F2','F3'):raise ValueError('unknown FGO comparison mode')
    if record['mode'] not in ('F2','F3'):return {'odom_heading_fallback':False}
    sources=record.get('heading_sources',{})
    required={'startup','keyframe_prediction','optimizer_initial_guess','failure_recovery'}
    if not required.issubset(sources):raise ValueError('heading dependency ledger incomplete')
    allowed={'external_initial_heading','gyro_increment','optimized_state','gyro_prediction','previous_optimized_plus_gyro','not_applicable'}
    odom={'odom_pose_yaw','odom_delta_yaw','odom_prediction'}
    for source in sources.values():
        if source not in allowed|odom:raise ValueError('unapproved/unknown heading source: '+source)
    fallback=any(s in odom for s in sources.values())
    if fallback and (record.get('odom_heading_fallback') is not True or not record.get('fallback_reason')):
        raise ValueError('hidden Odom heading dependency in F2/F3')
    return {'odom_heading_fallback':fallback,'must_report_separately':fallback}


def dependency_cutoff(record,inputs):
    cutoff=record['availability_cutoff_epoch_ns']
    if type(cutoff) is not int:raise ValueError('integer publication deadline required')
    for index in record['dependency_record_indices']:
        if index not in inputs or inputs[index]['receive_epoch_ns']>cutoff:raise ValueError('future or absent dependency')
    return True


def marginal_prior(jacobian,residual,prior_matrix,prior_offset,old_dimension=4,tolerance=1e-8,discarded_constant=None):
    j,r,a,c=[np.asarray(x,float) for x in (jacobian,residual,prior_matrix,prior_offset)]
    if j.ndim!=2 or j.shape[1]!=2*old_dimension or r.shape!=(len(j),) or a.shape!=(old_dimension,old_dimension) or c.shape!=(old_dimension,):raise ValueError('marginal ledger dimensions')
    if not all(np.isfinite(x).all() for x in (j,r,a,c)):raise ValueError('nonfinite marginal system')
    left,right=j[:,:old_dimension],j[:,old_dimension:]
    h00=left.T@left;h01=left.T@right
    if np.linalg.matrix_rank(h00)!=old_dimension:raise ValueError('old block rank deficient; explicit weak-information policy required')
    expected_h=right.T@right-h01.T@np.linalg.solve(h00,h01)
    expected_g=right.T@r-h01.T@np.linalg.solve(h00,left.T@r)
    if not np.allclose(a.T@a,expected_h,rtol=tolerance,atol=tolerance) or not np.allclose(a.T@c,expected_g,rtol=tolerance,atol=tolerance):
        raise ValueError('lost position/yaw/bias cross-information or affine residual')
    if discarded_constant is not None:
        expected_cost=float(r@r-(left.T@r)@np.linalg.solve(h00,left.T@r))
        if discarded_constant < -tolerance or not np.isclose(c@c+discarded_constant,expected_cost,rtol=tolerance,atol=tolerance):
            raise ValueError('eliminated constant cost changed or double counted')
    return {'H_and_gradient_verified':True,'state_dimension':old_dimension,'bias_cross_information_retained':True,
            'constant_cost_checked':discarded_constant is not None}


def factor_accounting(eliminated,expected_incident,retained):
    if (len(eliminated)!=len(set(eliminated)) or len(retained)!=len(set(retained)) or len(expected_incident)!=len(set(expected_incident))
            or set(eliminated)!=set(expected_incident) or set(eliminated)&set(retained)):
        raise ValueError('factor omission, repeat or double counting across marginalization')
    return True


def coverage(arms):
    if set(arms)!= {'F0','F1','F2','F3'}:raise ValueError('all four same-condition modes required')
    grid={r['state_time_s'] for r in arms['F0']};indexed={};reports={}
    def valid(r):return r is not None and r.get('pose') is not None and len(r['pose'])>=3 and all(math.isfinite(float(x)) for x in r['pose'][:3])
    for mode,rows in arms.items():
        by={r['state_time_s']:r for r in rows}
        if len(by)!=len(rows) or set(by)-grid:raise ValueError('duplicate or changed publication grid')
        indexed[mode]=by
        reports[mode]={'scheduled_publications':len(grid),'recorded_publications':len(rows),'missing_publications':len(grid-set(by)),
            'finite_pose_publications':sum(valid(r) for r in rows),'accepted_graph_publications':sum(bool(r.get('accepted_graph')) for r in rows),
            'status_counts':dict(Counter(r['status'] for r in rows)),
            'solver_failed_publications':sum(bool(r.get('solver_failed',False)) for r in rows),
            'explicit_odom_heading_fallbacks':sum(bool(r.get('odom_heading_fallback',False)) for r in rows)}
    common=[t for t in sorted(grid) if all(valid(indexed[m].get(t)) for m in arms)]
    common_graph=[t for t in common if all(indexed[m][t].get('accepted_graph',False) for m in arms)]
    return {'per_mode':reports,'common_finite_state_times_s':common,'common_accepted_graph_times_s':common_graph,
            'all_statuses_and_missing_intervals_reported':True,'common_subset_is_not_total_performance':True}
