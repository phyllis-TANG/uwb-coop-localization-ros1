import unittest
from analyze import relation,signed_change
class EvidenceMath(unittest.TestCase):
 def test_tradeoff_not_team_average_win(self):
  self.assertEqual(relation([.1,.08],[.2,.01]),'tradeoff')
 def test_xy_win_can_disappear_with_yaw(self):
  self.assertEqual(relation([.1,.01],[.2,.02]),'A_arithmetic_dominates')
  self.assertEqual(relation([.1,.01,.2,.1],[.2,.02,.1,.1]),'tradeoff')
 def test_rmse_delta_is_not_mean_positive_harm(self):
  self.assertAlmostEqual(signed_change([0,2],[1,1]),2**.5-1)
  self.assertNotAlmostEqual(signed_change([0,2],[1,1]),.5)
 def test_signed_help_and_tie(self):
  self.assertLess(signed_change([.01,.01],[.02,.02]),0)
  self.assertEqual(relation([1,2],[1+1e-14,2]),'arithmetic_tie')
if __name__=='__main__':unittest.main()
