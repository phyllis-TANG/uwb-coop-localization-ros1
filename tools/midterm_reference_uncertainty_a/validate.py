"""Twenty frozen deterministic checks and a twenty-row closed-form sensitivity table."""
from contract import *
import argparse,csv,math,platform,subprocess,traceback

NEGATIVE={'T07','T08','T09','T10','T11','T12','T15','T16','T18','T19'}
def case(z):
 t=z['id'];p=z['inputs'];v={}
 if t=='T01':
  r=ball_range(p['d'],p['rho']);assert r==(F(p['d']),F(p['d']));v={'distance_interval':r,'A0_exact':True}
 elif t=='T02':
  x,s0=vec(p['p']),vec(p['s0']);rho=F(p['rho']);d=sqrt_bounds(norm2(sub(x,s0)));assert d[0]==d[1];lo,hi=ball_range(d[0],rho);n,f=vec(p['near']),vec(p['far']);assert norm2(sub(n,s0))==rho*rho==norm2(sub(f,s0));assert norm2(sub(x,n))==lo*lo and norm2(sub(x,f))==hi*hi;v={'distance_interval':[lo,hi],'near_squared_distance':norm2(sub(x,n)),'far_squared_distance':norm2(sub(x,f))}
 elif t=='T03':
  x,s=vec(p['p']),vec(p['s']);d=sqrt_bounds(norm2(x))[0];new=sqrt_bounds(norm2(sub(x,s)));assert new[0]==new[1] and d-new[0]==F(p['rho']);v={'range_shift':new[0]-d,'lipschitz_bound_attained':True}
 elif t=='T04':
  x,s=vec(p['p']),vec(p['s']);assert dot(x,s)==0 and norm2(s)==F(p['rho'])**2;dsq=norm2(sub(x,s));a,b=sqrt_bounds(dsq);d=F(p['nominal_distance']);assert dsq==26 and a-d>0 and b-d<F(p['rho']);v={'distance_squared':dsq,'shift_interval':[a-d,b-d],'first_order_prediction':'0','nonlinear_shift_nonzero':True}
 elif t=='T05':
  zero=ball_range(p['d'],p['rho']);near=ball_range(p['near_d'],p['rho']);assert zero==(F(0),F(p['rho'])) and near[0]==0;v={'zero_distance_image':zero,'near_zero_image':near,'derivative_required':False}
 elif t=='T06':
  exact,loose=bias_envelope(p['d'],p['rho'],p['b']);actual=F(p['d'])+F(p['rho'])+F(p['b'][1]);assert exact[1]==actual and actual>F(p['d'])+F(p['b'][1]);v={'prediction_interval':exact,'symmetric_relaxation':loose,'boundary_prediction':actual,'old_unexpanded_upper':F(p['d'])+F(p['b'][1])}
 elif t=='T07':
  u=F(1);ranges=(2+u,2-u);false=vec(p['false_pair']);assert sum(ranges)==4 and all(1<=x<=3 for x in false) and sum(false)!=4;v={'exact_relation':'range1+range2=4','feasible_witness':ranges,'independent_box_false_witness':false,'false_witness_excluded_by_shared_reference':True}
 elif t=='T08':
  shifts=sub(vec(p['true_ranges']),vec(p['nominal']));assert shifts==[F(1),F(-1)] and shifts[0]!=shifts[1];v={'required_effective_biases':shifts,'single_shared_widened_bias_cannot_represent_truth':True}
 elif t=='T09':
  x=vec(p['p']);inside=all(F(a)<=y<=F(b) for y,(a,b) in zip(x,p['domain']));assert not inside and norm2(vec(p['noise']))==0;v={'noise_event_score':F(0),'true_state_in_domain':inside,'domain_limited_set_excludes_truth':True}
 elif t=='T10':
  actual=score2(p['R'],p['e']);wrong=norm2(vec(p['e']));assert wrong==2 and actual==20 and wrong<=F(p['tau'])<actual;v={'correct_correlated_score':actual,'wrong_independent_score':wrong,'threshold':F(p['tau']),'wrong_event_accepts_outside_true_noise_event':True}
 elif t=='T11':
  var=F(p['single_variance']);fake=var/p['copies'];e=F(p['epsilon_witness']);radius=F(p['single_radius']);assert e*e<radius**2*var and e*e>radius**2*fake
  try:score2([['1','1'],['1','1']],['1','1']);raise AssertionError('duplicated R was not rejected')
  except ValueError:pass
  v={'true_fused_variance':var,'wrong_independence_variance':fake,'single_coverage_erf':math.erf(float(radius)/math.sqrt(2)),'duplicate_claim_region_true_coverage_erf':math.erf(float(radius)*math.sqrt(float(fake/var))/math.sqrt(2)),'coverage_values_are_analytic_display_not_tail_certificates':True,'duplicated_covariance_status':'R_NOT_POSITIVE_DEFINITE'}
 elif t=='T12':
  n=p['atoms'];a=set(p['reference_fail']);b=set(p['noise_fail']);failure=F(len(a|b),n);as_,ae=F(len(a),n),F(len(b),n);actual=1-failure;wrong=(1-as_)*(1-ae);assert failure==as_+ae and actual<wrong;v={'alpha_reference':as_,'alpha_noise':ae,'actual_joint_inclusion':actual,'valid_union_lower_bound':1-as_-ae,'invalid_product_claim':wrong,'shared_probability_space_atoms':n,'enumeration_not_monte_carlo':True}
 elif t=='T13':
  s=F(p['scale']);base=score2(p['R'],p['e']);R=[[F(x)*s*s for x in row] for row in p['R']];e=[F(x)*s for x in p['e']];other=score2(R,e);a,b=bias_envelope(p['d'],p['rho'],p['b']);aa,bb=bias_envelope(F(p['d'])*s,F(p['rho'])*s,[F(x)*s for x in p['b']]);assert base==other and list(aa)==[x*s for x in a] and list(bb)==[x*s for x in b];v={'score_m':base,'score_mm':other,'range_m':a,'range_mm':aa}
 elif t=='T14':
  Q=[vec(row) for row in p['Q']];x,s,tr=vec(p['p']),vec(p['s']),vec(p['translation']);assert dot(Q[0],Q[0])==dot(Q[1],Q[1])==1 and dot(Q[0],Q[1])==0;xx=[a+b for a,b in zip(matvec(Q,x),tr)];ss=[a+b for a,b in zip(matvec(Q,s),tr)];old=norm2(sub(x,s));new=norm2(sub(xx,ss));assert old==new;v={'original_squared_distance':old,'transformed_squared_distance':new,'orthogonal_exact':True}
 elif t=='T15':
  assert F(p['anchor_reading'])<0;lower=(F(p['anchor_reading'])/F(p['sigma']))**2;assert lower>F(p['tau']);v={'one_anchor_global_score_lower_bound':lower,'threshold':F(p['tau']),'status':'EMPTY_IN_DECLARED_DOMAIN','finite_error_radius':None}
 elif t=='T16':
  x,s,tr=vec(p['p']),vec(p['s']),vec(p['translation']);shifted_x=[a+b for a,b in zip(x,tr)];shifted_s=[a+b for a,b in zip(s,tr)];assert norm2(sub(x,s))==norm2(sub(shifted_x,shifted_s));mx=[x[0],-x[1]];ms=[s[0],-s[1]]
  for a in map(vec,p['anchors']):assert norm2(sub(x,a))==norm2(sub(mx,a)) and norm2(sub(s,a))==norm2(sub(ms,a))
  assert norm2(sub(x,s))==norm2(sub(mx,ms));assert F(1)+F(0)==F('1/2')+F('1/2');v={'joint_translation_invariant':True,'collinear_joint_reflection_invariant':True,'distance_bias_ambiguity':[['1','0'],['1/2','1/2']],'unique_position_not_proved_by_row_count':True}
 elif t=='T17':
  L=[vec(row) for row in p['L']];R=[vec(row) for row in p['R']];assert [[dot(a,b) for b in L] for a in L]==R;e=vec(p['e']);w=[e[0]/L[0][0],F(0)];w[1]=(e[1]-L[1][0]*w[0])/L[1][1];score=score2(R,e);assert score==norm2(w)==5 and p['measurement_dimension']==2;v={'whitened_noise':w,'score':score,'noise_degrees_of_freedom':2,'not_fitted_residual_df':True}
 elif t=='T18':
  b=F(p['b']);n=p['rows'];assert norm2(vec(p['noise']))==0;wrong=n*(b/F(p['sigma']))**2;v={'fixed_bias_mean':[b]*n,'fixed_bias_covariance':[['0']*n for _ in range(n)],'true_random_noise_score':'0','score_if_fixed_bias_misclassified_zero_mean_noise':wrong};assert wrong>6
 elif t=='T19':
  R,Q,C,H=(F(p[k]) for k in ['R','Q','cross','H']);true=R+H*H*Q+2*H*C;wrong=R+H*H*Q;assert true==0 and wrong==2;v={'true_total_variance':true,'wrong_no_cross_term_variance':wrong,'joint_model':'epsilon=Z, delta_s=-Z, Var(Z)=1; no sampling'}
 elif t=='T20':
  old=tail4(p['q_A0'],p['terms']);new=tail4(p['q_A2_example'],p['terms']);a,eps=F(p['alpha_reference']),F(p['alpha_noise']);assert old<F('1/20') and new<eps and a+eps==F('1/20');v={'old_tail_upper':old,'new_tail_upper':new,'old_tau_plus_reference_lower':1-a-old,'allocated_tau_plus_reference_lower':1-a-new,'advertised_allocation_lower':1-a-eps,'threshold_dimension':4,'terms':p['terms']};assert 1-a-old<F('19/20')
 else:raise ValueError(t)
 return v

