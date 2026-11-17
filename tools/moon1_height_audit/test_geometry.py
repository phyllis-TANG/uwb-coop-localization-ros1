"""Synthetic acceptance fixtures, explicitly not Moon_1 observations."""
import csv
import tempfile
import unittest
from pathlib import Path
import numpy as np
from geometry import REQUIRED, metrics, load_csv, grid_stencil, sample_grid, raw_grid, support

class GeometryTests(unittest.TestCase):
    def test_flat_and_coincident(self):
        out=metrics([[0,0,1.16],[0,0,1.16]], [[2,0,1.16],[0,0,1.16]], 0)
        np.testing.assert_array_equal(out['ignore_error_m'], [0,0])
        np.testing.assert_array_equal(out['analytic_error_m'], [0,0])
        self.assertEqual(out['coincident'].tolist(),[False,True])

    def test_slope_and_vertical(self):
        out=metrics([[0,0,1.16],[0,0,2]], [[2,0,2.16],[0,0,0]], -.03)
        self.assertAlmostEqual(out['r_3d_m'][0],np.sqrt(5))
        np.testing.assert_allclose(out['ignore_error_m'],out['analytic_error_m'],atol=1e-15)
        self.assertEqual(out['ignore_error_m'][1],2)

    def test_stencil_fill_smoothing_and_clip(self):
        dtype=[('x',float),('y',float),('z',float)]
        pts=np.array([(x,-y,-.2*x) for x in range(9) for y in range(9) if (x,y)!=(4,4)],dtype=dtype)
        raw=raw_grid(pts,[0,8,0,8],1)
        vertices=np.array([[x,y,raw['smooth'][x,y]] for x in range(9) for y in range(9)],dtype=np.float32)
        data=dict(vertices=vertices,grid_shape=[9,9],observed=raw['observed'],distance_to_observation=np.zeros((9,9)))
        s=support(data,np.array([[4.2,4.2],[3.,3.],[-1,2],[8,8]]),raw)
        self.assertEqual(s['rank'][0],2)
        self.assertEqual(s['rank'][1],1)
        self.assertTrue(s['clipped'][2])
        self.assertTrue(s['clipped'][3])  # upper epsilon clip even on exact boundary
        self.assertFalse(s['outside'][3])
        self.assertGreater(s['fill_mass'][1],0)
        np.testing.assert_allclose(s['weights'].sum(axis=1),1)
        self.assertEqual(s['nodes'].shape,(4,4,2))

    def test_bilinear_plane(self):
        data=dict(grid_shape=[3,3],vertices=np.array([[x,y,2*x+3*y] for x in range(3) for y in range(3)],dtype=float))
        xy=np.array([[.2,.3],[1.5,1.8]])
        nodes,w,*_=grid_stencil(data,xy)
        z=sample_grid(data['vertices'][:,2].reshape(3,3),nodes,w)
        np.testing.assert_allclose(z,xy@[2,3])

    def test_legacy_and_invalid_time_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'old.csv';p.write_text('time_s,car1_x\n0,0\n1,1\n')
            with self.assertRaisesRegex(ValueError,'Legacy/incomplete'):load_csv(p)
            with p.open('w') as f:
                w=csv.DictWriter(f,fieldnames=REQUIRED);w.writeheader()
                for _ in range(2):w.writerow({k:0 for k in REQUIRED})
            with self.assertRaisesRegex(ValueError,'Non-increasing'):load_csv(p)

if __name__=='__main__':unittest.main()
