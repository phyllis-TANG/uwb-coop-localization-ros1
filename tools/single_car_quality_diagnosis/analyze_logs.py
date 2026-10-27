#!/usr/bin/env python3
"""Read-only diagnosis from full frozen logs, raw inputs and paired nominal runs.
No online quality modules or optimizer are imported. Truth is offline evaluation.
"""
import argparse,csv,gzip,hashlib,json,math,statistics
from collections import defaultdict
from pathlib import Path
import numpy as np

SCENARIOS=('nominal','uwb_step','uwb_ramp','multi_common_uwb')
SEEDS=(401,419,443)
GROUPS=('Q0','Q1','Q2','Q3')
LINKS=('node_10','node_2','node_3','node_8')
def read(p):
 with gzip.open(p,'rt') as f:return [json.loads(s) for s in f if s.strip()]
def dump(p,obj):p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write_csv(p,rows):
 with p.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def wrap(a):return math.atan2(math.sin(a),math.cos(a))
def distance(pose,model,k):
 lx,ly=model['base_to_antenna_body_xy_m'];c,s=math.cos(pose[2]),math.sin(pose[2]);p=np.array([pose[0]+c*lx-s*ly,pose[1]+s*lx+c*ly,model['antenna_height_m']]);return float(np.linalg.norm(p-model['anchors_xyz_m'][k]))
def error(row,truth):
 return dict(xy_error_m=math.dist(row['pose'][:2],truth['pose'][:2]),yaw_error_rad=wrap(row['pose'][2]-truth['pose'][2]),bias_error_rad_s=(row.get('bias_rad_s') or 0)-truth['bias_rad_s'])
def load(root,scenario,seed,group):
 p=root/'runs'/f'{scenario}_seed{seed}__{group}';graphs=read(p/'graphs.jsonl.gz');pubs=read(p/'publications.jsonl.gz');led=read(p/'quality_ledger.jsonl.gz');avs=read(p/'availability.jsonl.gz')
 return dict(path=p,graphs={(g['state_epoch_ns'],g['role']):g for g in graphs},graph_ids={g['record_id']:g for g in graphs},pubs={r['state_epoch_ns']:r for r in pubs},ledger={(r['state_epoch_ns'],r['target']):r for r in led},avs={r['state_epoch_ns']:r for r in avs},config=json.loads((p/'config.json').read_text()))
def check_pair(root,sc,seed):
 ip=root/'inputs'/f'{sc}_seed{seed}';npth=root/'inputs'/f'nominal_seed{seed}';a=read(ip/'events.jsonl.gz');b=read(npth/'events.jsonl.gz');labels=json.loads((ip/'labels.json').read_text());origin=labels['origin_epoch_ns'];count=0;changed=0;max_residual=0.
 assert len(a)==len(b)
 for x,y in zip(a,b):
  for k in ('kind','record_index','header_epoch_ns','receive_epoch_ns','topic'):assert x[k]==y[k]
  if x['kind']!='uwb':assert x['value']==y['value'];continue
  assert x['value'].keys()==y['value'].keys()
  for k,v in x['value'].items():
   t=(x['header_epoch_ns']-origin)/1e9;bias=0.
   if 12<=t<32:
    if sc=='uwb_step' and k=='node_10':bias=.6
    if sc=='uwb_ramp' and k=='node_10':bias=.6*min((t-12)/12,1)
    if sc=='multi_common_uwb':bias=.3
   delta=v-y['value'][k];assert abs(delta-bias)<2e-15,(sc,seed,k,t,delta,bias)
   count+=1;changed+=bias!=0;max_residual=max(max_residual,abs(delta-bias))
 assert (ip/'truth.jsonl.gz').read_bytes()==(npth/'truth.jsonl.gz').read_bytes()
 return dict(scenario=sc,seed=seed,raw_records=len(a),uwb_scalars=count,changed_uwb_scalars=changed,nonfault_sensor_values_exact_equal=True,truth_bytes_exact_equal=True,max_injection_subtraction_error_m=max_residual)