def main(out,freeze):
 if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=freeze:raise RuntimeError('HEAD differs from requested frozen source')
 freeze_manifest=json.loads((DOC/'FREEZE_MANIFEST.json').read_text())
 for p,h in freeze_manifest['files'].items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
 count=source_check();out.mkdir(parents=True,exist_ok=False);cfg=json.loads((DOC/'INPUTS.json').read_text());checks=[]
 for z in cfg['formal_cases']:
  try:result=case(z);row=dict(id=z['id'],status='PASS',classification='COUNTEREXAMPLE_CONFIRMED' if z['id'] in NEGATIVE else 'IDENTITY_OR_BOUND_VERIFIED',criterion=z['criterion'],inputs=z['inputs'],output=result)
  except Exception as e:row=dict(id=z['id'],status='FAIL',criterion=z['criterion'],inputs=z['inputs'],exception=repr(e),traceback=traceback.format_exc())
  save(out/(z['id']+'.json'),row);checks.append(row)
 rows=[]
 for d in cfg['sensitivity']['distances_m']:
  for rho in cfg['sensitivity']['radii_m']:
   dr=ball_range(d,rho);exact,loose=bias_envelope(d,rho,cfg['sensitivity']['bias_m']);assert loose[0]<=exact[0]<=exact[1]<=loose[1]
   rows.append(dict(d_m=F(d),rho_m=F(rho),distance_min=dr[0],distance_max=dr[1],distance_width=dr[1]-dr[0],biased_prediction_min=exact[0],biased_prediction_max=exact[1],symmetric_relaxation_min=loose[0],symmetric_relaxation_max=loose[1],exact_scalar_width=exact[1]-exact[0],relaxed_width=loose[1]-loose[0],extra_lower_slack=exact[0]-loose[0]))
 assert len(checks)==20 and len(rows)==20
 with (out/'SENSITIVITY.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(clean(rows))
 save(out/'INPUTS.json',cfg);save(out/'RESULTS.json',checks);save(out/'RUN.json',dict(freeze_sha=freeze,source_sha=cfg['source_sha'],input_sha256=digest(cfg),python=platform.python_version(),planned_checks=20,completed_checks=len(checks),passed=sum(z['status']=='PASS' for z in checks),failed=sum(z['status']=='FAIL' for z in checks),confirmed_counterexamples=sum(z.get('classification')=='COUNTEREXAMPLE_CONFIRMED' for z in checks),sensitivity_rows=len(rows),source_files_before=count,source_files_after=source_check(),**CALLS));print(json.dumps(json.loads((out/'RUN.json').read_text()),indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--freeze');p.add_argument('--development',action='store_true');a=p.parse_args();protect()
 if a.development:
  assert sqrt_bounds(F(5)**2+F(12)**2)==(F(13),F(13));save(a.out,dict(stage='DEVELOPMENT',helper_checks=1,formal_cases_run=0,case='5-12-13 exact norm',**CALLS));print('development helper PASS')
 else:
  if not a.freeze:p.error('--freeze required for validation')
  main(a.out,a.freeze)
