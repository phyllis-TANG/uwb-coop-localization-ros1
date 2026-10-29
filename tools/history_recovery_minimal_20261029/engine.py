"""Only new-peer admission changes. No truth/label input; no history edits."""
import copy, os, sys
import numpy as np
from support import EVIDENCE, SET
os.environ['PEER_GATE_FROZEN_ROOT']=str(EVIDENCE/'source')
sys.path.insert(0,str(EVIDENCE/'source/tools/cooperative_peer_gate_probe_20261028'))
from pinned import frontend, graph, replay

class CutGraph(graph.WindowGraph):
 def __init__(self,config):super().__init__(config,True)
 def update(self,stamp,local,observations,peer):
  return super().update(stamp,local,observations,peer if stamp<SET['cut_new_peer_at_state_s'] else None)

class CutReplay(frontend.JointReplay):
 def __init__(self,config,sink,origin):
  self.sink=sink; self.consumed=[]
  super().__init__(config,'D1',self.publish,origin)
  self.graph=CutGraph(config)
 def publish(self,row):
  r=copy.deepcopy(row);s=r['snapshot'];t=r['state_time_s']
  active=[u for u,p in zip(s['times_s'],s['peers_m']) if p is not None]
  for d in r['marginalization_details']:
   if d['old_peer_m'] is not None:self.consumed.append(d['times_s'][0])
  r.update(method_id='N',peer_factor_used=t in active,actual_peer_factor_id=('peer|'+str(r['state_epoch_ns'])) if t in active else None,
   admission='missing' if r['peer_median_m'] is None else 'fixed_time_reject' if t>=SET['cut_new_peer_at_state_s'] else 'admit',
   provenance=dict(window_peer_times_s=active,prior_peer_times_s=self.consumed.copy(),history_policy='retain full prior; no rollback'))
  self.sink(r)

def execute(events,config):
 replay.validate(config);rows=[];worker=None
 for e in events:
  if worker is None:worker=CutReplay(config,rows.append,e['receive_epoch_ns'])
  worker.ingest(e)
 if worker is None:raise ValueError('No input')
 worker.finish();return rows

def solve_snapshot(active,prior_package,initial,config):
 p=graph.JointPrior(**prior_package['prior'])
 obj=graph.Objective(active['times_s'],active['local'],active['observations'],active['peers_m'],config,p,True)
 sol=graph.least_squares(obj.fun,np.array(initial['states']).ravel(),jac=obj.jac,method='trf',tr_solver='exact',loss='linear',max_nfev=config['optimizer']['max_nfev'],ftol=1e-7,xtol=1e-7,gtol=1e-7)
 snap=copy.deepcopy(active);snap.update(prior=copy.deepcopy(prior_package['prior']),eliminated_constant=prior_package['eliminated_constant'],states=sol.x.reshape(-1,6).tolist())
 return dict(snapshot=snap,success=bool(sol.success and np.isfinite(sol.x).all()),status=int(sol.status),message=str(sol.message),cost=float(sol.cost),optimality=float(sol.optimality),nfev=int(sol.nfev))
