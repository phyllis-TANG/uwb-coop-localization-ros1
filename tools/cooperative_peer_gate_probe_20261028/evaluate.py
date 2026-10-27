#!/usr/bin/env python3
"""Independent readback/evaluation: no graph, frontend, probe or optimizer imports."""
import argparse,csv,gzip,hashlib,importlib.util,json,math,sys
from collections import Counter
from pathlib import Path
import numpy as np
from index_contract import validate
PERIODS={'all':lambda t:True,'pre':lambda t:3<=t<24,'fault':lambda t:24<=t<38,'recovery':lambda t:38<=t<48,'late':lambda t:48<=t<=63}
ERRORS=('car1_base_xy_error_m','car1_antenna_xy_error_m','car1_yaw_error_rad','car2_base_xy_error_m','car2_antenna_xy_error_m','car2_yaw_error_rad','relative_antenna_xy_error_m','distance_error_m')
def read(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return [json.loads(s) for s in f if s.strip()]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def dump(p,j):Path(p).write_text(json.dumps(j,indent=2,sort_keys=True,allow_nan=False)+'\n')
def csv_write(p,rows):
 with Path(p).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def ant(p,m):
 lx,ly=m['base_to_antenna_body_xy_m'];c,s=math.cos(p[2]),math.sin(p[2]);return np.array([p[0]+c*lx-s*ly,p[1]+s*lx+c*ly,m['antenna_height_m']])
def wrap(x):return math.atan2(math.sin(x),math.cos(x))
def rmse(rows,key):
 v=[r[key] for r in rows if r[key] is not None];return float(np.sqrt(np.mean(np.square(v)))) if v else None
def in_scope(rows,epochs,scope):return [r for r in rows if r['finite_pair'] and (scope=='all_finite' or r['state_epoch_ns'] in epochs)]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--matrix',type=Path,required=True);ap.add_argument('--frozen-source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False);index=json.loads((a.matrix/'index.json').read_text());validate(index,True)
 for p,s in index['execution_source_sha256'].items():assert sha(a.matrix/'source'/p)==s
 modelpath=a.frozen_source/'tools/two_car_fixed_lag_fgo_v1/audit.py';assert sha(modelpath)==index['frozen_source_sha256']['tools/two_car_fixed_lag_fgo_v1/audit.py'];spec=importlib.util.spec_from_file_location('independent_frozen_equations',modelpath);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 loaded={};configs={};sources={};inputmeta={};truths={};labels={};streams={};checks=Counter();marginal=[]
 for cell in index['cells']:
  key=(cell['scenario'],cell['seed']);run=a.matrix/'runs'/cell['cell_id'];meta=json.loads((run/'run.json').read_text());assert sha(run/'run.json')==cell['run_manifest_sha256'];assert meta['status']=='DONE';assert meta['execution_source_sha256']==index['execution_source_sha256'];assert meta['frozen_source_sha256']==index['frozen_source_sha256']
  for item in meta['outputs']:assert sha(run/item['path'])==item['sha256'] and (run/item['path']).stat().st_size==item['size_bytes'];checks['output_SHA']+=1
  inp=a.matrix.parent/'inputs'/f"{cell['scenario']}_seed{cell['seed']}"
  for name,field in [('events.jsonl.gz','events_sha256'),('config.json','config_sha256'),('truth.jsonl','truth_sha256'),('labels.json','labels_sha256')]:assert sha(inp/name)==cell[field];checks['input_SHA']+=1
  if key not in configs:
   configs[key]=json.loads((inp/'config.json').read_text());events=read(inp/'events.jsonl.gz');sources[key]=events;streams[key]=audit.input_streams(events);truths[key]={r['state_epoch_ns']:r for r in read(inp/'truth.jsonl')};labels[key]=json.loads((inp/'labels.json').read_text());inputmeta[key]=events[0]['receive_epoch_ns']
  rows=read(run/'updates.jsonl.gz');assert len(rows)==63 and [r['state_time_s'] for r in rows]==list(range(1,64));assert all(r['state_epoch_ns']==inputmeta[key]+round(r['state_time_s']*1e9) and r['availability_cutoff_epoch_ns']==r['state_epoch_ns']+10**9 for r in rows);loaded[(key[0],key[1],cell['method'])]=rows;checks['complete_runs']+=1
 # Verify the fixed sidecar contract and sole new adapter independently of prepare.py.
 assert {p.name for p in (a.matrix/'runs').iterdir() if p.is_dir()}=={c['cell_id'] for c in index['cells']}
 for (sc,seed),label in labels.items():
  if sc=='nominal':assert label['fault'] is None
  else:
   assert label['fault']['interval_s']==[24.,38.] and label['fault']['kind']==sc
   assert label['fault']['additive_bias_m']==(.3 if sc=='car1_common_wall_bias' else None if sc=='peer_gap' else 1.2)
  if sc!='car1_common_wall_bias':continue
  original=sources[('nominal',seed)];changed=sources[(sc,seed)];assert len(original)==len(changed);assert configs[(sc,seed)]==configs[('nominal',seed)];assert truths[(sc,seed)]==truths[('nominal',seed)]
  count=0
  for x,y in zip(original,changed):
   assert {k:v for k,v in x.items() if k!='value'}=={k:v for k,v in y.items() if k!='value'}
   for key,value in x['value'].items():
    target=x['kind']=='uwb' and x.get('vehicle_id')=='car1' and key in ('node_10','node_2','node_3','node_8') and 24*10**9<=x.get('header_epoch_ns',0)-inputmeta[(sc,seed)]<38*10**9
    if target:assert abs(y['value'][key]-value-.3)<1e-15;count+=1
    else:assert y['value'][key]==value
  assert count==1120;checks['independent_adapter_changed_scalars']+=count
 # Define contamination by raw support, explicitly separate from state-window labels.
 raw_flags={}
 for (sc,seed),config in configs.items():
  base=loaded[(sc,seed,'G0')];origin=inputmeta[(sc,seed)];flags={};events=sources[(sc,seed)]
  for row in base:
   ep=row['state_epoch_ns'];peer=row['peer_dependencies'];fault_peer=sum(sc=='peer_bias' and 24*10**9<=r['identity']['header_epoch_ns']-origin<38*10**9 for r in peer)
   walls=[]
   if sc in ('wall_bias','car1_common_wall_bias'):
    affected=('node_2',) if sc=='wall_bias' else ('node_10','node_2','node_3','node_8')
    support=[e for e in events if e['kind']=='uwb' and e['vehicle_id']=='car1' and e['receive_epoch_ns']<=row['availability_cutoff_epoch_ns'] and abs((e['header_epoch_ns']-origin)/1e9-row['state_time_s'])<=.4 and 24*10**9<=e['header_epoch_ns']-origin<38*10**9]
    if support:walls=['wall|car1|'+k+'|'+str(ep) for k in affected if k in row['bins']['car1']['observations']]
   flags[ep]=dict(peer_fault_support_count=fault_peer,peer_support_count=len(peer),fault_wall_factor_ids=walls)
  raw_flags[(sc,seed)]=flags
 allrows=[];metrics=[];gates=[];costs=[];series={};common={}
 for (sc,seed),config in configs.items():
  common[(sc,seed)]=set.intersection(*[{r['state_epoch_ns'] for r in loaded[(sc,seed,m)] if r['accepted_graph'] and r['pose'] is not None} for m in ('G0','G1','G2')])
  g0={r['state_epoch_ns']:r for r in loaded[(sc,seed,'G0')]};origin=inputmeta[(sc,seed)];flag=raw_flags[(sc,seed)];fault_peers={'peer|'+str(ep) for ep,f in flag.items() if f['peer_fault_support_count']};fault_walls=set(k for f in flag.values() for k in f['fault_wall_factor_ids'])
  for method in ('G0','G1','G2'):
   rows=loaded[(sc,seed,method)];cell=next(c for c in index['cells'] if (c['scenario'],c['seed'],c['method'])==(sc,seed,method));meta=json.loads((a.matrix/'runs'/cell['cell_id']/'run.json').read_text());evaluated=[];prior_walls=set();aux_prior_walls=set();previous_prior={};consumed={};all_peer_values={}
   audit.residuals.peer_sigma=config['peer']['sigma_m']
   for row in rows:
    ep=row['state_epoch_ns'];t=row['state_time_s'];truth=truths[(sc,seed)][ep];s=row['snapshot'];gate=row['gate'];audit.check_bins(row,config,streams[(sc,seed)],origin);checks['receive_prefix_bins']+=1
    for dep in row['peer_dependencies']:assert dep['identity']['receive_epoch_ns']<=row['availability_cutoff_epoch_ns'];checks['peer_raw_cutoffs']+=1
    for role,obj in [('main',row),('auxiliary',row['auxiliary'])]:
     if obj is None:continue
     snap=obj['snapshot'];seen=consumed.setdefault(role,set());assert len(snap['times_s'])<=21
     for md in obj['marginalization_details']:
      if role in previous_prior:assert md['before']==previous_prior[role]
      previous_prior[role]=md['after'];old_ep=origin+round(md['times_s'][0]*1e9);fid='peer|'+str(old_ep)
      if snap['peer_enabled'] and md['old_peer_m'] is not None:assert fid not in seen;seen.add(fid)
     if role in previous_prior:assert snap['prior']==previous_prior[role]
     previous_prior[role]=snap['prior'];active={}
     for tt,p in zip(snap['times_s'],snap['peers_m']):
      if not snap['peer_enabled'] or p is None:continue
      fid='peer|'+str(origin+round(tt*1e9));active[fid]=p
      if (role,fid) in all_peer_values:assert all_peer_values[(role,fid)]==p
      all_peer_values[(role,fid)]=p
     assert not set(active)&seen;assert set(obj['provenance']['window_peer_factor_ids'])==set(active);assert set(obj['provenance']['prior_peer_factor_ids'])==seen;checks['prior_source_chain']+=1
     if obj['accepted_graph']:
      r=audit.residuals(np.array(snap['states']).ravel(),snap['times_s'],snap['local'],snap['observations'],snap['peers_m'],config['models'],snap['prior'],snap['peer_enabled']);cost=.5*float(r@r);assert abs(cost-obj['optimizer']['cost'])<1e-8;checks['independent_objective_cost']+=1
     if obj['marginalization_details'] and (t==22 or t==63):
      for md in obj['marginalization_details']:marginal.append(dict(scenario=sc,seed=seed,method=method,role=role,**audit.marginal_check(md,config,snap['peer_enabled'])));checks['FD_Schur']+=1
    for md in row['provenance']['marginalizations']:prior_walls.update(set(md['consumed_wall_factor_ids'])&fault_walls)
    if row['auxiliary'] is not None:
     aux=row['auxiliary'];assert aux['state_epoch_ns']==ep and aux['availability_cutoff_epoch_ns']==row['availability_cutoff_epoch_ns'];assert aux['pose']==g0[ep]['pose'];assert aux['snapshot']['prior']==g0[ep]['snapshot']['prior'];assert not aux['snapshot']['peer_enabled'] and all(p is None for p in aux['snapshot']['peers_m']);checks['auxiliary_equal_G0_pose_prior']+=1
     for md in aux['provenance']['marginalizations']:aux_prior_walls.update(set(md['consumed_wall_factor_ids'])&fault_walls)
     if row['peer_median_m'] is None:assert gate['state']=='missing' and not gate['admitted_by_policy']
     elif not aux['accepted_graph']:assert gate['state']=='unknown' and not gate['admitted_by_policy']
     else:
      prediction=float(np.linalg.norm(ant(aux['pose'][:3],config['models']['car1'])-ant(aux['pose'][3:],config['models']['car2'])));q=abs(row['peer_median_m']-prediction)/config['peer']['sigma_m'];assert abs(prediction-gate['auxiliary_prediction_m'])<1e-12 and abs(q-gate['engineering_q'])<1e-12;assert gate['admitted_by_policy']==(q<=3);checks['independent_gate_formula']+=1
    actual=s['peer_enabled'] and t in s['times_s'] and s['peers_m'][s['times_s'].index(t)] is not None
    assert bool(actual)==row['peer_factor_used']==gate['information_entered'];assert (row['actual_peer_factor_id'] is not None)==actual
    if method=='G2' and not gate['admitted_by_policy']:assert not actual
    finite=row['pose'] is not None and bool(np.isfinite(row['pose']).all());angles=[];ants=[];d=dict(scenario=sc,seed=seed,method=method,state_epoch_ns=ep,t_s=t,cutoff_epoch_ns=row['availability_cutoff_epoch_ns'],status=row['status'],accepted=row['accepted_graph'],finite_pair=finite,common_accepted=ep in common[(sc,seed)],gate_state=gate['state'],gate_reason=gate['reason'],q=gate['engineering_q'],auxiliary_prediction_m=gate['auxiliary_prediction_m'],peer_measured_m=row['peer_median_m'],peer_available=row['peer_median_m'] is not None,peer_admitted=bool(actual),actual_peer_factor_id=row['actual_peer_factor_id'],**flag[ep],state_in_peer_fault=sc=='peer_bias' and 24<=t<38,window_peer_factors=len(row['provenance']['window_peer_factor_ids']),prior_peer_factors=len(row['provenance']['prior_peer_factor_ids']),window_fault_peer_factors=len(set(row['provenance']['window_peer_factor_ids'])&fault_peers),prior_fault_peer_factors=len(set(row['provenance']['prior_peer_factor_ids'])&fault_peers),window_fault_wall_factors=sum('wall|car1|'+k+'|'+str(origin+round(tt*1e9)) in fault_walls for tt,o in zip(s['times_s'],s['observations']) for k in o['car1']),prior_fault_wall_factors=len(prior_walls),auxiliary_prior_fault_wall_factors=len(aux_prior_walls),window_start_s=s['times_s'][0] if s['times_s'] else None,prior_cross_information_norm=float(np.linalg.norm((np.array(s['prior']['matrix']).T@np.array(s['prior']['matrix']))[:3,3:])),prior_affine_offset_norm=float(np.linalg.norm(s['prior']['offset'])),main_update_wall_s=row['main_update_wall_s'],auxiliary_update_wall_s=row['auxiliary_update_wall_s'],frozen_emit_wall_s=row['update_wall_s'],estimated_virtual_finish_s=row['estimated_worker_finish_s'],estimated_virtual_queue_s=row['estimated_worker_queue_s'],timing_origin=meta['timing_origin'])
    for i,car in enumerate(('car1','car2')):
     p=None if not finite else row['pose'][3*i:3*i+3];true=truth['cars'][car];a3=None if p is None else ant(p,config['models'][car]);angles.append(None if p is None else wrap(p[2]-true['pose'][2]));ants.append(a3)
     d.update({car+'_base_x_m':p[0] if p is not None else None,car+'_base_y_m':p[1] if p is not None else None,car+'_yaw_rad':p[2] if p is not None else None,car+'_base_xy_error_m':math.dist(p[:2],true['pose'][:2]) if p is not None else None,car+'_antenna_x_m':float(a3[0]) if a3 is not None else None,car+'_antenna_y_m':float(a3[1]) if a3 is not None else None,car+'_antenna_xy_error_m':float(np.linalg.norm(a3[:2]-np.array(true['antenna_xyz_m'])[:2])) if a3 is not None else None,car+'_yaw_error_rad':angles[-1]})
    true_ant=[np.array(truth['cars'][c]['antenna_xyz_m']) for c in ('car1','car2')];true_distance=float(np.linalg.norm(true_ant[0]-true_ant[1]));d.update(true_distance_m=true_distance,estimated_distance_m=float(np.linalg.norm(ants[0]-ants[1])) if finite else None,relative_antenna_xy_error_m=float(np.linalg.norm((ants[0]-ants[1])[:2]-(true_ant[0]-true_ant[1])[:2])) if finite else None,distance_error_m=float(np.linalg.norm(ants[0]-ants[1]))-true_distance if finite else None,peer_measurement_truth_error_m=row['peer_median_m']-true_distance if row['peer_median_m'] is not None else None,auxiliary_prediction_truth_error_m=gate['auxiliary_prediction_m']-true_distance if gate['auxiliary_prediction_m'] is not None else None)
    d.pop('fault_wall_factor_ids');evaluated.append(d);allrows.append(d)
   series[(sc,seed,method)]=evaluated
   for scope in ('all_finite','joint_common_accepted'):
    scoped=in_scope(evaluated,common[(sc,seed)],scope)
    for period,predicate in PERIODS.items():
     part=[r for r in scoped if predicate(r['t_s'])];metrics.append(dict(scenario=sc,seed=seed,method=method,scope=scope,period=period,n=len(part),accepted_included=sum(r['accepted'] for r in part),**{k+'_rmse':rmse(part,k) for k in ERRORS}))
   if method=='G2':
    for period,predicate in PERIODS.items():
     part=[r for r in evaluated if predicate(r['t_s'])];available=[r for r in part if r['peer_available']];fault=[r for r in available if r['peer_fault_support_count']>0];healthy=[r for r in available if r['peer_fault_support_count']==0];statefault=[r for r in available if r['state_in_peer_fault']];known=[r for r in available if r['gate_state'] in ('accepted','rejected')]
     def ratio(n,d):return n/d if d else None
     nhr=sum(not r['peer_admitted'] for r in healthy);nkhr=sum(r['gate_state']=='rejected' for r in healthy);nleak=sum(r['peer_admitted'] for r in fault)
     gates.append(dict(scenario=sc,seed=seed,period=period,publications=len(part),available=len(available),missing=sum(r['gate_state']=='missing' for r in part),unknown=sum(r['gate_state']=='unknown' for r in part),known=len(known),admitted=sum(r['peer_admitted'] for r in part),known_rejected=sum(r['gate_state']=='rejected' for r in part),healthy_peer_available=len(healthy),healthy_rejected_total=nhr,healthy_unknown_rejected=sum(r['gate_state']=='unknown' for r in healthy),healthy_known_q_rejected=nkhr,healthy_total_rejection_ratio=ratio(nhr,len(healthy)),healthy_known_q_rejection_ratio_per_available=ratio(nkhr,len(healthy)),fault_raw_supported_available=len(fault),fault_raw_supported_admitted=nleak,fault_raw_supported_miss_ratio=ratio(nleak,len(fault)),fault_state_available=len(statefault),fault_state_admitted=sum(r['peer_admitted'] for r in statefault),fault_state_miss_ratio=ratio(sum(r['peer_admitted'] for r in statefault),len(statefault)),fully_fault_supported_available=sum(r['peer_fault_support_count']==r['peer_support_count'] for r in fault),fully_fault_supported_admitted=sum(r['peer_admitted'] and r['peer_fault_support_count']==r['peer_support_count'] for r in fault),mixed_boundary_fault_available=sum(r['peer_fault_support_count']<r['peer_support_count'] for r in fault),mixed_boundary_fault_admitted=sum(r['peer_admitted'] and r['peer_fault_support_count']<r['peer_support_count'] for r in fault),max_known_q=max([r['q'] for r in known],default=None)))
   costs.append(dict(scenario=sc,seed=seed,method=method,timing_origin=meta['timing_origin'],publications=len(rows),accepted=sum(r['accepted_graph'] for r in rows),startup=sum(r['status']=='predict_only_warmup' for r in rows),solver_or_marginal_failures=sum('failed' in r['status'] or 'error' in r['status'] for r in rows),missing_odom=sum(r['status']=='missing_odom_bracket' for r in rows),physical_peer_available=sum(r['peer_median_m'] is not None for r in rows),actual_peer_factors=sum(r['peer_factor_used'] for r in rows),main_wall_total_s=sum(r['main_update_wall_s'] for r in rows),auxiliary_wall_total_s=sum(r['auxiliary_update_wall_s'] for r in rows),emit_wall_total_s=sum(r['update_wall_s'] for r in rows),emit_wall_p95_s=float(np.percentile([r['update_wall_s'] for r in rows],95)),full_estimator_plus_original_IO_s=meta.get('original_runtime_s',meta['elapsed_with_current_IO_s']),current_export_or_replay_IO_s=meta['elapsed_with_current_IO_s'],peak_main_scalars=max(6*r['graph_states'] for r in rows),peak_auxiliary_scalars=max([6*r['auxiliary']['graph_states'] for r in rows if r['auxiliary'] is not None],default=0),virtual_timing_not_vehicle_latency=True))
 deltas=[]
 for (sc,seed,method),rs in series.items():
  for scope in ('all_finite','joint_common_accepted'):
   base=in_scope(rs,common[(sc,seed)],scope)
   for period,predicate in PERIODS.items():
    target=[r for r in base if predicate(r['t_s'])]
    comparators=[('versus_G0',series[(sc,seed,'G0')])]
    if method=='G2':comparators.append(('versus_G1',series[(sc,seed,'G1')]))
    if sc!='nominal':comparators.append(('fault_increment_versus_matched_nominal',series[('nominal',seed,method)]))
    for contrast,other in comparators:
     epochs={r['state_epoch_ns'] for r in other if r['finite_pair'] and (scope=='all_finite' or r['state_epoch_ns'] in common[(('nominal' if contrast=='fault_increment_versus_matched_nominal' else sc),seed)])};matched=[r for r in target if r['state_epoch_ns'] in epochs];at={r['state_epoch_ns'] for r in matched};control=[r for r in other if r['state_epoch_ns'] in at]
     deltas.append(dict(scenario=sc,seed=seed,method=method,scope=scope,period=period,contrast=contrast,n_matched=len(matched),**{k+'_delta_rmse':rmse(matched,k)-rmse(control,k) if matched else None for k in ERRORS}))
 csv_write(a.output/'metrics.csv',metrics);csv_write(a.output/'gate_counts.csv',gates);csv_write(a.output/'paired_deltas.csv',deltas);csv_write(a.output/'costs.csv',costs);csv_write(a.output/'timeline.csv',allrows);dump(a.output/'marginal_FD_checks.json',marginal)
 assert not {'probe','pinned','graph','frontend','legacy','scipy.optimize'}&set(sys.modules)
 receipt=dict(status='PASS',matrix_cells=45,unique_inputs=15,joint_publications=len(allrows),per_car_publications=2*len(allrows),shared_accepted_state_epochs=sum(len(v) for v in common.values()),checks=dict(checks),estimator_imports=[],source_sha256=sha(Path(__file__)),scope='same-host independent equations and artifact checks; exposed development seeds, not new independent validation')
 dump(a.output/'receipt.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
