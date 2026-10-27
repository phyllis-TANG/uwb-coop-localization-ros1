"""B-neutral quality evidence checks, NOT a detector or estimator.

The provisional score/FSM names apply only to explicitly named fixture/frozen
protocols. Never import A's quality function. Real A output needs a separately
reviewed native adapter; matching hashes does not certify complete provenance.
"""
import math
import statistics
from evidence import require

ROOTS={'external_initialization','prediction','optimizer_initial_guess','history','cache','marginal_prior','score_pose'}
RAW_ID=('case_id','source_file_sha256','record_index','topic','header_epoch_ns','receive_epoch_ns')


def integer(value,name):require(type(value) is int,'exact integer '+name)


def identity(actual,original):
    for key in RAW_ID:require(actual[key]==original[key],'raw identity changed '+key)
    for key in ('record_index','header_epoch_ns','receive_epoch_ns'):integer(actual[key],key)


def closure(roots,nodes,catalog,link,cutoff,case):
    """Every declared initialization/history/cache/prior path is traversed."""
    require(set(roots)==ROOTS,'incomplete shadow root categories');visited=set();active=set();leaves=set()
    def visit(key):
        require(key in nodes,'missing shadow dependency node');require(key not in active,'cyclic shadow provenance')
        if key in visited:return
        active.add(key);n=nodes[key];require(n['case_id']==case,'cross-case shadow dependency')
        require(isinstance(n['parents'],list) and len(n['parents'])==len(set(n['parents'])),'duplicate dependency edge')
        if n['kind']=='raw':
            rid=n['raw_record_id'];require(rid in catalog,'raw source absent');row=catalog[rid];identity(n['identity'],row)
            require(row['case_id']==case and row['receive_epoch_ns']<=cutoff,'future/cross-case shadow input')
            require(row.get('kind')!='opaque_uwb_message','shadow must expose UWB scalar components, not opaque multi-link message')
            require(row.get('link_id')!=link,'excluded link leaked through shadow dependency closure');leaves.add(rid)
        elif n['kind']=='external_prior':
            require(not n['parents'] and n.get('frozen_external') is True and n.get('source_sha256'),'unapproved external initialization')
        else:
            require(n['kind'] in ('state','initial_guess','prediction','cache','marginal_prior','factor','score_pose','history'),'unknown provenance node kind')
            require(bool(n['parents']),'undeclared origin for shadow state/prior/cache')
        for p in n['parents']:visit(p)
        active.remove(key);visited.add(key)
    for category,entry in roots.items():
        require(isinstance(entry,dict) and set(entry)=={'node_ids','not_used_reason'},'explicit shadow root declaration required')
        if not entry['node_ids']:require(bool(entry['not_used_reason']),'silent missing shadow influence category')
        else:
            require(entry['not_used_reason'] is None,'used influence declared unused')
            for key in entry['node_ids']:visit(key)
    require(bool(roots['score_pose']['node_ids']),'missing score shadow pose provenance')
    return dict(nodes_traversed=len(visited),raw_dependency_ids=sorted(leaves),excluded_link_absent_from_declared_closure=True,
      completeness_limitation='Completeness requires native source audit and target-only intervention; a self-declared DAG alone is insufficient')


def score_of(row):
    """Independently calculate range/innovation from supplied shadow geometry."""
    if row['unknown_reason'] is not None:
        require(bool(row['unknown_reason']),'empty unknown reason');return None
    for key in ('shadow_pose','anchor_xyz_m','lever_xy_m'):
        require(row[key] is not None,'missing geometry must be unknown')
    values=[*row['shadow_pose'],*row['anchor_xyz_m'],*row['lever_xy_m'],row['antenna_height_m'],row['raw_range_m'],row['P1_m'],row['measurement_variance_m2'],row['prediction_variance_m2']]
    require(all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in values),'nonfinite/missing score input must be unknown')
    x,y,yaw=row['shadow_pose'];lx,ly=row['lever_xy_m'];ax,ay,az=row['anchor_xyz_m'];dx=x+math.cos(yaw)*lx-math.sin(yaw)*ly-ax;dy=y+math.sin(yaw)*lx+math.cos(yaw)*ly-ay
    predicted=math.sqrt(dx*dx+dy*dy+(row['antenna_height_m']-az)**2);variance=row['measurement_variance_m2']+row['prediction_variance_m2']
    require(row['measurement_variance_m2']>0 and row['prediction_variance_m2']>=0 and variance>0,'positive declared score variance required')
    innovation=row['raw_range_m']-row['P1_m']-predicted
    require(math.isclose(row['predicted_slant_range_m'],predicted,rel_tol=1e-12,abs_tol=1e-12),'shadow range geometry/P1 mismatch')
    require(math.isclose(row['innovation_m'],innovation,rel_tol=1e-12,abs_tol=1e-12),'innovation must not use post-fit main residual')
    if row['score_form']=='absolute_standardized_innovation':return abs(innovation)/math.sqrt(variance)
    if row['score_form']=='nis':return innovation*innovation/variance
    raise ValueError('unsupported frozen score formula; native adapter pending')


