"""Development-only analytic/rational cases. Never executes frozen eight cases."""
import unittest,json,tempfile
from pathlib import Path
from fractions import Fraction as F
from interval import *
from invert import objective,solve
from check import audit,contains,metrics,rational_bound
from inputs import make_model
SET=dict(q='1',tolerance=['.1']*3,max_boxes=2000,max_seconds=10)
class Tests(unittest.TestCase):
 def test_refuse_overwrite(self):
  from run import save
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'attempt.json';save(p,{'calls':1})
   with self.assertRaises(FileExistsError):save(p,{'calls':2})
   self.assertEqual(json.loads(p.read_text())['calls'],1)
 def test_arithmetic(self):
  vals=['-2.0000000000000000000000000000000000000001','-1','.0000000000000000000000000000003','0','.7','2']
  for a in vals:
   for b in vals:
    x,y=point(a),point(b)
    for op,exact in [(add,F(a)+F(b)),(sub,F(a)-F(b)),(mul,F(a)*F(b))]:
     lo,hi=op(x,y);self.assertTrue(F(lo)<=exact<=F(hi))
  lo,hi=square((D('-2'),D('3')));self.assertEqual((lo,hi),(D(0),D(9)))
  for x in ['0','2','4','1e-60','1e20']:
   l,h=sqrt(point(x));self.assertLessEqual(F(l)**2,F(x));self.assertGreaterEqual(F(h)**2,F(x))
  with self.assertRaises(TypeError):point(.1)
  with self.assertRaises(ValueError):point('NaN')
 def test_threshold(self):self.assertLess(threshold_certificate()['tail_upper_display'],.05)
 def affine(self):return dict(affine=True,A=[['1','0'],['0','1']],offset=['0','0'],observations=[['0','0']]*2,sigma=['1']*2,domain=[['-2','2']]*2)
 def test_affine_disk(self):
  m=self.affine();r=solve(m,SET);audit(m,SET,r)
  for p in [('0','0'),('1','0'),('-1','0'),('0','1'),('.6','.8')]:self.assertTrue(contains(r,p))
  self.assertGreaterEqual(F(metrics(m,r)['area_upper_m2']),F('3.1415'))
 def test_mirror(self):
  m=make_model([['-3','0'],['0','0'],['2','0'],['4','0']],['.5','1.5'],False,['0']*4)
  s=dict(SET,q='9.488',max_boxes=3000);r=solve(m,s);audit(m,s,r)
  self.assertTrue(contains(r,['.5','1.5']));self.assertTrue(contains(r,['.5','-1.5']))
 def test_boundary(self):
  m=self.affine();m['observations']=[['2','2'],['0','0']];r=solve(m,SET);audit(m,SET,r)
  self.assertTrue(contains(r,['2','0']));self.assertTrue(r['boundary_contact'])
 def test_empty(self):
  m=self.affine();m['observations']=[['100','100']]*2;r=solve(m,SET);audit(m,SET,r);self.assertTrue(r['empty_proved'])
 def test_budget_queue(self):
  m=self.affine();s=dict(SET,max_boxes=1);r=solve(m,s);audit(m,s,r)
  self.assertEqual(r['counts']['PENDING'],2);self.assertTrue(contains(r,['1','0']))
 def test_time(self):
  m=self.affine();ticks=iter([0,11,12]);r=solve(m,SET,clock=lambda:next(ticks));audit(m,SET,r)
  self.assertEqual(r['termination'],'TIME_BUDGET');self.assertEqual(r['counts']['PENDING'],1)
 def test_failure(self):
  m=self.affine()
  def fail(*a):raise ArithmeticError('injected')
  r=solve(m,SET,bound=fail);audit(m,SET,r);self.assertFalse(r['empty_proved']);self.assertEqual(r['termination'],'NUMERICAL_FAILURE')
 def test_projection(self):
  m=self.affine();m['A']=[['1','0','0'],['0','1','0']];m['domain']+=[['-.6','.6']]
  s=dict(SET,max_boxes=100);r=solve(m,s);audit(m,s,r);z=metrics(m,r)
  self.assertTrue(contains(r,['0','0','.6']));self.assertIsNotNone(z['radius_upper_m'])
  c=list(map(F,z['center']));rad=F(z['radius_upper_m'])
  for b in z['projection_rectangles']:
   for x in b[0]:
    for y in b[1]:self.assertLessEqual((F(x)-c[0])**2+(F(y)-c[1])**2,rad**2)
 def test_units(self):
  m=make_model([['-3','0'],['0','0'],['2','1'],['4','0']],['.5','1.5','.2'],True,['0']*4)
  b=decode([['.4','.6'],['1.4','1.6'],['.1','.3']]);lo,hi=objective(b,m)
  import copy
  mm=copy.deepcopy(m)
  def scale(v):
   a=D(v).as_tuple();return D((a.sign,a.digits,a.exponent+3))
  for key in ['anchors','observations','domain']:mm[key]=[[str(scale(v)) for v in row] for row in mm[key]]
  mm['known_bias']=str(scale(mm['known_bias']));mm['sigma']=[str(scale(v)) for v in mm['sigma']]
  bb=tuple((scale(a),scale(v)) for a,v in b);l,h=objective(bb,mm)
  self.assertLess(abs(l-lo),D('1e-25'));self.assertLess(abs(h-hi),D('1e-25'))
 def test_rational_model(self):
  m=make_model([['-3','0'],['0','0'],['2','1'],['4','0']],['.5','1.5','.2'],True,['0']*4)
  b=decode([['.4','.6'],['1.4','1.6'],['.1','.3']]);lo,hi=objective(b,m);l,h=rational_bound(tuple(tuple(F(x) for x in a) for a in b),m)
  self.assertLessEqual(F(lo),l);self.assertGreaterEqual(F(hi),h)
if __name__=='__main__':unittest.main(verbosity=2)
