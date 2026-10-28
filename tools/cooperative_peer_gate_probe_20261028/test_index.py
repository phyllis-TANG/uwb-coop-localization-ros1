import copy,unittest
from index_contract import EXPECTED,validate
class IndexTests(unittest.TestCase):
 def valid(self):return dict(status='DONE',cells=[dict(scenario=s,seed=k,method=m,status='DONE',events_sha256=f'e{s}{k}',config_sha256=f'c{k}') for s,k,m in sorted(EXPECTED)])
 def test_complete_45_required(self):
  good=self.valid();self.assertTrue(validate(good))
  for rows in ([],good['cells'][:-1],good['cells']+[good['cells'][0]],good['cells'][:-1]+[good['cells'][0]]):
   with self.assertRaises(ValueError):validate(dict(status='DONE',cells=rows))
 def test_failed_and_not_started_are_rejected(self):
  for state in ('FAILED','PLANNED','IN_PROGRESS'):
   bad=self.valid();bad['cells'][0]['status']=state
   with self.assertRaises(ValueError):validate(bad)
 def test_input_pairing_required(self):
  bad=self.valid();bad['cells'][0]['events_sha256']='different'
  with self.assertRaises(ValueError):validate(bad)
if __name__=='__main__':unittest.main(verbosity=2)
