#!/usr/bin/env python3
"""Task A: read stored states only; no estimator, optimizer or control policy."""
import argparse,copy,importlib.util,json,sys,math
from pathlib import Path
from collections import Counter
import numpy as np
from io_evidence import *
from signals import antenna,wrap,body_delta,finite,construct_local,CARS
PERIODS={'all':lambda t:True,'pre':lambda t:3<=t<24,'fault':lambda t:24<=t<38,'recovery':lambda t:38<=t<48,'late':lambda t:48<=t<=63,'recovery_0_20':lambda t:38<=t<58,'recovery_20plus':lambda t:58<=t<=63}
def rms(v):return float(np.sqrt(np.mean(np.square(v)))) if len(v) else None

def extract(evidence,out):
 out.mkdir(exist_ok=False);receipt=json.loads((evidence/'ARCHIVE_CHECK.json').read_text());assert receipt['status']=='PASS';root=Path(receipt['matrix_root']);index=json.loads((root/'RUN_INDEX.json').read_text());public=evidence/'public_snapshot'
 path=root/'source/tools/two_car_fixed_lag_fgo_v1/audit.py';assert sha(path)==index['source_sha256']['tools/two_car_fixed_lag_fgo_v1/audit.py']
 spec=importlib.util.spec_from_file_location('stored_scalar_equations',path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
 allruns={};configs={};truths={};events={};signals=[];local={} ;identities=[]
 for scenario in SCENARIOS:
  case=scenario+'_seed101';inp=root/'inputs'/case;configs[scenario]=json.loads((inp/'config.json').read_text());truths[scenario]={x['state_epoch_ns']:x for x in read(inp/'truth.jsonl')};events[scenario]=read(inp/'events.jsonl.gz')
  for cell in [c for c in index['cells'] if c['case']==case]:
   run=root/cell['path'];rows=read(run/'updates.jsonl.gz');assert len(rows)==63;allruns[scenario,cell['method']]=rows;identities.append(dict(scenario=scenario,method=cell['method'],path=str(run),updates_sha256=sha(run/'updates.jsonl.gz'),run_sha256=sha(run/'run.json'),inputs_sha256=cell['input_sha256']))
  streams={car:[] for car in CARS};seen=set()
  for e in events[scenario]:
   if e['kind']=='uwb' and e.get('representation')=='bridge':
    key=(e['vehicle_id'],e['source_observation_id'])
    if key not in seen:streams[e['vehicle_id']].append(e);seen.add(key)
  origin=events[scenario][0]['receive_epoch_ns'];c=configs[scenario]
  for row in allruns[scenario,'I']:
   assert row['state_epoch_ns']==origin+round(row['state_time_s']*1e9) and row['availability_cutoff_epoch_ns']==row['state_epoch_ns']+10**9
   ss=construct_local(row,c,streams,origin,audit)
   for v in ss:v['scenario']=scenario;signals.append(v);local[scenario,row['state_epoch_ns'],v['car']]=v
  print('LOCAL_SIGNALS',scenario,'63 epochs PASS',flush=True)
 # Signals are complete before the following truth/label joins. No control decision.
 csvwrite(out/'local_signals.csv',signals)
 diag=[];metric_values={};modes=Counter()
 for (scenario,method),rows in allruns.items():
  c=configs[scenario];metric_values[scenario,method]={};refrows=allruns[scenario,'I'];previous=None;previous_rates={};origin=events[scenario][0]['receive_epoch_ns'];rawstreams=audit.input_streams(copy.deepcopy(events[scenario]))
  for row,ref in zip(rows,refrows):
   ep=row['state_epoch_ns'];t=row['state_time_s'];assert ep==ref['state_epoch_ns'] and row['availability_cutoff_epoch_ns']==ref['availability_cutoff_epoch_ns']
   p=row['pose'];mp=row.get('main_pose',p);known=bool(ref['accepted_graph'] and finite(ref['pose']));mode=row.get('publication_mode',('independent' if method=='I' else 'normal_joint') if row['accepted_graph'] else 'unknown')
   main_success=row.get('main_accepted_graph',row['accepted_graph']);joint=row.get('joint_optimization_success',bool(method=='J' and row['accepted_graph']))
   vals=dict(t_s=t,finite=finite(p),reference_accepted=known,mode=mode,joint_success=joint,main_accepted=main_success,status=row.get('main_status',row['status']),reason=row.get('publication_reason','BASELINE_ACCEPTED' if row['accepted_graph'] else 'STARTUP'))
   ants=[antenna(p[3*i:3*i+3],c['models'][car]) for i,car in enumerate(CARS)] if finite(p) else None
   truths=[np.array(truths[scenario][ep]['cars'][car]['antenna_xyz_m']) for car in CARS]
   peer_residual=None if ants is None or row['peer_median_m'] is None else float(np.linalg.norm(ants[0]-ants[1])-row['peer_median_m'])
   relative=None if ants is None else ants[0]-ants[1]
   vals['relative_xy_rmse_m']=None if ants is None else float(np.linalg.norm(relative[:2]-(truths[0]-truths[1])[:2]));vals['distance_rmse_m']=None if ants is None else float(np.linalg.norm(relative)-np.linalg.norm(truths[0]-truths[1]))
   if method in METHODS:audit.check_bins(row,c,rawstreams,origin)
   for i,car in enumerate(CARS):
    tr=truths[scenario][ep]['cars'][car];pos=p[3*i:3*i+3] if finite(p) else None;re=antenna(ref['pose'][3*i:3*i+3],c['models'][car]);err=None if pos is None else float(np.linalg.norm(ants[i][:2]-truths[i][:2]));referr=float(np.linalg.norm(re[:2]-truths[i][:2]));sep=None if pos is None else float(np.linalg.norm(ants[i][:2]-re[:2]))
    val=dict(antenna_xy_rmse_m=err,base_xy_rmse_m=None if pos is None else float(np.linalg.norm(np.array(pos[:2])-tr['pose'][:2])),yaw_rmse_rad=None if pos is None else wrap(pos[2]-tr['pose'][2]),mean_help_m=None if err is None else max(referr-err,0.),mean_harm_m=None if err is None else max(err-referr,0.),max_separation_m=sep,max_excess004_m=None if sep is None else max(0.,sep-.04),max_excess100_m=None if sep is None else max(0.,sep-1.))
    vals[car]=val
    if method not in METHODS:continue
    v=dict(scenario=scenario,method=method,car=car,t_s=t,state_epoch_ns=ep,cutoff_epoch_ns=row['availability_cutoff_epoch_ns'],finite=finite(p),reference_accepted=known,publication_mode=mode,reason=vals['reason'],main_success=main_success,joint_success=joint,
     antenna_x_m=None if pos is None else float(ants[i][0]),antenna_y_m=None if pos is None else float(ants[i][1]),yaw_rad=None if pos is None else pos[2],true_error_xy_m=err,true_error_yaw_rad=val['yaw_rmse_rad'],separation_from_I_m=sep,
     peer_residual_published_m=peer_residual,relative_x_m=None if relative is None else float(relative[0]),relative_y_m=None if relative is None else float(relative[1]),antenna_distance_m=None if relative is None else float(np.linalg.norm(relative)),
     relative_xy_error_m=vals['relative_xy_rmse_m'],distance_error_m=vals['distance_rmse_m'],main_to_publish_xy_m=None,main_to_publish_yaw_rad=None,peer_residual_main_m=None,
     sample_dt_s=None,reference_pair_valid=False,reference_triplet_valid=False,publish_step_xy_m=None,publish_secant_speed_mps=None,publish_secant_vx_mps=None,publish_secant_vy_mps=None,publish_rate_change_mps2=None,publish_yaw_step_rad=None,publish_secant_yaw_rate_radps=None,
     main_step_xy_m=None,clip_offset_change_m=None,published_odom_body_conflict_m=None,internal_odom_body_conflict_m=None,window_previous_vs_previous_publication_xy_m=None,
     prior_peer_n=len(row['provenance']['prior_peer_factor_ids']),window_peer_n=len(row['provenance']['window_peer_factor_ids']),window_start_s=row['snapshot']['times_s'][0],prior_cross_norm=float(np.linalg.norm((np.array(row['snapshot']['prior']['matrix']).T@np.array(row['snapshot']['prior']['matrix']))[:3,3:])))
    if pos is not None and finite(mp):
     ma=[antenna(mp[3*j:3*j+3],c['models'][cc]) for j,cc in enumerate(CARS)];v['main_to_publish_xy_m']=float(np.linalg.norm(ants[i][:2]-ma[i][:2]));v['main_to_publish_yaw_rad']=wrap(pos[2]-mp[3*i+2]);v['peer_residual_main_m']=float(np.linalg.norm(ma[0]-ma[1])-row['peer_median_m']) if row['peer_median_m'] is not None else None
    if previous is not None and finite(previous['pose']) and pos is not None:
     dt=(ep-previous['state_epoch_ns'])/1e9;assert dt>0;old=previous['pose'][3*i:3*i+3];aprev=antenna(old,c['models'][car]);step=ants[i][:2]-aprev[:2];vel=step/dt;dth=wrap(pos[2]-old[2]);prior_ref=refrows[int(t)-2]
     v.update(sample_dt_s=dt,reference_pair_valid=bool(known and prior_ref['accepted_graph']),reference_triplet_valid=bool(t>=3 and known and prior_ref['accepted_graph'] and refrows[int(t)-3]['accepted_graph']),publish_step_xy_m=float(np.linalg.norm(step)),publish_secant_speed_mps=float(np.linalg.norm(vel)),publish_secant_vx_mps=float(vel[0]),publish_secant_vy_mps=float(vel[1]),publish_yaw_step_rad=dth,publish_secant_yaw_rate_radps=dth/dt)
     if car in previous_rates:v['publish_rate_change_mps2']=float(np.linalg.norm(vel-previous_rates[car])/dt)
     previous_rates[car]=vel
     oldmp=previous.get('main_pose',previous['pose']);oldma=antenna(oldmp[3*i:3*i+3],c['models'][car]);v['main_step_xy_m']=float(np.linalg.norm(ma[i][:2]-oldma[:2]));v['clip_offset_change_m']=float(np.linalg.norm((ants[i][:2]-ma[i][:2])-(aprev[:2]-oldma[:2])))
     oldodom=previous['bins'][car]['local_odom'];odom=row['bins'][car]['local_odom']
     if oldodom is not None and odom is not None:v['published_odom_body_conflict_m']=float(np.linalg.norm(body_delta(old,pos)-body_delta(oldodom,odom)))
     s=row['snapshot']
     if len(s['times_s'])>1 and s['times_s'][-2]==previous['state_time_s']:
      oldstate=s['states'][-2][3*i:3*i+3];state=s['states'][-1][3*i:3*i+3];v['window_previous_vs_previous_publication_xy_m']=float(np.linalg.norm(antenna(oldstate,c['models'][car])[:2]-aprev[:2]));v['internal_odom_body_conflict_m']=float(np.linalg.norm(body_delta(oldstate,state)-body_delta(s['local'][-2][i],s['local'][-1][i])))
    for k,z in local[scenario,ep,car].items():
     if k not in ['scenario','car','t_s','state_epoch_ns','cutoff_epoch_ns','reference_accepted']:v['local_'+k]=z
    diag.append(v)
   metric_values[scenario,method][ep]=vals;modes[scenario,method,mode]+=1;previous=row
 # Independently recompute original metrics and contrasts for ALL 16 cells.
 checks=[];maxerr=0.;fields=['antenna_xy_rmse_m','base_xy_rmse_m','yaw_rmse_rad','mean_help_m','mean_harm_m','max_separation_m','max_excess004_m','max_excess100_m','relative_xy_rmse_m','distance_rmse_m']
 for old in table(public/'results/metrics.csv'):
  values=metric_values[old['scenario'],old['method']];pred=PERIODS[old['period']];total=[v for v in values.values() if pred(v['t_s'])];selected=[v for v in total if v['finite'] and (old['scope']=='all_finite' or v['reference_accepted'])];car=old['car'];assert len(total)==int(old['denominator']) and len(selected)==int(old['n'])
  for field in fields:
   vv=[v[field] if field in ['relative_xy_rmse_m','distance_rmse_m'] else v[car][field] for v in selected]
   actual=float(np.mean(vv)) if field.startswith('mean_') else max(vv) if field.startswith('max_') else rms(vv)
   error=abs(actual-float(old[field]));maxerr=max(maxerr,error);assert error<1e-12,(old,field,actual)
  for field,actual in [('help_n',sum(v[car]['mean_help_m']>1e-9 for v in selected)),('harm_n',sum(v[car]['mean_harm_m']>1e-9 for v in selected)),('excess004_n',sum(v[car]['max_excess004_m']>1e-7 for v in selected)),('excess100_n',sum(v[car]['max_excess100_m']>1e-7 for v in selected)),('fallback',sum(v['mode']=='reference_fallback' for v in total)),('unknown',sum(v['mode']=='unknown' for v in total)),('post_clip',sum(v['mode']=='post_clip' for v in total)),('joint_success',sum(v['joint_success'] for v in total))]:assert actual==int(old[field])
  checks.append(old['scenario']+':'+old['method'])
 for old in table(public/'results/contrasts.csv'):
  s,m=old['scenario'],old['method'];vs=metric_values[s,m];other=metric_values[s,'I'] if old['contrast']=='same_input_vs_I' else metric_values['nominal',m]
  chosen=[(v,other[ep]) for ep,v in vs.items() if PERIODS[old['period']](v['t_s']) and v['finite'] and other[ep]['finite'] and (old['scope']=='all_finite' or v['reference_accepted'] and other[ep]['reference_accepted'])];assert len(chosen)==int(old['n']);car=old['car']
  a=rms([v[car]['antenna_xy_rmse_m'] for v,w in chosen]);b=rms([w[car]['antenna_xy_rmse_m'] for v,w in chosen]);assert abs(a-b-float(old['delta_rmse_m']))<1e-12
 for old in table(public/'results/costs.csv'):
  vs=list(metric_values[old['scenario'],old['method']].values());assert len(vs)==int(old['denominator'])
  for key,value in [('finite',sum(v['finite'] for v in vs)),('reference_accepted',sum(v['reference_accepted'] for v in vs)),('joint_success',sum(v['joint_success'] for v in vs)),('normal_joint',sum(v['mode']=='normal_joint' for v in vs)),('post_clip',sum(v['mode']=='post_clip' for v in vs)),('fallback',sum(v['mode']=='reference_fallback' for v in vs)),('unknown',sum(v['mode']=='unknown' for v in vs)),('timeout',sum(v['reason']=='TIMEOUT' for v in vs)),('failure',sum('failed' in v['status'] or 'error' in v['status'] for v in vs))]:assert value==int(old[key]),(old,key,value)
 # Solver-controls are source identity checked in prepare; recompute all 12 too.
 for old in table(public/'results/solver_controls.csv'):
  a,b=old['comparison'].split('_');c=configs[old['scenario']];i=0 if old['car']=='car1' else 1
  ds=[float(np.linalg.norm(antenna(x['pose'][3*i:3*i+3],c['models'][old['car']])[:2]-antenna(y['pose'][3*i:3*i+3],c['models'][old['car']])[:2])) for x,y in zip(allruns[old['scenario'],a][2:],allruns[old['scenario'],b][2:])]
  assert len(ds)==int(old['n']) and abs(max(ds)-float(old['max_antenna_difference_m']))<1e-12 and abs(rms(ds)-float(old['rms_antenna_difference_m']))<1e-12
 csvwrite(out/'diagnostics.csv',diag)
 # Independent evaluation join only after local construction; explicit diagnostic label.
 joined=[]
 for sig in signals:
  tr=truths[sig['scenario']][sig['state_epoch_ns']]['cars'][sig['car']];i=0 if sig['car']=='car1' else 1;p=allruns[sig['scenario'],'I'][int(sig['t_s'])-1]['pose'];err=float(np.linalg.norm(antenna(p[3*i:3*i+3],configs[sig['scenario']]['models'][sig['car']])[:2]-tr['antenna_xyz_m'][:2]))
  joined.append(dict(sig,offline_true_error_xy_m=err,offline_injected_local_wall=bool(sig['scenario']!='nominal' and sig['car']=='car1' and 24<=sig['t_s']<38)))
 csvwrite(out/'local_signals_offline_join.csv',joined)
 summary=[];keys=['true_error_xy_m','true_error_yaw_rad','publish_step_xy_m','publish_secant_speed_mps','publish_rate_change_mps2','publish_yaw_step_rad','published_odom_body_conflict_m','internal_odom_body_conflict_m','main_to_publish_xy_m','main_to_publish_yaw_rad','peer_residual_published_m','clip_offset_change_m','window_previous_vs_previous_publication_xy_m']
 for s in SCENARIOS:
  for m in METHODS:
   for car in CARS:
    for per,pred in PERIODS.items():
     total=[v for v in diag if v['scenario']==s and v['method']==m and v['car']==car and pred(v['t_s'])]
     for scope in ['all_recorded','reference_pair_valid']:
      vv=total if scope=='all_recorded' else [v for v in total if v['reference_pair_valid']]
      for key in keys:
       data=[v[key] for v in vv if v[key] is not None and (scope=='all_recorded' or key!='publish_rate_change_mps2' or v['reference_triplet_valid'])];summary.append(dict(scenario=s,method=m,car=car,period=per,scope=scope,metric=key,denominator=len(total),n=len(data),mean=None if not data else float(np.mean(data)),rms=rms(data),max_abs=max(map(abs,data),default=None)))
 csvwrite(out/'summary.csv',summary)
 assert not {'graph','core','frontend','probe','replay_control','scipy.optimize'}&set(sys.modules)
 dump(out/'EXTRACTION_CHECK.json',dict(status='PASS',fixed_HEAD=HEAD,execution_commit=EXEC,original_metrics_rows_recomputed=len(checks),original_contrasts_rows_recomputed=len(table(public/'results/contrasts.csv')),original_solver_controls_recomputed=12,max_original_metric_abs_difference=maxerr,original_cost_state_counts_checked=16,cost_wall_numbers='identity checked only; no rerun timing',diagnostics_rows=len(diag),local_rows=len(signals),GN_proxy_computations=sum(s['GN_status']=='nominal_GN_proxy_not_published_covariance' for s in signals),known_signal_limitations='posterior local linearization, engineering noise; not published covariance or truth guarantee',source_reader_sha256=sha(Path(__file__)),signal_source_sha256=sha(Path(__file__).with_name('signals.py')),shared_scalar_audit_sha256=sha(path),estimator_runs=0,source_runs=identities))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();extract(a.evidence,a.output)
