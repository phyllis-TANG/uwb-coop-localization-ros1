"""Same receive frontend; private independent reference shares each closed bin."""
import copy
from common import METHODS
from bindings import frontend,replay,base,records
from core import InfluenceGraph
class Replay(frontend.JointReplay):
 def __init__(self,config,method,sink,origin,test_fault=None):
  self.method=method;self.sink=sink;self.provenance=records.Provenance(origin)
  super().__init__(config,'D1',self.publish,origin);self.graph=InfluenceGraph(config,method,test_fault=test_fault)
 def publish(self,row):
  row=copy.deepcopy(row);row['method_id']=self.method;current=self.graph.current
  if current is None or current['state_time_s']!=row['state_time_s']:
   row.update(reference=None,auxiliary=None,publication_mode='unknown',publication_reason='MISSING_ODOM',joint_optimization_success=False,reference_accepted=False,
    budget_m=self.graph.budget,budget_certified=False,published_separation_m=None,covariance=None,main_accepted_graph=False,main_pose=None,main_status=row['status'],main_update_wall_s=0.,reference_update_wall_s=0.)
  else:
   row['reference']=copy.deepcopy(current['reference']);row['reference'].update(state_epoch_ns=row['state_epoch_ns'],availability_cutoff_epoch_ns=row['availability_cutoff_epoch_ns'])
   row['auxiliary']=row['reference']
   assert all(p is None for p in row['reference']['snapshot']['peers_m'])
  self.provenance.add(row);row.pop('auxiliary',None)
  self.sink(row)
def execute(events,config,method,sink,test_fault=None):
 if method not in ['W025','U','K004','K100']:raise ValueError('New-run method invalid')
 replay.validate(config);worker=Replay(config,method,sink,events[0]['receive_epoch_ns'],test_fault)
 for e in events:worker.ingest(e)
 worker.finish();return worker
