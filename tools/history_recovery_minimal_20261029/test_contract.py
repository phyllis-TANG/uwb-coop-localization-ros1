import copy, unittest
from unittest.mock import patch
import numpy as np
from support import config,old,SET
from engine import CutGraph,graph
from publication import publish,antennas

class Contract(unittest.TestCase):
 def test_only_admission_changes(self):
  cfg=config(SET['cases'][0]);g=CutGraph(cfg);ref=g.prior.record();local=np.zeros((2,3));obs={'car1':{},'car2':{}}
  with patch.object(graph.WindowGraph,'update',return_value={'test':True}) as f:
   for t,z,expected in [(38,2.,2.),(39,2.,None),(39,None,None),(20,None,None)]:
    g.update(t,local,obs,z);args=f.call_args.args
    self.assertEqual(args[0],t);self.assertIs(args[1],local);self.assertIs(args[2],obs);self.assertEqual(args[3],expected)
  self.assertTrue(g.peer_enabled);self.assertEqual(g.prior.record(),ref)
 def test_real_objective_removes_peer(self):
  cfg=config(SET['cases'][0]);s=old(SET['cases'][0],'J')[30]['snapshot'];x=np.array(s['states']).ravel();args=[s['times_s'],s['local'],s['observations']];prior=graph.JointPrior(**s['prior'])
  a=graph.Objective(*args,s['peers_m'],cfg,prior,True);none=graph.Objective(*args,[None]*len(s['peers_m']),cfg,prior,True)
  n=sum(p is not None for p in s['peers_m']);self.assertEqual(len(a.fun(x))-len(none.fun(x)),n);np.testing.assert_array_equal(a.fun(x)[:-n],none.fun(x));self.assertGreater(np.linalg.norm(a.jac(x)[-n:]),0)
 def test_published_antenna_zero_and_nonzero(self):
  cfg=config(SET['cases'][0]);r={'pose':[2.,3.,1.2,3.,2.,-1.7],'accepted_graph':True};i={'pose':[1.,3.,-.8,3.,1.,.4],'accepted_graph':True}
  for limits in ([0.,.04],[.04,0.],[.04,.04]):
   out=publish(r,i,cfg,limits);d=np.linalg.norm(antennas(out['pose'],cfg)-antennas(i['pose'],cfg),axis=1);np.testing.assert_allclose(d,limits,atol=1e-12,rtol=0);self.assertEqual(out['pose'][2::3],r['pose'][2::3]);self.assertIsNone(out['covariance'])
 def test_unknown_and_failure_not_success(self):
  cfg=config(SET['cases'][0]);r={'pose':[0.]*6,'accepted_graph':True};i=copy.deepcopy(r);i['accepted_graph']=False
  self.assertEqual(publish(r,i,cfg,[.04,.04])['mode'],'unknown');self.assertFalse(publish(r,i,cfg,[.04,.04])['budget_certified'])
  self.assertEqual(publish(i,r,cfg,[.04,.04])['mode'],'reference_fallback')
if __name__=='__main__':unittest.main()
