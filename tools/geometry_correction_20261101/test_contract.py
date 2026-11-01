"""Deterministic toy checks; no new study seed or FGO replay."""
import unittest
import numpy as np
from initialize import fit_xy
from analyze import interval

class Contracts(unittest.TestCase):
    def test_moving_slant_range_initialization_without_true_initial_guess(self):
        refs=np.array([[0.,0.,2.],[5.,0.,2.2],[5.,5.,2.4],[0.,5.,2.1]])
        offsets=np.array([[.1,.2],[.3,.4],[.8,.3],[1.,.5]])
        truth=np.array([1.2,1.7]);height=.2
        measurements=np.sqrt(np.sum((truth+offsets[:,None,:]-refs[None,:,:2])**2,axis=2)+(height-refs[None,:,2])**2)
        result,receipt=fit_xy(offsets,refs,height,measurements)
        np.testing.assert_allclose(result.x,truth,atol=1e-8,rtol=0)
        self.assertLess(receipt['residual_rms_m'],1e-9)
    def test_prespecified_decision_edges(self):
        self.assertTrue(interval([.002,.0021,.0022,.0019])['pass_primary'])
        self.assertFalse(interval([.0001,.0001,.0001,.0001])['pass_primary'])
        self.assertFalse(interval([-.002,.0021,.0022,.0019])['pass_primary'])
        self.assertFalse(interval([.002,.0021,.0022])['pass_primary'])

if __name__=='__main__':unittest.main(verbosity=2)
