import unittest,tempfile,subprocess,sys,csv
from pathlib import Path
import numpy as np
from antenna_geometry import positions
class Geometry(unittest.TestCase):
 def test_flat_and_slope(self):
  for slope in [0.,.5]:
   vertices=np.array([[x,y,slope*x] for x in [0,2] for y in [0,2]])
   data=dict(vertices=vertices,grid_shape=[2,2]);raw=np.array([[0.,0.,0.],[1.,0.,1.]])
   body,ant=positions(data,raw)
   self.assertAlmostEqual(np.linalg.norm(ant[1]-ant[0]),np.sqrt(1+slope*slope))
   np.testing.assert_array_equal(raw,[[0,0,0],[1,0,1]])
 def test_csv_zero_noise(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);np.savez(p/'scene.npz',vertices=np.array([[x,y,0] for x in [0,2] for y in [0,2]]),grid_shape=[2,2],sim_time=[0.,1.],leader=[[0,0,0],[0,0,0]],follower=[[1,0,1],[1,0,1]])
   subprocess.run([sys.executable,str(Path(__file__).with_name('make_uwb_replay.py')),'--scene',str(p/'scene.npz'),'--output',str(p/'out.csv'),'--noise','0'],check=True)
   for r in csv.DictReader((p/'out.csv').read_text().splitlines()):
    self.assertEqual(float(r['true_range_m']),1.);self.assertEqual(float(r['car1_range_m']),1.)
    self.assertEqual(float(r['car1_z']),1.16);self.assertEqual(float(r['car2_z']),1.16)
    self.assertEqual(float(r['car2_gt_z']),1.)
if __name__=='__main__':unittest.main()
