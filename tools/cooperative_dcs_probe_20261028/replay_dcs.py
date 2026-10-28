"""D0-D2 exact original routes; D3 uses the same frontend with peer DCS."""
import copy
from bindings import probe,frontend,replay,records
from kernel import WindowGraph

class DCSReplay(frontend.JointReplay):
    def __init__(self,config,sink,origin,peer_enabled=True,dcs=True):
        self.sink=sink;super().__init__(config,'D1' if peer_enabled else 'D0',self._publish,origin)
        self.graph=WindowGraph(config,peer_enabled,dcs);self.provenance=records.Provenance(origin)
    def _publish(self,row):
        row=copy.deepcopy(row);row['method_id']='D3';row['auxiliary']=None
        row['candidate_peer_factor_id']='peer|'+str(row['state_epoch_ns'])
        row['actual_peer_factor_id']=row['candidate_peer_factor_id'] if row['peer_factor_used'] else None
        row['main_update_wall_s']=row['update_wall_s'];row['auxiliary_update_wall_s']=0.
        for item in row.get('dcs_final_peers',[]):item['factor_id']='peer|'+str(self.origin_ns+round(item['state_time_s']*1e9))
        self.provenance.add(row);self.sink(row)

def execute(events,config,method,sink,peer_enabled=True,dcs=True):
    if method in ('D0','D1','D2'):return probe.execute(events,config,'G'+method[1],sink)
    if method!='D3':raise ValueError('unknown method')
    replay.validate(config);worker=None
    for raw in events:
        if worker is None:worker=DCSReplay(config,sink,raw['receive_epoch_ns'],peer_enabled,dcs)
        worker.ingest(raw)
    if worker is None:raise ValueError('empty input')
    worker.finish();return worker
