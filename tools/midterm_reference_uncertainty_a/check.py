"""Read back frozen deterministic outputs; independently check rational certificates and counts."""
from contract import ROOT,DOC,source_check,protect,save,CALLS
from fractions import Fraction as Q
from math import factorial,erf,sqrt
import argparse,csv,json,hashlib

def main(results,out):
 source_count=source_check();cfg=json.loads((DOC/'INPUTS.json').read_text());run=json.loads((results/'RUN.json').read_text());rows=json.loads((results/'RESULTS.json').read_text());assert len(rows)==cfg['expected_cases']==run['completed_checks']==20
 assert [r['id'] for r in rows]==[r['id'] for r in cfg['formal_cases']];assert run['failed']==0 and all(r['status']=='PASS' for r in rows)
 freeze=json.loads((DOC/'FREEZE_MANIFEST.json').read_text())
 for path,sha in freeze['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
 saved_cfg=json.loads((results/'INPUTS.json').read_text());assert saved_cfg==cfg
 for row,z in zip(rows,cfg['formal_cases']):assert row==json.loads((results/(row['id']+'.json')).read_text()) and row['inputs']==z['inputs'] and row['criterion']==z['criterion']
 v={r['id']:r['output'] for r in rows};checks=[]
 assert list(map(Q,v['T01']['distance_interval']))==[Q(5),Q(5)];checks.append('zero_reference_reduction')
 assert list(map(Q,v['T02']['distance_interval']))==[Q(4),Q(6)] and Q(v['T02']['near_squared_distance'])==16 and Q(v['T02']['far_squared_distance'])==36;checks.append('ball_boundary_exact_squares')
 assert Q(v['T03']['range_shift'])==-1;checks.append('parallel_tightness')
 lo,hi=map(Q,v['T04']['shift_interval']);assert 0<lo<=hi<1 and (lo+5)**2<=26<=(hi+5)**2;checks.append('perpendicular_integer_sqrt_certificate')
 assert list(map(Q,v['T05']['zero_distance_image']))==[Q(0),Q(1,10)];assert Q(v['T05']['near_zero_image'][0])==0;checks.append('zero_distance_no_derivative')
 assert Q(v['T06']['boundary_prediction'])==Q(27,10)>Q(v['T06']['old_unexpanded_upper']);checks.append('bias_boundary')
 assert sum(map(Q,v['T07']['feasible_witness']))==4 and sum(map(Q,v['T07']['independent_box_false_witness']))==6;checks.append('shared_reference_false_witness')
 assert list(map(Q,v['T08']['required_effective_biases']))==[Q(1),Q(-1)];checks.append('shared_bias_false_equivalence')
 assert not v['T09']['true_state_in_domain'] and Q(v['T09']['noise_event_score'])==0;checks.append('domain_outside')
 # Independent eigen-direction score for R with correlation .9 and e=(1,-1).
 assert Q(v['T10']['correct_correlated_score'])==Q(2)/(1-Q(9,10)) and Q(v['T10']['wrong_independent_score'])==2;checks.append('correlated_eigen_score')
 assert Q(v['T11']['true_fused_variance'])==1 and Q(v['T11']['wrong_independence_variance'])==Q(1,2);assert abs(v['T11']['single_coverage_erf']-erf(sqrt(2)))<1e-15 and abs(v['T11']['duplicate_claim_region_true_coverage_erf']-erf(1))<1e-15;checks.append('duplicate_information_analytic_probability')
 assert Q(v['T12']['actual_joint_inclusion'])==Q(95,100)==Q(v['T12']['valid_union_lower_bound']);assert Q(v['T12']['invalid_product_claim'])==Q(98,100)*Q(97,100)>Q(95,100);checks.append('dependent_union_exact_atom_count')
 assert Q(v['T13']['score_m'])==Q(v['T13']['score_mm'])==5;assert [1000*Q(x) for x in v['T13']['range_m']]==list(map(Q,v['T13']['range_mm']));checks.append('unit_invariance')
 assert Q(v['T14']['original_squared_distance'])==Q(v['T14']['transformed_squared_distance'])==26;checks.append('rotation_invariance')
 assert Q(v['T15']['one_anchor_global_score_lower_bound'])==62500>Q(v['T15']['threshold']) and v['T15']['finite_error_radius'] is None;checks.append('empty_not_zero_error')
 assert v['T16']['joint_translation_invariant'] and v['T16']['collinear_joint_reflection_invariant'];assert [sum(map(Q,p)) for p in v['T16']['distance_bias_ambiguity']]==[Q(1),Q(1)];checks.append('nonidentifiability_witnesses')
 assert list(map(Q,v['T17']['whitened_noise']))==[Q(1),Q(-2)] and v['T17']['noise_degrees_of_freedom']==2;checks.append('whitening_dimension')
 assert list(map(Q,v['T18']['fixed_bias_mean']))==[Q(3,10)]*2 and all(Q(x)==0 for row in v['T18']['fixed_bias_covariance'] for x in row);checks.append('fixed_bias_not_random_covariance')
 assert Q(v['T19']['true_total_variance'])==0 and Q(v['T19']['wrong_no_cross_term_variance'])==2;checks.append('cross_covariance_cancellation')
 # Different expression: factorial series rather than recurrence.
 for q,key,limit in [('9.488','old_tail_upper',Q(1,20)),('10.72','new_tail_upper',Q(3,100))]:
  t=Q(q)/2;bound=(1+t)/sum((t**k/Q(factorial(k)) for k in range(81)),Q(0));assert Q(v['T20'][key])==bound<limit
 assert Q(v['T20']['advertised_allocation_lower'])==Q(19,20);checks.append('tail_certificate_and_risk_budget')
 with (results/'SENSITIVITY.csv').open() as f:sens=list(csv.DictReader(f))
 assert len(sens)==cfg['sensitivity']['planned_rows']==20
 assert {(r['d_m'],r['rho_m']) for r in sens}=={(str(Q(d)),str(Q(r))) for d in cfg['sensitivity']['distances_m'] for r in cfg['sensitivity']['radii_m']}
 for r in sens:
  x={k:Q(val) for k,val in r.items()};d,rho=x['d_m'],x['rho_m'];a,b=max(Q(0),d-rho),d+rho;assert x['distance_min']==a and x['distance_max']==b and x['distance_width']==b-a
  assert x['biased_prediction_min']==a-Q(3,5) and x['biased_prediction_max']==b+Q(3,5);assert x['exact_scalar_width']==b-a+Q(6,5);assert x['relaxed_width']==2*rho+Q(6,5);assert x['extra_lower_slack']==max(Q(0),rho-d)
 assert sum(r.get('classification')=='COUNTEREXAMPLE_CONFIRMED' for r in rows)==run['confirmed_counterexamples']==10
 assert run['optimizer_calls']==run['search_calls']==run['random_calls']==0
 result=dict(status='PASS',formal_records_read=20,independent_checks=len(checks),checks=checks,sensitivity_rows_read=20,source_files_unchanged=source_count,frozen_files_unchanged=len(freeze['files']),new_formal_examples=0,**CALLS);save(out,result);print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=__import__('pathlib').Path,required=True);p.add_argument('--out',type=__import__('pathlib').Path,required=True);a=p.parse_args();protect();main(a.results,a.out)
