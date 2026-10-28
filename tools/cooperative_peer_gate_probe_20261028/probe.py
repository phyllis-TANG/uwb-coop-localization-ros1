"""Ordinary excluded-peer prediction gate; no trust policy or history rollback."""
import copy,hashlib,json,math,time
import numpy as np
from pinned import frontend,graph,legacy,replay
GATE_Q=3.0
METHODS=('G0','G1','G2')

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def antenna_pair(pose,config):
 return [np.r_[legacy.antenna(pose[3*i:3*i+3],config['models'][car]['base_to_antenna_body_xy_m']),config['models'][car]['antenna_height_m']].tolist() for i,car in enumerate(legacy.CARS)]

def decision(measured,auxiliary,config,test_mode=None):
 prediction=None;q=None;reason=None
 if measured is None:state='missing';admit=False;reason='NO_AGGREGATED_PEER'
 elif not auxiliary['accepted_graph']:state='unknown';admit=False;reason='AUXILIARY_NOT_ACCEPTED'
 elif auxiliary['pose'] is None or not np.isfinite(auxiliary['pose']).all():state='unknown';admit=False;reason='AUXILIARY_POSE_UNAVAILABLE'
 else:
  points=antenna_pair(auxiliary['pose'],config);prediction=float(np.linalg.norm(np.array(points[0])-points[1]));q=abs(measured-prediction)/config['peer']['sigma_m'];admit=q<=GATE_Q;state='accepted' if admit else 'rejected';reason='Q_LE_3' if admit else 'Q_GT_3'
 if test_mode is not None:
  if test_mode not in ('allow_all','reject_all'):raise ValueError('Unsupported contract-test mode')
  admit=measured is not None and test_mode=='allow_all';state='missing' if measured is None else 'test_accept' if admit else 'test_reject';reason='CONTRACT_TEST_ONLY'
 return dict(state=state,reason=reason,measurement_m=measured,auxiliary_prediction_m=prediction,engineering_q=q,peer_sigma_m=config['peer']['sigma_m'],threshold=GATE_Q,admitted_by_policy=admit,semantics='engineering fixed scale; not NIS/PL or a calibrated false alarm probability')

class GatedGraph(graph.WindowGraph):
 def __init__(self,config,test_mode=None):
  super().__init__(config,True);self.auxiliary=graph.WindowGraph(config,False);self.test_mode=test_mode;self.current=None
  self.auxiliary_initial_prior=copy.deepcopy(self.auxiliary.prior.record())
 def update(self,stamp,local,observations,peer):
  start=time.perf_counter();aux=self.auxiliary.update(stamp,local,observations,None);aux_wall=time.perf_counter()-start
  # Auxiliary never sees peer, main state/prior or gate decisions, even at initialization.
  gate=decision(peer,aux,self.config,self.test_mode)
  start=time.perf_counter();result=super().update(stamp,local,observations,peer if gate['admitted_by_policy'] else None);main_wall=time.perf_counter()-start
  self.current=dict(state_time_s=stamp,gate=gate,auxiliary=dict(aux,snapshot=copy.deepcopy(self.auxiliary.snapshot()),initial_prior=self.auxiliary_initial_prior),auxiliary_update_wall_s=aux_wall,main_update_wall_s=main_wall)
  return result

class ProbeReplay(frontend.JointReplay):
 def __init__(self,config,method,on_output,origin_ns,test_mode=None):
  if method not in METHODS:raise ValueError('Unknown method')
  self.method=method;self.sink=on_output
  super().__init__(config,'D0' if method=='G0' else 'D1',self._publish,origin_ns)
  if method=='G2':self.graph=GatedGraph(config,test_mode)
 def _publish(self,row):
  row=copy.deepcopy(row);row['method_id']=self.method
  if self.method=='G2':
   current=self.graph.current
   if current is None or current['state_time_s']!=row['state_time_s']:
    gate=dict(state='missing' if row['peer_median_m'] is None else 'unknown',reason='NO_AGGREGATED_PEER' if row['peer_median_m'] is None else 'MISSING_CURRENT_ODOM_BRACKET',measurement_m=row['peer_median_m'],auxiliary_prediction_m=None,engineering_q=None,peer_sigma_m=self.config['peer']['sigma_m'],threshold=GATE_Q,admitted_by_policy=False)
    current=dict(gate=gate,auxiliary=None,auxiliary_update_wall_s=0.,main_update_wall_s=0.)
   row.update({k:copy.deepcopy(v) for k,v in current.items() if k!='state_time_s'})
   row['gate']['state_epoch_ns']=row['state_epoch_ns'];row['gate']['availability_cutoff_epoch_ns']=row['availability_cutoff_epoch_ns']
  else:
   row['auxiliary']=None;row['gate']=dict(state='missing' if row['peer_median_m'] is None else 'not_applicable',reason='BASELINE_NO_GATE',measurement_m=row['peer_median_m'],auxiliary_prediction_m=None,engineering_q=None,admitted_by_policy=self.method=='G1' and row['peer_median_m'] is not None)
   row['auxiliary_update_wall_s']=0.;row['main_update_wall_s']=row['update_wall_s']
  snapshot=row['snapshot'];t=row['state_time_s'];present=t in snapshot['times_s']
  actual=bool(snapshot['peer_enabled'] and present and snapshot['peers_m'][snapshot['times_s'].index(t)] is not None)
  row['peer_factor_used']=actual;row['gate']['information_entered']=actual
  row['candidate_peer_factor_id']='peer|'+str(row['state_epoch_ns']);row['actual_peer_factor_id']=row['candidate_peer_factor_id'] if actual else None
  if row['auxiliary'] is not None:
   row['auxiliary']['state_epoch_ns']=row['state_epoch_ns'];row['auxiliary']['availability_cutoff_epoch_ns']=row['availability_cutoff_epoch_ns'];row['auxiliary']['record_id']=digest(dict(epoch=row['state_epoch_ns'],snapshot=row['auxiliary']['snapshot']))
   assert all(p is None for p in row['auxiliary']['snapshot']['peers_m'])
  self.sink(row)

def execute(events,config,method,sink,test_mode=None):
 replay.validate(config);worker=None
 for raw in events:
  if worker is None:worker=ProbeReplay(config,method,sink,raw['receive_epoch_ns'],test_mode)
  worker.ingest(raw)
 if worker is None:raise ValueError('Empty input')
 worker.finish();return worker

def semantic(value):
 if isinstance(value,dict):return {k:semantic(v) for k,v in value.items() if not(k.endswith('_wall_s') or k.startswith('estimated_worker_'))}
 if isinstance(value,list):return [semantic(v) for v in value]
 return value

def numeric(row):
 s=copy.deepcopy(row['snapshot'])
 if not s['peer_enabled']:s['peers_m']=[None]*len(s['peers_m'])
 s.pop('peer_enabled',None)
 return dict(pose=row['pose'],accepted_graph=row['accepted_graph'],status=row['status'],snapshot=s)

def export_baseline(row,method):
 """Decorate an archived baseline publication; no estimator is constructed/run."""
 if method not in ('G0','G1'):raise ValueError('Only frozen baselines can be reused')
 result=[];exporter=object.__new__(ProbeReplay);exporter.method=method;exporter.sink=result.append
 ProbeReplay._publish(exporter,row)
 return result[0]
