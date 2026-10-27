#!/usr/bin/env python3
"""Pre-registered exposed-data attribution only; frozen-source main reconstruction
and prior-only snapshot substitutions. Never writes to original runs.
"""
import argparse,copy,json,sys
from pathlib import Path
import numpy as np
from analyze_logs import load,read,dump,write_csv,error,state_row,SEEDS,digest

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--experiment',type=Path,required=True);ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False)
 # Import the actual hash-verified frozen source, not the working tree implementation.
 sys.path.insert(0,str(a.experiment/'source/tools/single_car_quality_fgo'))
 from qgraph import WeightedImuGraph,WeightedImuObjective,WeightedPoseObjective
 from bridge import imu_graph,BoundaryPrior
 from scipy.optimize import least_squares
 rows=[];control=[];snapshots=[];jacchecks=[];fitted=[]
 for seed in SEEDS:
  run=load(a.experiment,'multi_common_uwb',seed,'Q3');origin=json.loads((a.experiment/'inputs'/f'multi_common_uwb_seed{seed}/labels.json').read_text())['origin_epoch_ns'];truth={z['epoch_ns']:z for z in read(a.experiment/'inputs'/f'multi_common_uwb_seed{seed}/truth.jsonl.gz')};graph_origin=origin+10_000_000
  for arm in ('original_gains_control','node2_post32_unity'):
   changed=[]
   def provider(ep,obs):
    weights={k:run['ledger'][(ep,k)]['actual_information_multiplier'] for k in obs}
    if arm=='node2_post32_unity' and (ep-origin)/1e9>=32:
     if weights['node_2']!=1:changed.append(ep)
     weights['node_2']=1.
    return dict(weights=weights,ids={k:f'Q3|{ep}|{k}' for k in obs})
   graph=WeightedImuGraph(run['config']['base'],provider=provider,role='Q3:main',origin=graph_origin)
   for ep,pub in run['pubs'].items():
    orig=pub['row'];s=orig['objective_snapshot'];new=graph.update(orig['state_time_s'],orig['local_odom'],s['observations'][-1],orig['angular_interval']);e=error(new,truth[ep]);diff=float(np.max(np.abs(np.array(new['objective_snapshot']['states'])-np.array(s['states']))))
    if arm=='original_gains_control':assert diff<1e-10,(seed,ep,diff)
    if arm=='node2_post32_unity' and ((ep-origin)/1e9<33 or seed!=419):assert diff<1e-10
    rows.append(dict(seed=seed,arm=arm,t_s=(ep-origin)/1e9,state_epoch_ns=ep,**e,x=new['pose'][0],y=new['pose'][1],yaw=new['pose'][2],bias=new['bias_rad_s'],max_window_state_delta_from_original=diff))
    fitted.append(dict(kind='D1',seed=seed,arm=arm,epoch=ep,result=new))
   control.append(dict(seed=seed,arm=arm,changed_state_epochs_ns=changed,changed_factors=len(changed),original_input_sha=json.loads((run['path']/'run.json').read_text())['input_sha256']))
 tasks=[('multi_common_uwb',seed,q,'main') for seed in SEEDS for q in ('Q1','Q3')]
 for ev in json.loads((a.analysis/'healthy_events.json').read_text()):tasks.append((ev['scenario'],ev['seed'],ev['group'],ev['target']))
 assert len(tasks)==14 and len(set(tasks))==14
 for sc,seed,q,role in tasks:
  run=load(a.experiment,sc,seed,q);nom=load(a.experiment,'nominal',seed,q);ep=max(run['pubs']);g=run['graphs'][(ep,role)];ng=nom['graphs'][(ep,role)];s=g['row']['objective_snapshot'];ns=ng['row']['objective_snapshot'];base=run['config']['base'];truth={z['epoch_ns']:z for z in read(a.experiment/'inputs'/f'{sc}_seed{seed}/truth.jsonl.gz')}[ep];x0=np.array(s['states']).ravel();d=len(s['states'][0]);sameobs=s['observations']==ns['observations'];sameweights=s['quality_weights']==ns['quality_weights'];intervals=[run['graphs'][(e,role)]['row']['angular_interval'] for e in s.get('interval_end_epochs_ns',[])]
  def objective(p):
   prior=(imu_graph.Prior if d==4 else BoundaryPrior)(p['point'],p['matrix'],p['offset'])
   if d==4:return WeightedImuObjective(s['times_s'],s['local_odom'],s['observations'],intervals,base['model'],prior,base,s['quality_weights'])
   return WeightedPoseObjective(s['times_s'],s['local_odom'],s['observations'],base['model'],prior,s['quality_weights'])
  pair=[]
  for name,p in [('original_prior_control',s['prior']),('nominal_prior_only',ns['prior'])]:
   obj=objective(p);res=least_squares(obj.fun,x0,jac=obj.jac,method='trf',tr_solver='exact',loss='linear',max_nfev=base['optimizer']['max_nfev'],ftol=1e-7,xtol=1e-7,gtol=1e-7);assert res.success
   state=res.x.reshape(-1,d)[-1];orig=np.array(g['row']['pose']+([g['row']['bias_rad_s']] if d==4 else []));nomstate=np.array(ng['row']['pose']+([ng['row']['bias_rad_s']] if d==4 else []));delta=float(np.max(np.abs(state-orig)));delta_nom=float(np.max(np.abs(state-nomstate)))
   if name=='original_prior_control':assert delta<2e-5,(sc,seed,q,role,delta)
   if name=='nominal_prior_only' and sameobs and sameweights:assert delta_nom<2e-5,(sc,seed,q,role,delta_nom)
   item=dict(scenario=sc,seed=seed,group=q,role=role,state_epoch_ns=ep,arm=name,current_observations_equal_nominal=sameobs,current_weights_equal_nominal=sameweights,prior_sha256=digest(p),current_factors_sha256=digest(dict(times=s['times_s'],local=s['local_odom'],observations=s['observations'],weights=s['quality_weights'],angular=[{k:i[k] for k in ('valid','dt_ns','raw_angle_rad')} for i in intervals])),bias=state_row(state)['bias_rad_s'],**error(state_row(state),truth),max_state_delta_original=delta,max_state_delta_nominal=delta_nom,cost=float(res.cost),optimality=float(res.optimality),nfev=res.nfev)
   snapshots.append(item);pair.append(item);fitted.append(dict(kind='D2',scenario=sc,seed=seed,group=q,role=role,arm=name,x=res.x.reshape(-1,d).tolist(),initial_states=s['states'],prior=p))
  # Analytic objective derivatives are checked independently by central differences.
  obj=objective(s['prior']);J=obj.jac(x0);worst=0.
  for col in sorted(set([0,1,2,d-1,len(x0)//2,len(x0)-d,len(x0)-2,len(x0)-1])):
   v=np.zeros_like(x0);v[col]=1e-6;fd=(obj.fun(x0+v)-obj.fun(x0-v))/2e-6;worst=max(worst,float(np.max(np.abs(fd-J[:,col]))))
  assert worst<2e-5; jacchecks.append(dict(scenario=sc,seed=seed,group=q,role=role,max_abs_jacobian_fd_error=worst))
 write_csv(a.output/'D1_series.csv',rows);write_csv(a.output/'D2_snapshots.csv',snapshots);dump(a.output/'D1_controls.json',control);dump(a.output/'jacobian_checks.json',jacchecks)
 import gzip
 with gzip.open(a.output/'full_intervention_results.json.gz','wt') as f:json.dump(fitted,f,sort_keys=True)
 dump(a.output/'receipt.json',dict(status='PASS',registration_commit='88a0e73',D1_main_reconstructions=6,D2_snapshot_solves=28,matrix_restarts=0,independent_validation=False,threshold_changes=0,original_evidence_modified=False))
 print('PASS: 6 main reconstructions; 28 snapshot solves; no matrix restart')
if __name__=='__main__':main()
