"""Independent development fixtures. Not A formal inputs or validation seeds."""
import copy,json,tempfile,unittest
from pathlib import Path
from fractions import Fraction as F
from common import I,validate,write,read
from core import solve,objective,distance
from certificate import audit,bias_at,bound,contains,point
from geometry import projections,audit_projection,evaluate
from archive import pack,unpack
TH={'8':'16','9':'18'}
def fixture():
 return dict(schema='DUAL-B-INTERNAL-V1',state_order=['px','py','sx','sy','b'],anchors=[['1','0'],['0','1'],['-1','0'],['0','-1']],observations=[['1','1']]*8+[['0','0']],measurement_ids=[f'dev{i}' for i in range(9)],R=[['1' if i==j else '0' for j in range(9)] for i in range(9)],domain=[['-2','2']]*4,bias_domain=['-.6','.6'],bias_incidence=[0]*8+[1],units='m',frame='development',epoch='single',representation='exact development values')
def settings(method='P4',**kw):return dict(df=8 if method=='N4' else 9,q=TH['8' if method=='N4' else '9'],tolerance=['.05']*5,max_boxes=100,max_seconds=2,**kw)
class Tests(unittest.TestCase):
 def run_case(self,m=None,method='P4',s=None):
  m=m or fixture();s=s or settings(method);r=solve(m,method,s,TH);audit(m,method,s,r);return m,s,r
 def test_01_projected_fixed_point(self):
  m=fixture();p=tuple(point('0') for _ in range(4));lo,hi=bound(p,m,'P4');self.assertEqual((lo,hi),(0,0));self.assertEqual(bound(p+(point('0'),),m,'J5'),(0,0))
 def test_02_bias_interior_and_endpoints(self):
  m=fixture();m['observations'][8]=['1','1'];p=I.decode([['0','0']]*4);lo,hi=objective(p,m,'P4');self.assertLessEqual(F(lo),F('.16'));self.assertGreaterEqual(F(hi),F('.16'));m['observations'][8]=['-1','-1'];self.assertEqual(objective(p,m,'P4'),(lo,hi))
 def test_03_known_bias(self):
  m=fixture();m['bias_domain']=['.3','.3'];m['observations'][8]=['.3','.3'];self.assertEqual(bias_at(['0']*4,m,'0')['inner'],['3/10','3/10'])
 def test_04_zero_distance(self):self.assertEqual(distance(I.decode([['0','0']]*2),I.decode([['0','0']]*2)),(0,0))
 def test_05_touch_zero_remainder(self):
  m=fixture();m['observations'][8]=['.6','.6'];z=bias_at(['0']*4,m,'0');self.assertEqual(z['inner'],['3/5','3/5'])
 def test_06_empty_bias(self):
  m=fixture();m['observations'][8]=['2','2'];self.assertEqual(bias_at(['0']*4,m,'0')['status'],'EMPTY_PROVED')
 def test_07_interval_observation(self):
  m=fixture();m['observations'][8]=['.5','2'];self.assertEqual(bias_at(['0']*4,m,'0')['inner'],['1/2','3/5'])
 def test_08_mirror(self):
  m=fixture();m['anchors']=[['-2','0'],['-1','0'],['1','0'],['2','0']];p=I.decode([['0','0'],['1','1'],['1','1'],['1','1']]);from core import predictions
  m['observations']=I.encode(predictions(p,m));m['R']=[['.0016' if i==j else '0' for j in range(9)] for i in range(9)]
  for method in ('J5','P4','N4'):
   _,s,r=self.run_case(m,method);self.assertTrue(contains(r,['0','1','1','1']));self.assertTrue(contains(r,['0','-1','1','-1']))
 def test_09_wrong_R(self):
  for val,i,j in [('0',0,0),('-.1',0,0),('.1',0,1)]:
   m=fixture();m['R'][i][j]=val
   with self.assertRaises(ValueError):solve(m,'P4',settings(),TH)
 def test_10_wrong_threshold(self):
  s=settings();s['q']='9.488'
  with self.assertRaises(ValueError):solve(fixture(),'P4',s,TH)
 def test_11_wrong_df(self):
  s=settings();s['df']=4
  with self.assertRaises(ValueError):solve(fixture(),'P4',s,TH)
 def forced(self):
  s=settings();s['max_boxes']=1;return self.run_case(s=s)
 def test_12_deleted_queue(self):
  m,s,r=self.forced();r['nodes'].pop()
  with self.assertRaises((AssertionError,KeyError)):audit(m,'P4',s,r)
 def test_13_false_exclusion(self):
  m,s,r=self.forced();r['nodes'][-1]['status']='OUTSIDE'
  with self.assertRaises(AssertionError):audit(m,'P4',s,r)
 def test_14_split_gap(self):
  m,s,r=self.forced();r['nodes'][-1]['box'][0][0]='.1'
  with self.assertRaises(AssertionError):audit(m,'P4',s,r)
 def test_15_projection_omission(self):
  m,s,r=self.forced();p=projections(m,r);p['s']['rectangles'].pop()
  with self.assertRaises(AssertionError):audit_projection(m,r,p)
 def test_16_corrupt_archive(self):
  with tempfile.TemporaryDirectory() as td:
   d=Path(td);write(d/'x.json',{'a':1});man=pack([d/'x.json'],d,d/'out.tar.gz');unpack(d/'out.tar.gz',man,d/'good');(d/'out.tar.gz').write_bytes(b'corrupt')
   with self.assertRaises(AssertionError):unpack(d/'out.tar.gz',man,d/'bad')
 def test_17_truth_rejected(self):
  m=fixture();m['truth']=['0']*5
  with self.assertRaises(ValueError):solve(m,'P4',settings(),TH)
 def test_18_budget_complete(self):
  m,s,r=self.forced();self.assertEqual(r['termination'],'BOX_BUDGET');self.assertEqual(len(r['queue']),2);audit_projection(m,r,projections(m,r))
 def test_19_timeout(self):
  ticks=iter([0,3,4]);m=fixture();s=settings();r=solve(m,'P4',s,TH,clock=lambda:next(ticks));audit(m,'P4',s,r);self.assertEqual(r['termination'],'TIME_BUDGET')
 def test_20_empty_domain_result(self):
  m=fixture();m['observations']=[['-100','-100']]*9
  for method in ('J5','P4','N4'):
   _,s,r=self.run_case(m,method);self.assertTrue(r['empty_proved']);self.assertIsNone(projections(m,r)['p']['radius_upper_m'])
 def test_21_duplicate_identity(self):
  m=fixture();m['measurement_ids'][1]=m['measurement_ids'][0]
  with self.assertRaises(ValueError):solve(m,'P4',settings(),TH)
 def test_22_n4_peer_invariance(self):
  m=fixture();_,s,r=self.run_case(m,'N4');m['observations'][8]=['100','100'];r2=solve(m,'N4',s,TH);self.assertEqual(r['nodes'],r2['nodes'])
 def test_23_joint_and_marginal_distinction(self):
  m,s,r=self.forced();e=evaluate(m,'P4',s,r,{'truth':['0']*5,'noise':['0']*9});self.assertTrue(e['noise_event']['holds']);self.assertEqual(e['exact_joint_position_feasibility'],'FEASIBLE_PROVED')
 def test_24_dimensionality(self):
  for method,dim in [('J5',5),('P4',4),('N4',4)]:
   m,s,r=self.run_case(method=method);self.assertEqual(r['dimension'],dim);self.assertTrue(all(len(n['box'])==dim for n in r['nodes']))
if __name__=='__main__':unittest.main(verbosity=2)
