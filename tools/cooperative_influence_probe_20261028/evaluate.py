#!/usr/bin/env python3
"""Saved-evidence-only independent audit and per-car benefit/cost evaluation."""
import argparse,csv,gzip,json,math,sys
from collections import Counter
from pathlib import Path
import numpy as np
from common import METHODS,SCENARIOS,sha,dump,read
import independent as ind
PERIODS={'all':lambda t:True,'pre':lambda t:3<=t<24,'fault':lambda t:24<=t<38,'recovery':lambda t:38<=t<48,'late':lambda t:48<=t<=63}
def csvwrite(p,rs):
 with Path(p).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]),lineterminator='\n');w.writeheader();w.writerows(rs)
def rms(x):return float(np.sqrt(np.mean(np.square(x)))) if len(x) else None
def finite(p):return p is not None and bool(np.isfinite(p).all())
def audit_rows(rows,config,events,iref,kind,method):
 checks=Counter();deltas=[];previous={};constants={};consumed={};origin=events[0]['receive_epoch_ns'];streams=ind.audit.input_streams(events)
 for row,ir in zip(rows,iref):
  assert row['state_epoch_ns']==ir['state_epoch_ns'] and row['availability_cutoff_epoch_ns']==ir['availability_cutoff_epoch_ns']
  ind.audit.check_bins(row,config,streams,origin);checks['receive_bins']+=1
  ref=row.get('reference',ir)
  for key in ['times_s','states','local','observations','prior','eliminated_constant']:
   assert ref['snapshot'][key]==ir['snapshot'][key],('independent reference changed',method,key,row['state_time_s'])
  assert ref['pose']==ir['pose'] and ref['accepted_graph']==ir['accepted_graph'];checks['reference_exact_I']+=1
  if kind=='new':
   assert ref['state_epoch_ns']==row['state_epoch_ns'] and ref['availability_cutoff_epoch_ns']==row['availability_cutoff_epoch_ns']
   assert all(p is None for p in ref['snapshot']['peers_m'])
  for role,obj in [('main',row)]+([('reference',ref)] if kind=='new' else []):
   s=obj['snapshot'];seen=consumed.setdefault(role,set());assert len(s['times_s'])<=21
   weight=row.get('peer_information_weight',1.) if role=='main' else 1.
   for md in obj['marginalization_details']:
    assert md['before']==previous[role];previous[role]=md['after'];constants[role]=constants.get(role,0.)+md['constant']
    deltas.append(ind.marginal(md,config,weight,s['peer_enabled']));checks['FD_all_marginals']+=1
    if s['peer_enabled'] and md['old_peer_m'] is not None:
     fid='peer|'+str(origin+round(md['times_s'][0]*1e9));assert fid not in seen;seen.add(fid)
   if role in previous:assert previous[role]==s['prior']
   previous[role]=s['prior'];assert abs(constants.get(role,0.)-s['eliminated_constant'])<1e-9
   active={'peer|'+str(origin+round(t*1e9)) for t,z in zip(s['times_s'],s['peers_m']) if s['peer_enabled'] and z is not None}
   assert not active&seen
   assert active==set(obj['provenance']['window_peer_factor_ids']) and seen==set(obj['provenance']['prior_peer_factor_ids']);checks['factor_prior_chain']+=1
   accepted=obj.get('main_accepted_graph',obj['accepted_graph']) if role=='main' else obj['accepted_graph']
   if accepted:
    r=ind.residuals(np.array(s['states']).ravel(),s,config,weight);cost=float(r@r/2);assert abs(cost-obj['optimizer']['cost'])<1e-7*max(1.,cost)
    pose=obj.get('main_pose',obj['pose']) if role=='main' else obj['pose'];assert pose==s['states'][-1];checks['full_active_objective']+=1
  if kind!='reuse':
   mode=row['publication_mode'];known=bool(ref['accepted_graph'] and finite(ref['pose']));assert row['reference_accepted']==known
   if mode=='reference_fallback':assert row['pose']==ref['pose'] and not row['joint_optimization_success'] and not row['accepted_graph']
   if mode=='unknown':assert not row['budget_certified'] and not row['joint_optimization_success']
   if mode=='post_clip':assert not row['joint_optimization_success']
   if row['budget_certified']:
    assert known;distance=np.linalg.norm(ind.antenna_xy(row['pose'],config)-ind.antenna_xy(ref['pose'],config),axis=1)
    assert max(distance)<=row['budget_m']+1e-7;np.testing.assert_allclose(distance,row['published_separation_m'],atol=1e-12,rtol=0);checks['actual_published_budget']+=1
   if mode=='normal_joint':assert row['pose']==row['snapshot']['states'][-1]
   assert row['covariance'] is None
   if kind=='derived' and known:
    a=ind.antenna_xy(row['main_pose'],config);b=ind.antenna_xy(ref['pose'],config);d=a-b;n=np.linalg.norm(d,axis=1);expect=b+d*np.minimum(1.,row['budget_m']/np.maximum(n,1e-300))[:,None]
    np.testing.assert_allclose(ind.antenna_xy(row['pose'],config),expect,atol=1e-12,rtol=0);checks['independent_clip_geometry']+=1
   for it in row.get('solver_iterations',[]):
    r=ind.residuals(np.asarray(it['states']).ravel(),row['snapshot'],config,row['peer_information_weight']);assert abs(float(r@r/2)-it['cost'])<1e-7*max(1.,it['cost']);checks['SLSQP_iteration_objectives']+=1
 return dict(checks=dict(checks),max_marginal_errors={k:max((d[k] for d in deltas),default=0.) for k in ['H_max_abs','g_max_abs','constant_abs']})
