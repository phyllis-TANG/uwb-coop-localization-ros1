"""Two runs only. Exact saved prefix gate; unchanged frozen solver and policies."""
from extension import *
import gzip,csv,time,shutil,subprocess
from engine import IntegrityReplay,MonitoredGraph
from influence import Primitives
from run import compact
from evaluate import evaluate
from common import SPEC,write_json,csv_write,sha
from independent import verify_input_prefix

class ExtendedGraph(MonitoredGraph):
 def update(self,stamp,local,observations,peer):
  if stamp>=64 and len(self.primitives.keys)==len(Primitives().keys):
   new=[k for k in Primitives(range(1,90)).keys if k not in self.primitives.index]
   self.primitives.keys+=new;self.primitives.index={k:i for i,k in enumerate(self.primitives.keys)}
   for g in [self,*self.subsets.values()]:g.noise.prior_b=np.pad(g.noise.prior_b,((0,0),(0,len(new))))
  return super().update(stamp,local,observations,peer)

def check_saved(rows,condition,config):
 old=ROOT/f'docs/research/integrity_validation_20261030/units/5101_{condition}'
 scores=json.load(gzip.open(old/'scores.json.gz','rt')); assert len(scores)==63
 for r,o in zip(rows[:63],scores):
  assert r['state_time_s']==o['t'] and r['accepted_graph']==o['accepted']
  for k in ['ss','b0','b1','declarations']:
   if r['monitor'][k]!=o['monitor'][k]:raise AssertionError(f'PREFIX_OUTPUT_DIFFERENCE {condition} t={r["state_time_s"]} {k}')
 trajectory=list(csv.DictReader(gzip.open(old/'trajectory.csv.gz','rt')))
 for r in rows[:63]:
  for ci,car in enumerate(['car1','car2']):
   o=next(x for x in trajectory if x['car']==car and float(x['t_s'])==r['state_time_s'])
   assert r['pose'][3*ci:3*ci+3]==[float(o[k]) for k in ['base_x_m','base_y_m','yaw_rad']]
 if (old/'monitor.jsonl.gz').exists():
  previous=[json.loads(l) for l in gzip.open(old/'monitor.jsonl.gz','rt')]
  for r,o in zip(rows[:63],previous):
   for k in ['pose','accepted_graph','status','bins','main_snapshot_sha256','marginalizations','marginal_evidence']:
    assert compact(r)[k]==o[k],(r['state_time_s'],k)
 return dict(status='PASS_EXACT_SAVED_FIELDS',publications=63,numeric_tolerance=0,all_scores_and_declarations_exact=True,full_main_snapshot_hash_available=condition=='nominal',wall_long_limit='original full graph/prior not retained; all saved pose/status/scores/decisions checked')

