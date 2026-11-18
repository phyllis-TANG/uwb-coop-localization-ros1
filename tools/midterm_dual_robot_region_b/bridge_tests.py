"""Synthetic A/B schema tests; never executes the formal matrix."""
import copy,unittest
from common import read,DOC,I
from runtime import a_check
from a_bridge import a_module,make_certificate,protocol_recovery
from prepare import convert,decimal_exact
from core import solve,predictions
from certificate import audit
from geometry import projections
LOCK=read(DOC/'SOURCE_LOCK.json');A=a_module(LOCK['source_root']);TH={'8':'24','9':'26'}
def fixture():
 x=dict(schema_version='DUAL-A-V1',model_id='dual_robot_single_epoch_diagonal_v1',state_order=A.ORDER,measurement_ids=A.IDS,anchor_map={f'a{k}':v for k,v in enumerate([['1','0'],['0','1'],['-1','0'],['0','-1']])},bias_incidence=[0]*8+[1],domains=[['-2','2']]*4+[['-3/5','3/5']],observation_intervals=[['1','1']]*8+[['0','0']],noise_model=dict(kind='known_diagonal_gaussian',dimension=9,variance=['1']*9,independence='nine_unique_raw_errors',bias_evolution='single_constant'),threshold_certificate=A.threshold(9),arithmetic_policy=A.POLICY,budget=dict(max_nodes=41,max_seconds='2',position_resolution='1/20',bias_resolution='1/20'),source_commit=A.BASE,case_id='BRIDGE_DEVELOPMENT_ONLY',units='m',frame='synthetic_xy',epoch='t0',antenna_reference='2d_antenna',representation='enclosing_closed_cartesian_intervals',position_prior=None,motion=None)
 return A.seal(x)
class Tests(unittest.TestCase):
 def test_32_A_all_modes(self):
  x=fixture();A.validate(x);c=dict(a_input=x,model=convert(x))
  for method in ('J5','P4','N4'):
   s=dict(df=8 if method=='N4' else 9,q=TH['8' if method=='N4' else '9'],tolerance=['.05']*5,max_boxes=40,max_seconds=2)
   r=solve(c['model'],method,s,TH);audit(c['model'],method,s,r);p=projections(c['model'],r);self.assertEqual(a_check(c,method,s,r,p,LOCK)['status'],'PASS')
 def test_33_A_recovery(self):
  x=fixture()
  for p in [['0']*4,['1/3','1/5','-2/3','7/8'],['2','0','0','0']]:self.assertEqual(protocol_recovery(x,p),A.recovery(x,p))
 def test_34_exact_rational_conversion(self):
  from fractions import Fraction as F
  for x in ['3/5','1/625','7/1099511627776000000000000000000000000000000','-9/2']:self.assertEqual(F(decimal_exact(x)),F(x))
  with self.assertRaises(ValueError):decimal_exact('1/3')
 def test_35_A_tampered_branch(self):
  x=fixture();c=dict(a_input=x,model=convert(x));s=dict(df=9,q='26',tolerance=['.05']*5,max_boxes=1,max_seconds=2);r=solve(c['model'],'P4',s,TH);p=projections(c['model'],r);z=make_certificate(c,'P4',s,r,p);z['nodes'].pop()
  with self.assertRaises(A.Invalid):A.check(x,z)
 def test_36_A_frozen_threshold_proofs(self):
  for df in (8,9):A.threshold_check(A.threshold(df),df)
if __name__=='__main__':unittest.main(verbosity=2)
