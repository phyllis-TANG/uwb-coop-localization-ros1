#!/usr/bin/env python3
"""Four preregistered static Jacobian/residual checks, no iterative fitting."""
import argparse,gzip,itertools,json,sys
from pathlib import Path
import numpy as np
from common import *
TIMES=(23,24,37,54)
DEFAULT=Path('/home/ubuntu22/uwb-cooperative-a-evidence-20261029-artifacts/evidence-v1')
def rows(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else p.open()) as f:return [json.loads(x) for x in f if x.strip()]
def antenna(p,model):
 l=np.array(model['base_to_antenna_body_xy_m']);c,s=np.cos(p[2]),np.sin(p[2]);return np.r_[np.array(p[:2])+np.array([[c,-s],[s,c]])@l,model['antenna_height_m']]
def range_jacobian(p,anchors):
 delta=p-anchors;distance=np.linalg.norm(delta,axis=1);return distance,delta/distance[:,None]
def describe(J,residual):
 u,s,v=np.linalg.svd(J,full_matrices=True);tol=max(J.shape)*np.finfo(float).eps*s[0];rank=int(sum(s>tol))
 step=np.linalg.lstsq(J,residual,rcond=None)[0];left=residual-J@step
 return dict(shape=list(J.shape),rank=rank,nullity=J.shape[1]-rank,residual_dof=J.shape[0]-rank,
             singular_values=s.tolist(),condition_nonzero=float(s[0]/s[rank-1]),full_column_rank=rank==J.shape[1],
             tangent_projected_residual_rms_m=float(np.sqrt(np.mean(left**2))),tangent_step=step.tolist(),
             interpretation='one linear projection at saved I state; not a new location fit, model selection, alarm or confidence bound')