def one(condition):
 size=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file());assert size<90_000_000 and shutil.disk_usage(OUT).free>500_000_000
 dest=OUT/condition;dest.mkdir(exist_ok=False)
 config,events,truth,receipt=extend(condition);write_json(dest/'INPUT.json',receipt);write_json(dest/'config.json',config)
 rows=[];sources={};active=[];audit=[];chosen={63.,72.,73.,80.,89.};worker=None
 def sink(row):
  t=row['state_time_s'];ns=row['availability_cutoff_epoch_ns'];origin=events[0]['receive_epoch_ns'];half=config['replay']['range_bin_half_width_s']
  sources[t]={}
  for car in simulate.CARS:
   selected=[e for e in events if e['kind']=='uwb' and e['vehicle_id']==car and e['receive_epoch_ns']<=ns and abs((e['header_epoch_ns']-origin)/1e9-t)<=half]
   for key in config['models'][car]['anchors_xyz_m']:
    v=[e for e in selected if key in e['value']];assert len(v)==row['bins'][car]['sample_counts'][key]
    if len(v)>=5:assert float(np.median([e['value'][key] for e in v]))==row['bins'][car]['observations'][key]
   sources[t][car]=dict(header_min_s=min((e['header_epoch_ns']-origin)/1e9 for e in selected),header_max_s=max((e['header_epoch_ns']-origin)/1e9 for e in selected),record_indices=[e['record_index'] for e in selected],fault_header_count=sum(24_000_000_000<=e['header_epoch_ns']-origin<52_000_000_000 for e in selected) if car=='car1' else 0)
  graphs={'main':worker.graph,**worker.graph.subsets}
  for role,g in graphs.items():
   fault_times=[u for u,obs in zip(g.times,g.observations) if obs['car1'] and sources[u]['car1']['fault_header_count']]
   active.append(dict(t_s=t,graph=role,window_start_s=g.times[0],window_end_s=g.times[-1],active_fault_bins=json.dumps(fault_times),active_fault_bin_count=len(fault_times),prior_fault_source_columns=sum(k.startswith('wall|car1|') and 24<=float(k.split('|')[2])<=52 for k in g.noise.record()['prior_noise_columns'])))
  if t in chosen:
   row['linear_evidence']={role:dict(snapshot=copy.deepcopy(g.snapshot()),prior_b=g.noise.prior_b.tolist(),k=g.noise.last_k.tolist()) for role,g in graphs.items()}
   audit.append(dict(t_s=t,primitive_keys=worker.graph.primitives.keys.copy(),graphs={role:dict(snapshot=copy.deepcopy(g.snapshot()),prior=g.prior.record(),primitive=g.noise.record(),factor_sources={str(u):sources[u] for u in g.times}) for role,g in graphs.items()}))
  rows.append(row)
 worker=IntegrityReplay(config,sink,events[0]['receive_epoch_ns']);worker.graph=ExtendedGraph(config)
 start=time.perf_counter()
 for e in events:worker.ingest(e)
 worker.finish();elapsed=time.perf_counter()-start
 with gzip.open(dest/'monitor.jsonl.gz','wt') as f:
  for r in rows:f.write(json.dumps(compact(r))+'\n')
 with gzip.open(dest/'audit.json.gz','wt') as f:json.dump(audit,f)
 csv_write(dest/'ACTIVE_SOURCES.csv',active)
 check=check_saved(rows,condition,config);write_json(dest/'PREFIX_OUTPUT_CHECK.json',check)
 write_json(dest/'BIN_CHECK.json',verify_input_prefix(rows,events,config))
 exit_time=min(x['t_s'] for x in active if x['graph']=='main' and x['t_s']>=52 and x['active_fault_bin_count']==0)
 SPEC['evaluation_intervals']={'all':[1,90],'pre':[1,24],'fault':[24,52],'post_fault_active':[52,exit_time],'post_exit':[exit_time,90]}
 evaluation=evaluate(condition,rows,truth,config)
 for name,table in evaluation.items():
  with gzip.open(dest/(name+'.csv.gz'),'wt') as f:
   w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
 write_json(dest/'RUN.json',dict(status='DONE',condition=condition,publications=len(rows),accepted=sum(r['accepted_graph'] for r in rows),actual_fault_bin_exit_s=exit_time,elapsed_s=elapsed,emit_wall_s=sum(r['total_monitored_emit_wall_s'] for r in rows),max_virtual_delay_s=max(r['monitor_available_time_virtual_s']-r['state_time_s'] for r in rows),actual_timing='offline per-publication perf_counter duration; virtual queue time is not wall-clock vehicle availability',commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()))
 print(condition,'DONE',elapsed,exit_time,flush=True)
if __name__=='__main__':
 assert json.loads((OUT/'PREFIX_CHECK.json').read_text())['status']=='PASS'
 for condition in ['nominal','wall_long']:
  try:one(condition)
  except Exception as e:
   write_json(OUT/f'FAILED_{condition}.json',dict(error=str(e),status='REPRODUCTION_FAILED_DO_NOT_INTERPRET_EXTENSION'));raise