def evaluate(root,out):
 out.mkdir(exist_ok=False);index=json.loads((root/'RUN_INDEX.json').read_text());expected={s+'_seed101__'+m for s in SCENARIOS for m in METHODS}
 assert index['status']=='DONE' and len(index['cells'])==16 and {c['id'] for c in index['cells']}==expected
 for p,s in index['source_sha256'].items():assert sha(root/'source'/p)==s
 allrows=[];audits=[];costs=[];bycase={};configs={};stats=Counter()
 for cell in index['cells']:
  case=cell['case'];m=cell['method'];kind=cell['kind'];run=root/cell['path'];inp=root/'inputs'/case
  assert cell['status']==('REUSED_VERIFIED' if kind=='reuse' else 'DONE') and sha(run/'run.json')==cell['run_sha256']
  meta=json.loads((run/'run.json').read_text());assert meta['status']=='DONE'
  for name,s in cell['input_sha256'].items():assert sha(inp/name)==s
  outputs=meta['outputs'];outputs=[dict(path=k,**v) for k,v in outputs.items()] if isinstance(outputs,dict) else outputs
  for p in outputs:assert sha(run/p['path'])==p['sha256']
  if kind!='reuse':assert meta['source_sha256']==index['source_sha256'] and meta['commit']==index['commit'];assert meta['input_sha256']==cell['input_sha256']
  config=json.loads((inp/'config.json').read_text());configs[case]=config;events=read(inp/'events.jsonl.gz');truth={r['state_epoch_ns']:r for r in read(inp/'truth.jsonl')}
  rows=read(run/'updates.jsonl.gz');iref=read(root/f'reused/{case}__I/updates.jsonl.gz');assert len(rows)==len(iref)==63
  ar=audit_rows(rows,config,events,iref,kind,m);ar.update(id=cell['id'],status='PASS');audits.append(ar);stats.update(ar['checks']);print('AUDIT',cell['id'],'PASS',flush=True)
  main_s=ref_s=clip_s=0.;nits=[];poses=[];bycase[cell['scenario'],m]={}
  for r,ir in zip(rows,iref):
   ep=r['state_epoch_ns'];t=r['state_time_s'];assert ep==events[0]['receive_epoch_ns']+round(t*1e9);ref=r.get('reference',ir);p=r['pose'];valid=finite(p)
   mode=r.get('publication_mode',('independent' if m=='I' else 'normal_joint') if r['accepted_graph'] else 'unknown')
   reason=r.get('publication_reason','BASELINE_ACCEPTED' if r['accepted_graph'] else 'STARTUP')
   weight=r.get('peer_information_weight',0. if m=='I' else 1.);known=bool(ref['accepted_graph'] and finite(ref['pose']))
   v=dict(scenario=cell['scenario'],method=m,t_s=t,state_epoch_ns=ep,availability_cutoff_epoch_ns=r['availability_cutoff_epoch_ns'],finite=valid,reference_accepted=known,
    mode=mode,reason=reason,main_accepted=r.get('main_accepted_graph',r['accepted_graph']),joint_success=r.get('joint_optimization_success',bool(m=='J' and r['accepted_graph'])),
    status=r.get('main_status',r['status']),budget_m=r.get('budget_m'),budget_certified=r.get('budget_certified',False),peer_information_weight=weight,
    main_wall_s=r.get('main_update_wall_s',r['update_wall_s']),reference_wall_s=r.get('reference_update_wall_s',ir['update_wall_s'] if m!='I' else 0.),clip_wall_s=r.get('clip_wall_s',0.),
    prior_peer_n=len(r['provenance']['prior_peer_factor_ids']),window_peer_n=len(r['provenance']['window_peer_factor_ids']),
    prior_cross_norm=float(np.linalg.norm((np.array(r['snapshot']['prior']['matrix']).T@np.array(r['snapshot']['prior']['matrix']))[:3,3:])),
    optimizer_status=r.get('optimizer',{}).get('status'),optimizer_nfev=r.get('optimizer',{}).get('nfev'),slsqp_nit=r.get('solver_diagnostics',{}).get('nit'),
    scalar_variables=r['scalar_variables'])
   tr=truth[ep];ants=[];trueants=[];refs=ind.antenna_xy(ref['pose'],config) if finite(ref['pose']) else None
   for i,car in enumerate(['car1','car2']):
    true=tr['cars'][car];ant=ind.audit.ant(p[3*i:3*i+3],config['models'][car]) if valid else None;ants.append(ant);trueants.append(np.array(true['antenna_xyz_m']))
    err=None if not valid else float(np.linalg.norm(ant[:2]-true['antenna_xyz_m'][:2]));re=None if refs is None else float(np.linalg.norm(refs[i]-true['antenna_xyz_m'][:2]));disp=None if not valid or refs is None else float(np.linalg.norm(ant[:2]-refs[i]))
    if err is not None and re is not None:assert abs(err-re)<=disp+1e-12
    v.update({car+'_antenna_xy_error_m':err,car+'_base_xy_error_m':None if not valid else float(np.linalg.norm(np.array(p[3*i:3*i+2])-true['pose'][:2])),car+'_yaw_error_rad':None if not valid else ind.audit.wrap(p[3*i+2]-true['pose'][2]),
     car+'_reference_error_m':re,car+'_separation_m':disp,car+'_help_m':None if err is None or re is None else max(0.,re-err),car+'_harm_m':None if err is None or re is None else max(0.,err-re),
     car+'_excess004_m':None if disp is None else max(0.,disp-.04),car+'_excess100_m':None if disp is None else max(0.,disp-1.)})
   v.update(relative_xy_error_m=None if not valid else float(np.linalg.norm((ants[0]-ants[1])[:2]-(trueants[0]-trueants[1])[:2])),distance_error_m=None if not valid else float(np.linalg.norm(ants[0]-ants[1])-np.linalg.norm(trueants[0]-trueants[1])))
   allrows.append(v);bycase[cell['scenario'],m][ep]=v;main_s+=v['main_wall_s'];ref_s+=v['reference_wall_s'];clip_s+=v['clip_wall_s'];nits+=[v['slsqp_nit']] if v['slsqp_nit'] is not None else []
  vs=list(bycase[cell['scenario'],m].values())
  costs.append(dict(scenario=cell['scenario'],method=m,kind=kind,denominator=63,finite=sum(v['finite'] for v in vs),reference_accepted=sum(v['reference_accepted'] for v in vs),joint_success=sum(v['joint_success'] for v in vs),
    normal_joint=sum(v['mode']=='normal_joint' for v in vs),post_clip=sum(v['mode']=='post_clip' for v in vs),fallback=sum(v['mode']=='reference_fallback' for v in vs),unknown=sum(v['mode']=='unknown' for v in vs),
    timeout=sum(v['reason']=='TIMEOUT' for v in vs),failure=sum('failed' in v['status'] or 'error' in v['status'] for v in vs),
    main_total_s=main_s,reference_total_s=ref_s,clip_total_s=clip_s,combined_update_p95_s=float(np.percentile([v['main_wall_s']+v['reference_wall_s']+v['clip_wall_s'] for v in vs],95)),
    elapsed_wall_s=meta.get('elapsed_wall_s',meta.get('original_runtime_s',meta.get('elapsed_with_current_IO_s'))),timing_origin='current_main_and_private_reference' if kind=='new' else 'historical_main_reference_plus_current_clip' if kind=='derived' else 'historical_baseline',max_slsqp_nit=max(nits,default=0),max_solve_scalars=max(v['scalar_variables'] for v in vs)))
 metrics=[];contrasts=[]
 for (s,m),values in bycase.items():
  for scope in ['all_finite','reference_accepted']:
   for period,pred in PERIODS.items():
    total=[v for v in values.values() if pred(v['t_s'])];sel=[v for v in total if v['finite'] and (scope=='all_finite' or v['reference_accepted'])]
    for car in ['car1','car2']:
     row=dict(scenario=s,method=m,scope=scope,period=period,car=car,denominator=len(total),n=len(sel),antenna_xy_rmse_m=rms([v[car+'_antenna_xy_error_m'] for v in sel]),base_xy_rmse_m=rms([v[car+'_base_xy_error_m'] for v in sel]),yaw_rmse_rad=rms([v[car+'_yaw_error_rad'] for v in sel]),
      mean_help_m=None if not sel else float(np.mean([v[car+'_help_m'] for v in sel])),mean_harm_m=None if not sel else float(np.mean([v[car+'_harm_m'] for v in sel])),help_n=sum(v[car+'_help_m']>1e-9 for v in sel),harm_n=sum(v[car+'_harm_m']>1e-9 for v in sel),
      max_separation_m=max((v[car+'_separation_m'] for v in sel),default=None),max_excess004_m=max((v[car+'_excess004_m'] for v in sel),default=None),max_excess100_m=max((v[car+'_excess100_m'] for v in sel),default=None),
      excess004_n=sum(v[car+'_excess004_m']>1e-7 for v in sel),excess100_n=sum(v[car+'_excess100_m']>1e-7 for v in sel),fallback=sum(v['mode']=='reference_fallback' for v in total),unknown=sum(v['mode']=='unknown' for v in total),post_clip=sum(v['mode']=='post_clip' for v in total),joint_success=sum(v['joint_success'] for v in total),relative_xy_rmse_m=rms([v['relative_xy_error_m'] for v in sel]),distance_rmse_m=rms([v['distance_error_m'] for v in sel]))
     metrics.append(row)
    for name,other in [('same_input_vs_I',bycase[s,'I'])]+([('same_method_vs_nominal',bycase['nominal',m])] if s!='nominal' else []):
     selected=[v for v in sel if other[v['state_epoch_ns']]['finite'] and (scope=='all_finite' or other[v['state_epoch_ns']]['reference_accepted'])]
     for car in ['car1','car2']:
      key=car+'_antenna_xy_error_m';target=rms([v[key] for v in selected]);control=rms([other[v['state_epoch_ns']][key] for v in selected]);contrasts.append(dict(scenario=s,method=m,scope=scope,period=period,car=car,contrast=name,n=len(selected),target_rmse_m=target,reference_rmse_m=control,delta_rmse_m=None if target is None else target-control))
 # Same solver / inactive controls, paired published antenna differences without truth.
 controls=[]
 for s in SCENARIOS:
  for a,b in [('U','J'),('K100','U'),('K004','C004')]:
   pairs=[(v,bycase[s,b][ep]) for ep,v in bycase[s,a].items() if v['reference_accepted'] and v['finite'] and bycase[s,b][ep]['finite']]
   ra=read(root/next(c['path'] for c in index['cells'] if c['scenario']==s and c['method']==a)/'updates.jsonl.gz');rb=read(root/next(c['path'] for c in index['cells'] if c['scenario']==s and c['method']==b)/'updates.jsonl.gz');config=configs[s+'_seed101']
   for car,i in [('car1',0),('car2',1)]:
    distances=[float(np.linalg.norm(ind.antenna_xy(x['pose'],config)[i]-ind.antenna_xy(y['pose'],config)[i])) for x,y in zip(ra[2:],rb[2:]) if finite(x['pose']) and finite(y['pose'])]
    controls.append(dict(scenario=s,comparison=a+'_'+b,car=car,n=len(distances),max_antenna_difference_m=max(distances),rms_antenna_difference_m=rms(distances)))
 for name,rows in [('metrics.csv',metrics),('contrasts.csv',contrasts),('costs.csv',costs),('solver_controls.csv',controls)]:csvwrite(out/name,rows)
 with gzip.open(out/'timeline.csv.gz','xt',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(allrows[0]),lineterminator='\n');w.writeheader();w.writerows(allrows)
 dump(out/'audits.json',dict(status='PASS',counts=dict(stats),cells=audits))
 assert not {'core','bindings','graph','legacy','frontend','probe','scipy.optimize'}&set(sys.modules)
 dump(out/'receipt.json',dict(status='PASS',cells=16,reused=4,derived=4,new_main=8,new_private_references=8,publication_records=len(allrows),counts=dict(stats),reader_sha256=sha(Path(__file__)),equations_sha256=sha(Path(ind.__file__)),solver_imports=[],source_commit=index['commit']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();evaluate(a.root,a.output)