def run(evidence,out):
 out.mkdir(exist_ok=False);src=Sources()
 receipt=src.json('docs/research/cooperative_followup_20261029/a_evidence/checks/ARCHIVE_CHECK.json',REFS['pr75'])
 ar=evidence/'cooperative_influence_probe_20261028_v1.tar.gz';assert ar.stat().st_size==54249275 and sha(ar)==receipt['sha256']
 root=evidence/'unpacked/cooperative_influence_probe_20261028/evidence-v1';index=json.loads((root/'RUN_INDEX.json').read_text());case='car1_common_wall_bias_seed101';cell=next(c for c in index['cells'] if c['case']==case and c['method']=='I');inp=root/'inputs'/case
 for name,h in cell['input_sha256'].items():assert sha(inp/name)==h
 runpath=root/cell['path'];metadata=json.loads((runpath/'run.json').read_text());assert sha(runpath/'run.json')==cell['run_sha256']
 for item in metadata['outputs']:assert sha(runpath/item['path'])==item['sha256']
 updates=rows(runpath/'updates.jsonl.gz');events=rows(inp/'events.jsonl.gz');config=json.loads((inp/'config.json').read_text());model=config['models']['car1'];keys=sorted(model['anchors_xyz_m']);anchors=np.array([model['anchors_xyz_m'][k] for k in keys]);origin=events[0]['receive_epoch_ns']
 geometry=src.json(DOC+'geometry.json');assert model['antenna_height_m']==geometry['mounts']['car1']['antenna_reference_height_m']
 assert model['anchors_xyz_m']==geometry['anchors']['xyz_m']
 selected=[x for x in updates if x['state_time_s'] in TIMES];assert len(selected)==4
 result=[];ranges=[];compact=[];supports=[]
 for row in selected:
  assert row['accepted_graph'] and not row['snapshot']['peer_enabled'];assert not row['provenance']['prior_peer_factor_ids']
  t=row['state_time_s'];ep=row['state_epoch_ns'];cut=row['availability_cutoff_epoch_ns'];assert cut-ep==10**9
  raw=[e for e in events if e['kind']=='uwb' and e['vehicle_id']=='car1' and e['representation']=='bridge' and e['receive_epoch_ns']<=cut and abs((e['header_epoch_ns']-origin)/1e9-t)<=config['replay']['range_bin_half_width_s']]
  assert len({e['source_observation_id'] for e in raw})==len(raw)
  p=antenna(row['pose'][:3],model);distance,G3=range_jacobian(p,anchors);G=G3[:,:2]
  z=[]
  for k in keys:
   samples=[e['value'][k] for e in raw if k in e['value'] and e['value'][k]>0];med=float(np.median(samples));assert med==row['bins']['car1']['observations'][k];z.append(med-model['range_bias_m'][k])
  residual=np.array(z)-distance
  matrices={'H0_XY':G,'H2_XY_common':np.column_stack([G,np.ones(4)]),'H3_XY_arbitrary':np.column_stack([G,np.eye(4)]),'H0_unknown_height':G3,'H2_unknown_height':np.column_stack([G3,np.ones(4)])}
  for k in range(4):matrices['H1_fault_'+keys[k]]=np.column_stack([G,np.eye(4)[:,k]])
  hypotheses={k:describe(J,residual) for k,J in matrices.items()}
  pair_ranks={','.join(keys[i] for i in pair):describe(G[list(pair)],residual[list(pair)]) for pair in itertools.combinations(range(4),2)}
  for j,k in enumerate(keys):ranges.append(dict(t_s=t,state_epoch_ns=ep,cutoff_epoch_ns=cut,car='car1',anchor=k,antenna_x_m=p[0],antenna_y_m=p[1],antenna_z_m=p[2],raw_bin_m=row['bins']['car1']['observations'][k],frozen_bias_m=model['range_bias_m'][k],corrected_range_m=z[j],predicted_slant_m=distance[j],observed_minus_predicted_m=residual[j],J_x=G3[j,0],J_y=G3[j,1],J_z=G3[j,2]))
  for e in raw:supports.append(dict(t_s=t,record_index=e['record_index'],source_observation_id=e['source_observation_id'],header_epoch_ns=e['header_epoch_ns'],receive_epoch_ns=e['receive_epoch_ns']))
  result.append(dict(t_s=t,state_epoch_ns=ep,cutoff_epoch_ns=cut,point_source='saved peer-free I antenna, no truth',antenna_xyz_m=p.tolist(),anchors_xyz_m=anchors.tolist(),anchor_order=keys,Gxyz=G3.tolist(),raw_residual_m=residual.tolist(),hypotheses=hypotheses,healthy_pair_checks=pair_ranks,reference_prior_peer_n=0,window_start_s=row['snapshot']['times_s'][0],prior_id=row['provenance']['current_prior_id']))
  compact.append(dict(t_s=t,raw_residual_rms_m=float(np.sqrt(np.mean(residual**2))),H0_rank=hypotheses['H0_XY']['rank'],H2_rank=hypotheses['H2_XY_common']['rank'],H2_condition=hypotheses['H2_XY_common']['condition_nonzero'],H2_tangent_bias_m=hypotheses['H2_XY_common']['tangent_step'][-1],H2_tangent_residual_rms_m=hypotheses['H2_XY_common']['tangent_projected_residual_rms_m'],H0_unknown_height_rank=hypotheses['H0_unknown_height']['rank'],H2_unknown_height_rank=hypotheses['H2_unknown_height']['rank'],H2_unknown_height_condition=hypotheses['H2_unknown_height']['condition_nonzero'],H3_nullity=hypotheses['H3_XY_arbitrary']['nullity'],min_healthy_pair_singular_value=min(x['singular_values'][-1] for x in pair_ranks.values())))
 # Truth appears only after all local matrices/projections have been computed.
 truth={x['state_epoch_ns']:x for x in rows(inp/'truth.jsonl')}
 for x,c in zip(result,compact):
  gt=np.array(truth[x['state_epoch_ns']]['cars']['car1']['antenna_xyz_m']);c['offline_I_true_error_xy_m']=float(np.linalg.norm(np.array(x['antenna_xyz_m'])[:2]-gt[:2]))
 csvwrite(out/'four_snapshots.csv',compact);csvwrite(out/'raw_four_ranges.csv',ranges);csvwrite(out/'support_records.csv',supports);dump(out/'static_matrices.json',result)
 assert not any(k in sys.modules for k in ['graph','frontend','core','scipy.optimize'])
 dump(out/'run.json',dict(status='DONE',estimator_runs=0,real_bags_read=0,seed=101,times=list(TIMES),car='car1',archive_sha256=sha(ar),input_sha256=cell['input_sha256'],saved_updates_sha256=sha(runpath/'updates.jsonl.gz'),original_execution_commit=index['commit'],source_sha256={p.name:sha(p) for p in Path(__file__).parent.glob('*.py')},fixed_sources=src.items,outputs={p.name:sha(p) for p in out.iterdir() if p.is_file()},rank_tolerance='max(shape)*machine_epsilon*s_max, algebra only, not detection threshold',limitations=['linear projection only','no iterative solve','no calibrated noise bound','geometry/height engineering source, uncertainty unknown']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,default=DEFAULT);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.evidence,a.output)