def transition(previous,score,policy):
    """Audit only this named, explicitly supplied declarative FSM."""
    require(policy['name']=='consecutive_bad_disable_good_recover_v1','unsupported FSM; independent native implementation pending')
    require(0<=policy['good_lte']<policy['bad_gte'],'invalid hysteresis thresholds')
    for key in ('disable_after_bad','recover_after_good'):require(type(policy[key]) is int and policy[key]>0,'positive persistence counter')
    if score is None:state='unknown';bad=good=0;reason='unknown'
    elif score>=policy['bad_gte']:
        bad=previous['bad_count']+1;good=0;state='disabled' if previous['health'] in ('disabled','recovering') or bad>=policy['disable_after_bad'] else 'suspect';reason='score_high'
    elif score<=policy['good_lte']:
        good=previous['good_count']+1;bad=0;state='recovering' if previous['health'] in ('disabled','recovering') and good<policy['recover_after_good'] else 'healthy';reason='score_low'
    else:
        good=bad=0;state=previous['health'] if previous['health'] in ('disabled','recovering') else 'suspect';reason='hysteresis_band'
    weight=policy['weights'][state];require(isinstance(weight,(int,float)) and math.isfinite(weight) and 0<=weight<=1,'invalid declared information multiplier')
    if state=='unknown':require(weight<policy['weights']['healthy'],'unknown cannot silently receive healthy treatment')
    return dict(health=state,bad_count=bad,good_count=good,information_multiplier=weight,reason=reason)


def decision(row,previous,policy,nodes,catalog):
    for key in ('state_epoch_ns','cutoff_epoch_ns'):integer(row[key],key)
    require(row['quality_arm'] in ('Q2','Q3') and row['case_id'] in ('004023','005135'),'quality case/arm allowlist')
    require(row['cutoff_epoch_ns']-row['state_epoch_ns']==1000000000,'original one-second publication wait')
    for rid in row['support_record_ids']+row['decision_dependencies']:
        require(rid in catalog,'decision input absent');source=catalog[rid]
        for k in ('record_index','header_epoch_ns','receive_epoch_ns'):integer(source[k],k)
        require(source['case_id']==row['case_id'] and source['receive_epoch_ns']<=row['cutoff_epoch_ns'],'future/cross-case decision data')
    require(bool(row['support_record_ids']),'constraint must bind actual original messages')
    require(len(row['support_record_ids'])==len(set(row['support_record_ids']))>=5,'constraint needs original five unique scalar supports')
    require(len({(catalog[k]['source_file_sha256'],catalog[k]['record_index']) for k in row['support_record_ids']})==len(row['support_record_ids']),'same physical frame counted repeatedly')
    require(all(catalog[k]['link_id']==row['link_id'] and catalog[k]['kind']=='uwb_component' for k in row['support_record_ids']),'constraint support link identity')
    support=[catalog[k] for k in row['support_record_ids']]
    require(all(abs(s['header_epoch_ns']-row['state_epoch_ns'])<=400000000 and not s['ambiguous_link_in_frame'] for s in support),'support outside frozen bin or duplicate link ambiguity')
    require(all(s['component_value'] is not None and math.isfinite(s['component_value']) and s['component_value']>0 and s['component_value']-row['P1_m']>0 for s in support),'invalid raw range support')
    require(row['raw_range_m']==statistics.median(s['component_value'] for s in support),'quality statistic differs from original raw median')
    provenance=closure(row['shadow_roots'],nodes,catalog,row['link_id'],row['cutoff_epoch_ns'],row['case_id'])
    score=score_of(row);require(row['score'] is None if score is None else row['score'] is not None and math.isclose(row['score'],score,rel_tol=1e-11,abs_tol=1e-11),'independent consistency score mismatch/null filled zero')
    if row['score'] is not None:require(isinstance(row['score'],(int,float)) and not isinstance(row['score'],bool) and math.isfinite(row['score']) and row['score']>=0,'invalid numeric score')
    for key in ('bad_count','good_count'):integer(row[key],key)
    require(type(row['entered_graph']) is bool,'explicit graph admission boolean required')
    for key in ('old_information_multiplier','new_information_multiplier'):require(isinstance(row[key],(int,float)) and not isinstance(row[key],bool) and math.isfinite(row[key]),'explicit numeric information weight required')
    expected=transition(previous,score,policy)
    for key in ('health','bad_count','good_count'):require(row[key]==expected[key],'independent health transition/hysteresis mismatch')
    require(row['reason']==expected['reason'] or score is None and row['reason']==row['unknown_reason'],'quality reason mismatch')
    require(row['old_information_multiplier']==1. and row['new_information_multiplier']==expected['information_multiplier'],'recorded weight differs from declared policy')
    require(row['entered_graph']==(row['new_information_multiplier']>0),'graph admission contradicts effective weight')
    require(not row['fallback_reason'] or row['fallback_reason'] in policy.get('allowed_fallback_reasons',[]),'unapproved quality fallback')
    return expected,provenance