def prior_stats(g,nominal):
 s=g['row']['objective_snapshot'];p=s['prior'];n=nominal['row']['objective_snapshot']['prior'];M=np.array(p['matrix']);N=np.array(n['matrix']);point=np.array(p['point']);npnt=np.array(n['point']);delta=npnt-point;delta[2]=wrap(delta[2]);r=M@delta+np.array(p['offset']);rn=np.array(n['offset']);H=M.T@M
 d=len(point);return dict(prior_digest=digest(p),nominal_prior_digest=digest(n),prior_H_delta_fro=float(np.linalg.norm(H-N.T@N)),prior_residual_at_nominal_boundary_norm=float(np.linalg.norm(r)),nominal_prior_residual_at_own_point_norm=float(np.linalg.norm(rn)),prior_gradient_at_nominal_x=float((M.T@r)[0]),prior_gradient_at_nominal_y=float((M.T@r)[1]),prior_gradient_at_nominal_yaw=float((M.T@r)[2]),prior_gradient_at_nominal_bias=float((M.T@r)[3]) if d==4 else None,prior_xy_yaw_cross_norm=float(np.linalg.norm(H[:2,2])),prior_xy_bias_cross_norm=float(np.linalg.norm(H[:2,3])) if d==4 else None,prior_yaw_bias_cross=float(H[2,3]) if d==4 else None)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--experiment',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output;out.mkdir(exist_ok=False);timelines=[];events=[];periods=[];prior_rows=[];pairchecks=[];details=[];raw_evidence=[];marginal_rows=[];checks=defaultdict(int)
 for seed in SEEDS:
  nominal={q:load(a.experiment,'nominal',seed,q) for q in GROUPS}
  for sc in SCENARIOS[1:]:
   pairchecks.append(check_pair(a.experiment,sc,seed));inp=a.experiment/'inputs'/f'{sc}_seed{seed}';labels=json.loads((inp/'labels.json').read_text());origin=labels['origin_epoch_ns'];truth={t['epoch_ns']:t for t in read(inp/'truth.jsonl.gz')};raw={e['record_index']:e for e in read(inp/'events.jsonl.gz')}
   for q in GROUPS:
    r=load(a.experiment,sc,seed,q);n=nominal[q];model=r['config']['base']['model'];frozen={};consumed=defaultdict(list);last={};chain_fault=defaultdict(set);series=[]
    for (epoch,role),g in r['graphs'].items():
     previous=last.get(role);assert g['previous_record_id']==previous;last[role]=g['record_id'];checks['graph_previous_id']+=1
     s=g['row']['objective_snapshot'];ng=n['graphs'][(epoch,role)];t=(epoch-origin)/1e9;assert g['availability_cutoff_epoch_ns']==epoch+10**9
     if role!='main':
      assert all(role not in o for o in s['observations']);assert all(all(v==1 for v in w.values()) for w in s['quality_weights']);checks['shadow_target_exclusion_and_unity']+=1
     for md in g['row'].get('marginalization_details',[]):
      lin=md['linearization_input'];old=lin['times_s'][0]+.01
      # Raw fault may straddle the bin at 12.01/32.01. Conservatively track any contributing injected sample.
      faults=[]
      md_ids=md.get('consumed_quality_factor_ids',[f'{q}|{origin+10_000_000+round(lin["times_s"][0]*1e9)}|{key}' for key in lin['observations'][0]])
      for fid in md_ids:
       assert fid not in consumed[role];consumed[role].append(fid)
       k=fid.split('|')[-1];ep=int(fid.split('|')[-2]);support=r['graphs'][(ep,role)]['support_new']['range_support'].get(k,[])
       affected=any(12<=(z['identity']['header_epoch_ns']-origin)/1e9<32 for z in support) and (sc=='multi_common_uwb' or k=='node_10')
       gain=lin.get('quality_weights',[{key:1. for key in lin['observations'][0]}])[0][k]
       if affected and gain>0:chain_fault[role].add(fid);faults.append(fid)
      if role=='main' or faults:
       marginal_rows.append(dict(scenario=sc,seed=seed,group=q,role=role,t_s=t,old_state_t_s=old,consumed=md_ids,fault_affected_positive_consumed=faults,cumulative_fault_affected_positive_prior=len(chain_fault[role]),prior_before=md.get('prior_before_digest',digest(lin['prior'])),prior_after=md.get('prior_after_digest',digest(md['prior_after']))))
     if role=='main':
      e=error(g['row'],truth[epoch]);ne=error(ng['row'],truth[epoch]);pr=prior_stats(g,ng);window_fault=0;window_down=0
      for ktime,o,w in zip(s['times_s'],s['observations'],s['quality_weights']):
       ep=origin+10_000_000+round(ktime*1e9)
       for k,v in o.items():
        deps=r['graphs'][(ep,role)]['support_new']['range_support'][k]
        affected=any(12<=(z['identity']['header_epoch_ns']-origin)/1e9<32 for z in deps) and (sc=='multi_common_uwb' or k=='node_10')
        window_fault+=affected and w[k]>0;window_down+=w[k]<1
      item=dict(scenario=sc,seed=seed,group=q,t_s=t,state_epoch_ns=epoch,cutoff_epoch_ns=g['availability_cutoff_epoch_ns'],available_epoch_ns=r['avs'][epoch]['available_receive_epoch_ns'],**e,nominal_xy_error_m=ne['xy_error_m'],nominal_yaw_error_rad=ne['yaw_error_rad'],nominal_bias_error_rad_s=ne['bias_error_rad_s'],x=g['row']['pose'][0],y=g['row']['pose'][1],yaw=g['row']['pose'][2],bias=g['row'].get('bias_rad_s',0),window_start_s=s['times_s'][0]+.01,window_fault_affected_positive_factors=window_fault,window_nonunit_factors=window_down,prior_fault_affected_positive_ancestors=len(chain_fault[role]),marginalizations=g['row']['marginalizations'],**pr)
      series.append(item);prior_rows.append(item)
    for (epoch,k),l in r['ledger'].items():
     t=(epoch-origin)/1e9;main=r['graphs'][(epoch,'main')];nom=n['ledger'][(epoch,k)];g=r['graph_ids'].get(l['reference_record_id']);ng=n['graph_ids'].get(nom['reference_record_id']);true_range=distance(truth[epoch]['pose'],model,k);me=l['corrected_aggregate_m']-true_range;prediction=None;pred_error=None;npred=None
     if g is not None:
      assert (g['state_epoch_ns'],g['availability_cutoff_epoch_ns'],g['role'])==(epoch,l['availability_cutoff_epoch_ns'],k);checks['same_state_cutoff_shadow']+=1
      prediction=distance(g['row']['pose'],model,k);pred_error=prediction-true_range;npred=distance(ng['row']['pose'],model,k)
      if l['engineering_score'] is not None:
       assert abs(abs(l['corrected_aggregate_m']-prediction)/.2-l['engineering_score'])<1e-12;checks['score_recomputed']+=1
     # Independently tie each raw scalar dependency back to original receive/header and reaggregate.
     rawvals=[]
     for dep in l['target_dependencies']:
      ident=dep['identity'];rr=raw[ident['record_index']];assert rr['receive_epoch_ns']==ident['receive_epoch_ns']<=l['availability_cutoff_epoch_ns'];assert rr['header_epoch_ns']==ident['header_epoch_ns'];assert rr['value'][k]==dep['raw_range_m'];rawvals.append(dep['raw_range_m']);checks['raw_dependency']+=1
     assert statistics.median(rawvals)==l['raw_aggregate_m']
     ss=main['row']['objective_snapshot'];assert ss['quality_weights'][-1][k]==l['actual_information_multiplier'];checks['actual_graph_gain']+=1
     for kt,ww in zip(ss.get('quality_factor_ids',[]),ss['quality_weights']):
      for target,fid in kt.items():
       if fid in frozen:assert frozen[fid]==ww[target]
       else:frozen[fid]=ww[target]
     p=l['policy'];m=error(main['row'],truth[epoch]);post=next(z for z in r['pubs'][epoch]['postfit_factor_diagnostics'] if z['factor_id']==l['factor_id'])
     tl=dict(scenario=sc,seed=seed,group=q,target=k,t_s=t,state_epoch_ns=epoch,cutoff_epoch_ns=l['availability_cutoff_epoch_ns'],available_epoch_ns=r['avs'][epoch]['available_receive_epoch_ns'],raw_median_m=l['raw_aggregate_m'],P1_m=l['P1_subtracted_m'],corrected_m=l['corrected_aggregate_m'],truth_range_m=true_range,measurement_error_m=me,excluded_prediction_m=prediction,excluded_prediction_error_m=pred_error,nominal_excluded_prediction_m=npred,nominal_score=nom['engineering_score'],signed_score_residual_m=l['raw_signed_consistency_residual_m'],score=l['engineering_score'],state=p['state'],gain=l['actual_information_multiplier'],reason=p['reason'],persistence=p.get('persistence'),reference_id=l['reference_record_id'],main_id=main['record_id'],other_links=l['reference_geometry']['other_links'] if l['reference_geometry'] else None,main_postfit_m=post['postfit_signed_raw_residual_m'],main_original_huber=post['original_pseudo_huber_residual'],main_weighted_huber=post['actual_weighted_residual'],**m)
     timelines.append(tl)
    if q in ('Q2','Q3'):
     rows=[z for z in timelines if (z['scenario'],z['seed'],z['group'])==(sc,seed,q)]
     for k in LINKS:
      if sc=='multi_common_uwb' or k=='node_10':continue
      lr=[z for z in rows if z['target']==k];start=None
      for i,z in enumerate(lr):
       if z['gain']<1 and start is None:start=i
       if start is not None and (z['gain']==1 or i==len(lr)-1):
        stop=i;part=lr[start:stop] if z['gain']==1 else lr[start:stop+1];on=lr[start];end=z if z['gain']==1 else None;id=f'{sc}_{seed}_{q}_{k}_{len(events)+1:02d}';trigger=lr[max(0,start-1):start+1]
        assert all(x['score']>=1.5 for x in trigger)
        ev=dict(event_id=id,scenario=sc,seed=seed,group=q,target=k,onset_s=on['t_s'],end_s=end['t_s'] if end else None,onset_available_s=(on['available_epoch_ns']-origin)/1e9,end_available_s=(end['available_epoch_ns']-origin)/1e9 if end else None,state_duration_s=end['t_s']-on['t_s'] if end else None,available_duration_s=(end['available_epoch_ns']-on['available_epoch_ns'])/1e9 if end else None,trigger_scores=[x['score'] for x in trigger],trigger_nominal_scores=[x['nominal_score'] for x in trigger],trigger_meas_errors_m=[x['measurement_error_m'] for x in trigger],trigger_shadow_errors_m=[x['excluded_prediction_error_m'] for x in trigger],max_score=max(x['score'] for x in part),max_measurement_error_m=max(abs(x['measurement_error_m']) for x in part),max_shadow_error_m=max(abs(x['excluded_prediction_error_m']) for x in part),disabled_frames=sum(x['gain']==0 for x in part),raw_fault_chain_in_reference=True,reference_excludes_healthy_only=k,main_fault_gain_at_onset=r['ledger'][(on['state_epoch_ns'],'node_10')]['actual_information_multiplier'],reference_fault_gain_at_onset=r['graphs'][(on['state_epoch_ns'],k)]['row']['objective_snapshot']['quality_weights'][-1]['node_10'])
        events.append(ev)
        detail=[]
        for z in lr[max(0,start-2):min(len(lr),stop+3)]:
         ep=z['state_epoch_ns'];ll=r['ledger'][(ep,k)];gg=r['graphs'][(ep,k)]
         detail.append(dict(timeline=z,ledger=ll,reference_graph=gg,main_graph=r['graphs'][(ep,'main')]))
        details.append(dict(event=ev,records=detail));start=None
    for name,lo,hi in [('full',0,60),('fault',12,32),('post_0_20',32,52),('post_gt20',52,60)]:
     xs=[s for s in series if lo<=s['t_s']<hi]
     row=dict(scenario=sc,seed=seed,group=q,period=name,n=len(xs))
     for field in ('xy_error_m','yaw_error_rad','bias_error_rad_s'):
      row[field+'_rmse']=float(np.sqrt(np.mean([s[field]**2 for s in xs])));row['nominal_'+field+'_rmse']=float(np.sqrt(np.mean([s['nominal_'+field]**2 for s in xs])))
     if q in ('Q0','Q2'):row['bias_error_rad_s_rmse']=row['nominal_bias_error_rad_s_rmse']=None
     row['max_prior_fault_ancestors']=max(s['prior_fault_affected_positive_ancestors'] for s in xs);row['max_window_fault_factors']=max(s['window_fault_affected_positive_factors'] for s in xs);periods.append(row)
    print(sc,seed,q,'done',flush=True)
 write_csv(out/'timeline.csv',timelines);write_csv(out/'healthy_events.csv',events);write_csv(out/'periods.csv',periods);write_csv(out/'main_history.csv',prior_rows);write_csv(out/'marginal_history.csv',marginal_rows);dump(out/'paired_input_checks.json',pairchecks);dump(out/'checks.json',dict(checks));dump(out/'healthy_events.json',events)
 with gzip.open(out/'event_full_evidence.json.gz','wt') as f:json.dump(details,f,sort_keys=True)
 assert len(events)==8 and sum(e['scenario']=='uwb_step' and e['group']=='Q2' for e in events)==2 and sum(e['scenario']=='uwb_step' and e['group']=='Q3' for e in events)==5 and sum(e['scenario']=='uwb_ramp' and e['group']=='Q3' for e in events)==1
 print(json.dumps(dict(status='PASS',healthy_episodes=len(events),checks=checks)))
if __name__=='__main__':main()
