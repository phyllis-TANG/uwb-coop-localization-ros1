"""Independent scalar readback. Imports no graph, frontend, online Jacobian or solver."""
import copy, importlib.util, json
import numpy as np
from support import *
p=EVIDENCE/'source/tools/two_car_fixed_lag_fgo_v1/audit.py'
spec=importlib.util.spec_from_file_location('scalar_audit',p);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

def check():
 idx=json.loads((OUT/'v1/RUN_INDEX.json').read_text());assert idx['status']=='DONE'
 for p,h in idx['source_sha256'].items():assert sha(ROOT/p)==h
 for c in idx['cells']:
  if c['mode']!='verified_reuse':assert sha(OUT/'v1'/c['path'])==c['sha256']
 results=[]
 for case in SET['cases']:
  cfg=config(case);audit.residuals.peer_sigma=cfg['peer']['sigma_m'];events=read(EVIDENCE/'inputs'/case/'events.jsonl.gz');streams=audit.input_streams(events);origin=events[0]['receive_epoch_ns'];rows=read(OUT/'v1'/(case+'__N.jsonl.gz'));jr=old(case,'J');seen=[];prev=None;constant=0.;costdiff=[];marg=[];before=[]
  assert len(rows)==63
  for r,j in zip(rows,jr):
   s=r['snapshot'];t=r['state_time_s'];audit.check_bins(r,cfg,streams,origin)
   assert r['availability_cutoff_epoch_ns']==j['availability_cutoff_epoch_ns'];assert r['state_epoch_ns']==j['state_epoch_ns'];assert r['bins']==j['bins']
   if t<SET['cut_new_peer_at_state_s']:
    np.testing.assert_allclose(r['pose'],j['pose'],atol=SET['regression_atol_m_rad'],rtol=0)
    assert s==j['snapshot'];before.append(t)
   else:assert s['peers_m'][-1] is None and not r['peer_factor_used']
   for d in r['marginalization_details']:
    assert d['before']==prev;prev=d['after'];constant+=d['constant'];marg.append(audit.marginal_check(d,cfg,True))
    if d['old_peer_m'] is not None:assert d['times_s'][0] not in seen;seen.append(d['times_s'][0])
   if prev is not None:assert prev==s['prior']
   prev=s['prior'];assert abs(constant-s['eliminated_constant'])<1e-9
   active=[u for u,p in zip(s['times_s'],s['peers_m']) if p is not None];assert not set(active)&set(seen);assert seen==r['provenance']['prior_peer_times_s'];assert active==r['provenance']['window_peer_times_s'];assert len(s['states'])<=21
   if r['accepted_graph']:
    rr=audit.residuals(np.array(s['states']).ravel(),s['times_s'],s['local'],s['observations'],s['peers_m'],cfg['models'],s['prior'],True);dif=abs(rr@rr/2-r['optimizer']['cost']);assert dif<1e-7;costdiff.append(dif)
  snapchecks=[]
  for pn in SET['snapshot_priors']:
   for xn in SET['snapshot_initializations']:
    r=read(OUT/'v1'/(case+'__prior'+pn+'__init'+xn+'.jsonl.gz'))[0];s=r['snapshot'];rr=audit.residuals(np.array(s['states']).ravel(),s['times_s'],s['local'],s['observations'],s['peers_m'],cfg['models'],s['prior'],True);assert abs(rr@rr/2-r['cost'])<1e-7
    assert all(z is None for z in s['peers_m']);snapchecks.append(r['retained_factors_sha256'])
  assert len(set(snapchecks))==1
  results.append(dict(case=case,status='PASS',publications=63,receive_bins=63,exact_archived_J_snapshots_before39=len(before),objectives=len(costdiff),max_cost_abs=max(costdiff),marginalizations_checked=len(marg),marginal_max_H_abs=max(m['hessian_max_abs'] for m in marg),marginal_max_g_abs=max(m['gradient_max_abs'] for m in marg),marginal_max_constant_abs=max(m['constant_abs'] for m in marg),snapshot_objectives=4))
 full=read(OUT/'v1'/(SET['cases'][0]+'__N.jsonl.gz'));prefix=read(OUT/'v1/nominal_prefix46.jsonl.gz')
 for p,f in zip(prefix,full):
  for k in ['pose','snapshot','accepted_graph','status','state_epoch_ns','availability_cutoff_epoch_ns','bins','provenance']:assert p[k]==f[k],k
 report=dict(status='PASS',cases=results,prefix_publications=len(prefix),auditor_source_sha256=sha(EVIDENCE/'source/tools/two_car_fixed_lag_fgo_v1/audit.py'),sharing='Uses frozen independent scalar audit equations and input schema; no online solver/Jacobian import',limitations='Checks artifact consistency and causal prefix, not true accuracy or validity of synthetic assumptions')
 dump(DOC/'CHECKS.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':check()
