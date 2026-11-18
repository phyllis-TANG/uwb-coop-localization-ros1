import copy
import gzip
import json
import unittest
import check


class WitnessReadback(unittest.TestCase):
    def setUp(self):
        self.w=json.loads((check.OUT/'witnesses.json').read_text())[0]['witnesses'][0]
        path=check.ROOT/'docs/research/ground_continuous_b/runs/101_nominal/records.json.gz'
        with gzip.open(path,'rt') as f:
            self.obs=next(r['obs'] for r in json.load(f) if r['t']==30)

    def test_valid(self):
        check.point(self.w,self.obs)

    def test_corruption(self):
        for field,value in [('bias_m','9/10'),('weighted_stat_strict_upper','0'),
                            ('feasible_bias_inner_m',['-3/5','3/5']),
                            ('xy_m',[['0','0'],['1','1']]),
                            ('residual_intervals_m',[['0','0']]*9)]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                bad=copy.deepcopy(self.w)
                bad[field]=value
                check.point(bad,self.obs)

if __name__=='__main__':
    unittest.main()
