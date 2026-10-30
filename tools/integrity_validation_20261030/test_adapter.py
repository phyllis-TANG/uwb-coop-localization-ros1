import unittest
from experiment import make,CONDITIONS,simulate
class Adapter(unittest.TestCase):
 def test_registered_changes_and_pairing(self):
  c,e,t,r=make(101,'nominal')
  for condition in CONDITIONS:
   cc,ee,tt,rr=make(101,condition)
   self.assertEqual(c,cc);self.assertEqual(t,tt)
   for a,b in zip(e,ee):
    self.assertEqual(a['receive_epoch_ns'],b['receive_epoch_ns'])
    if a['kind']=='odom':self.assertEqual(a['value'],b['value'])
    if a['kind']=='uwb' and condition!='peer_bias':
     key='node_0' if a['vehicle_id']=='car1' else 'node_1'
     self.assertEqual(a['value'][key],b['value'][key])
   if condition=='car1_common_wall_bias':self.assertEqual(rr['changed_wall_scalars'],1120)
 def test_original_three_inputs(self):
  from inputs import make as original
  for condition in list(CONDITIONS)[:3]:
   c,e,t,r=make(101,condition);cc,ee,tt,_=original(condition)
   self.assertEqual(c,cc);self.assertEqual(e,ee);self.assertEqual(t,tt)
if __name__=='__main__':unittest.main()
