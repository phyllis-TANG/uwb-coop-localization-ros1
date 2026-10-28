import copy,unittest
from common import METHODS,SCENARIOS
from run_development import validate
class IndexContract(unittest.TestCase):
 def test_missing_duplicate_failed_or_pending_cannot_pass(self):
  cells=[dict(id=s+'_seed101__'+m,case=s+'_seed101',method=m,status='REUSED_VERIFIED' if m in ['I','J'] else 'DONE') for s in SCENARIOS for m in METHODS]
  index=dict(status='DONE',cells=cells);validate(index,True)
  for c in [cells[:-1],cells+[cells[0]],cells[:-1]+[cells[0]],[]]:
   with self.assertRaises(ValueError):validate(dict(status='DONE',cells=c),True)
  for status in ['PLANNED','RUNNING','FAILED']:
   bad=copy.deepcopy(index);bad['cells'][-1]['status']=status
   with self.assertRaises(ValueError):validate(bad,True)
if __name__=='__main__':unittest.main(verbosity=2)