def factor_cost(factors,decisions,other_cost,reported_cost,expected_decision_ids):
    """Rebuild representative weighted UWB cost, without A objective imports."""
    require(math.isfinite(other_cost) and other_cost>=0,'independent non-UWB cost required');seen=set();cost=other_cost
    actual=[f['decision_id'] for f in factors]
    require(len(actual)==len(set(actual)) and set(actual)==set(expected_decision_ids),'objective constraint omission or repeated decision')
    for factor in factors:
        key=factor['factor_id'];require(key not in seen,'duplicate objective factor');seen.add(key)
        require(factor['decision_id'] in decisions,'factor lacks actual quality decision');d=decisions[factor['decision_id']]
        require(factor['link_id']==d['link_id'],'factor/decision link mismatch');w=d['new_information_multiplier']
        require(factor['information_multiplier']==w and factor['entered_graph']==d['entered_graph'],'recorded weight not really applied in objective')
        require(factor['raw_range_m']==d['raw_range_m'] and factor['P1_m']==d['P1_m'],'objective range/P1 changed')
        model_range=math.dist(factor['optimized_antenna_xyz_m'],factor['anchor_xyz_m']);z=(model_range-(factor['raw_range_m']-factor['P1_m']))/factor['range_sigma_m'];r=z*math.sqrt(2/(math.hypot(1,z)+1));weighted=math.sqrt(w)*r
        require(math.isclose(factor['weighted_residual'],weighted,rel_tol=1e-10,abs_tol=1e-10),'objective ignored or double-applied weight')
        cost+=weighted*weighted/2
    require(math.isclose(cost,reported_cost,rel_tol=1e-9,abs_tol=1e-8),'representative objective total mismatch')
    return dict(weighted_UWB_factors=len(factors),independent_total_cost=cost,other_cost_scope='must be independently reconstructed by B native F0/F3 residual reader; a production-declared subtotal alone is insufficient')


def invariant_prefix(full,prefix):
    require(bool(prefix) and len(prefix)<len(full),'nonempty truncated prefix required')
    omitted={'solve_wall_s','marginal_wall_s','update_wall_s','quality_wall_s','shadow_wall_s','estimated_worker_start_s','estimated_worker_finish_s','estimated_worker_queue_s'}
    for a,b in zip(full,prefix):require({k:v for k,v in a.items() if k not in omitted}=={k:v for k,v in b.items() if k not in omitted},'future input changed closed decision/publication')
    return len(prefix)


def shadow_intervention(before,after,target):
    """Compare target-excluded artifacts after changing target observations only."""
    require(before['target_link']==after['target_link']==target,'intervention target identity')
    require(before['other_input_sha256']==after['other_input_sha256'],'counterfactual changed other observations')
    require(before['target_input_sha256']!=after['target_input_sha256'],'counterfactual did not change target observations')
    require(before['marginalizations']>0 and after['marginalizations']>0,'intervention must include carried priors')
    for key in ('external_initialization','prediction','optimizer_initial_guess','history','cache','marginal_prior','score_pose'):
        require(before['shadow_artifact_sha256'][key]==after['shadow_artifact_sha256'][key],'excluded link reentered shadow through '+key)
    return True
