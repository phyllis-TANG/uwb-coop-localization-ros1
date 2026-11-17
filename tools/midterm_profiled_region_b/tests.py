import unittest,copy
from fractions import Fraction as F
from common import I,OC,OINPUT,projected
from profiled import gap_squared,bound,recover_bias,solve
from certificate import rational_profile,audit,xy_contains,bias_reference
class Tests(unittest.TestCase):
 def model(self):return dict(anchors=[['1','0'],['0','1'],['-1','0'],['0','-1']],observations=[['1','1']]*4,sigma=['1']*4,affected_index=3,unknown_bias=True,domain=[['-2','2'],['-2','2'],['-.6','.6']],known_bias='.3')
 def test_clipping(self):
  for value,expected in [('1.2',F(0)),('1.8',F('.04')),('0.2',F('.04'))]:
   m=self.model();m['observations'][3]=[value,value];l,h=bound((I.point('0'),I.point('0')),projected(m))
   self.assertLessEqual(F(l),expected);self.assertGreaterEqual(F(h),expected)
 def test_interval_quantifiers(self):
  m=self.model();m['observations'][3]=['1.5','2'];l,h=bound((I.point('0'),I.point('0')),projected(m));self.assertEqual(l,0);self.assertEqual(h,0)
  z=recover_bias(['0','0'],m,q='0');self.assertEqual(list(map(F,z['outer'])),[F('.5'),F('.6')])
 def test_zero_budget_tangent(self):
  m=self.model();m['observations'][3]=['1.6','1.6'];z=recover_bias(['0','0'],m,'0');self.assertEqual(list(map(F,z['outer'])),[F('.6')]*2);self.assertIsNotNone(z['inner'])
 def test_negative_budget_empty(self):
  m=self.model();m['observations'][0]=['3','3'];self.assertEqual(recover_bias(['0','0'],m,'1')['status'],'EMPTY_PROVED')
 def test_degenerate_bias(self):
  m=self.model();m['unknown_bias']=False;m['domain']=m['domain'][:2];m['observations'][3]=['1.3','1.3'];z=recover_bias(['0','0'],m,'0');self.assertEqual(list(map(F,z['outer'])),[F('.3')]*2)
 def test_independent_point_and_box(self):
  m=OINPUT.make_model([['-3','0'],['0','0'],['2','1'],['4','0']],['.5','1.5','.2'],True,['0']*4)
  b=I.decode([['.4','.6'],['1.4','1.6']]);l,h=bound(b,projected(m));lo,hi=rational_profile(OC.unpack(I.encode(b)),projected(m));self.assertLessEqual(F(l),lo);self.assertGreaterEqual(F(h),hi)
  z=recover_bias(['.5','1.5'],m);out,inner=bias_reference(['.5','1.5'],m,'9.488');self.assertLessEqual(F(z['outer'][0]),out[0]);self.assertGreaterEqual(F(z['outer'][1]),out[1])
 def settings(self):return dict(q='9.488',tolerance=['.1']*3,max_boxes=1000,max_seconds=5)
 def test_mirror_and_certificate(self):
  m=OINPUT.make_model([['-3','0'],['0','0'],['2','0'],['4','0']],['.5','1.5','.2'],True,['0']*4);s=self.settings();r=solve(m,s);audit(m,s,r,'PROFILED');self.assertTrue(xy_contains(r,['.5','1.5']));self.assertTrue(xy_contains(r,['.5','-1.5']))
 def test_budget_and_tamper(self):
  m=self.model();s=dict(self.settings(),max_boxes=1);r=solve(m,s);audit(m,s,r,'PROFILED');self.assertTrue(xy_contains(r,['0','0']));self.assertGreater(r['counts'].get('PENDING',0),0)
  bad=copy.deepcopy(r);bad['nodes'].pop()
  with self.assertRaises((AssertionError,KeyError)):audit(m,s,bad,'PROFILED')
  bad=copy.deepcopy(r)
  for n in bad['nodes']:
   if n['status']=='PENDING':n['status']='OUTSIDE';break
  with self.assertRaises(AssertionError):audit(m,s,bad,'PROFILED')
 def test_time_and_numerical(self):
  m=self.model();s=self.settings();ticks=iter([0,6,7]);r=solve(m,s,clock=lambda:next(ticks));audit(m,s,r,'PROFILED');self.assertEqual(r['termination'],'TIME_BUDGET')
 def test_empty(self):
  m=self.model();m['observations']=[['-10','-10']]*4;r=solve(m,self.settings());audit(m,self.settings(),r,'PROFILED');self.assertTrue(r['empty_proved'])
 def test_units(self):
  m=self.model();m['observations'][3]=['2','2'];b=(I.point('0'),I.point('0'));v=bound(b,projected(m));mm=copy.deepcopy(m)
  for key in ['anchors','observations','domain']:mm[key]=[[str(I.D(x)*1000) for x in row] for row in mm[key]]
  mm['sigma']=['1000']*4;vv=bound(b,projected(mm));self.assertEqual(v,vv)
if __name__=='__main__':unittest.main(verbosity=2)
