"""Regression tests for missing bias versus a valid zero estimate."""
import csv,json,math,tempfile,unittest
from pathlib import Path
from analyze_logs import error,state_row,rmse_values,write_csv
from make_delivery import vals

class BiasSemanticsTests(unittest.TestCase):
 def test_missing_bias(self):
  truth=dict(pose=[1.,2.,3.],bias_rad_s=.017)
  for row in (dict(pose=[1.,2.,3.]),dict(pose=[1.,2.,3.],bias_rad_s=None),state_row([1.,2.,3.])):
   with self.subTest(row=row):
    result=dict(bias=row.get('bias_rad_s'),**error(row,truth))
    self.assertIsNone(result['bias']);self.assertIsNone(result['bias_error_rad_s'])
    self.assertIsNone(rmse_values([result['bias_error_rad_s']]))
    self.assertIsNone(json.loads(json.dumps(result))['bias_error_rad_s'])
    with tempfile.TemporaryDirectory() as temp:
     p=Path(temp)/'missing.csv';write_csv(p,[result])
     with p.open() as f:exported=next(csv.DictReader(f))
     self.assertEqual(exported['bias'],'');self.assertEqual(exported['bias_error_rad_s'],'')
     self.assertTrue(math.isnan(vals([exported],'bias_error_rad_s')[0]))

 def test_valid_zero_bias(self):
  truth=dict(pose=[1.,2.,3.],bias_rad_s=.017)
  row=state_row([1.,2.,3.,0.]);result=dict(bias=row['bias_rad_s'],**error(row,truth))
  self.assertEqual(result['bias'],0.);self.assertEqual(result['bias_error_rad_s'],-.017)
  self.assertAlmostEqual(rmse_values([None,result['bias_error_rad_s']]),.017)
  self.assertEqual(error(row,dict(truth,bias_rad_s=0.))['bias_error_rad_s'],0.)
  with tempfile.TemporaryDirectory() as temp:
   p=Path(temp)/'zero.csv';write_csv(p,[result])
   with p.open() as f:exported=next(csv.DictReader(f))
   self.assertEqual(float(exported['bias']),0.);self.assertEqual(float(exported['bias_error_rad_s']),-.017)
   self.assertEqual(vals([exported],'bias')[0],0.)

if __name__=='__main__':unittest.main(verbosity=2)
