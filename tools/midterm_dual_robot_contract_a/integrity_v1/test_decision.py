import copy
import unittest
from decision import covering_radius,decide,load,ROOT,Fraction

DOC=ROOT/'docs/research/midterm_dual_robot_contract_a'
EX=DOC/'precontract_v1/examples'


class Integrity(unittest.TestCase):
    def setUp(self):
        self.p=load(DOC/'integrity_v1/publication.json')
        self.x=load(EX/'normal.input.json')
        self.c=load(EX/'normal.composite.json')

    def run_case(self,**changes):
        return decide(dict(self.p,**changes),self.x,self.c)

    def test_offset(self):
        self.assertGreater(Fraction(self.run_case()['PL']),5)
        self.assertLess(Fraction(self.run_case(estimate_xy=['2','2'])['PL']),3)

    def test_disconnected_and_true_boundary(self):
        rectangles=[{'box':[['0','0'],['0','0']]},{'box':[['2','3'],['1','4']]}]
        radius=covering_radius(rectangles,['0','0'])
        self.assertEqual(radius,5)
        # Post-hoc only: true antenna is the far corner (3,4).
        self.assertEqual(3**2+4**2,radius**2)

    def test_round_outward(self):
        r=covering_radius([{'box':[['1','1'],['1','1']]}],['0','0'])
        self.assertGreaterEqual(r*r,2)
        self.assertLess((r-Fraction(1,10**30))**2,2)

    def test_limit_equality(self):
        row=self.run_case(AL=self.run_case()['PL'])
        self.assertTrue(row['available'])
        self.assertFalse(row['alarm'])

    def test_empty(self):
        x=load(EX/'empty.input.json')
        c=load(EX/'empty.composite.json')
        row=decide(dict(self.p,input_hash=x['input_hash'],case=x['case_id']),x,c)
        self.assertEqual(row['reason'],'EMPTY_REGION')

    def test_no_retroactive_alarm(self):
        for t,reason in [('1','NOT_READY'),('2','LATE')]:
            row=self.run_case(as_of=t,decision_ready_time='2')
            self.assertEqual(row['reason'],reason)
            self.assertFalse(row['alarm'])
            self.assertIsNone(row['PL'])

    def test_not_ready_then_timely_alarm(self):
        self.assertFalse(self.run_case(as_of='0')['alarm'])
        self.assertTrue(self.run_case(as_of='1')['alarm'])

    def test_expired(self):
        self.assertEqual(self.run_case(as_of='3')['reason'],'EXPIRED')

    def test_start(self):
        self.assertEqual(self.run_case(estimate_xy=None,published_at=None)['reason'],'NO_PUBLISHED_POSITION')

    def test_missing_or_damaged(self):
        for c,reason in [(None,'MISSING_CERTIFICATE'),({},'INVALID_CERTIFICATE_OR_INPUT')]:
            row=decide(self.p,self.x,c)
            self.assertEqual(row['reason'],reason)
            self.assertFalse(row['available'] or row['alarm'])

    def test_wrong_observation_epoch_identity(self):
        self.assertEqual(self.run_case(input_hash='stale')['reason'],'INPUT_IDENTITY')

    def test_budget_outer_and_lost_queue(self):
        x=load(EX/'normal.input.json')
        tree=copy.deepcopy(self.c['search_certificate'])
        node=tree['nodes'][0]
        node.update(kind='PENDING',box=x['domains'][:4])
        tree.update(input_hash=x['input_hash'],status='BUDGET_OUTER',queue=[node['id']])
        tree['counts'].update(UNDECIDED=0,PENDING=1)
        tree['cost']['processed_nodes']=0
        from decision import verifier
        tree['projections']=verifier('plane').PreparedInput(x).projections([node])
        row=decide(dict(self.p,AL='10'),x,tree)
        self.assertEqual(row['reason'],'WITHIN_AL_BUDGET_OUTER')
        tree['queue']=[]
        self.assertEqual(decide(self.p,x,tree)['reason'],'INVALID_CERTIFICATE_OR_INPUT')

    def test_reject_truth_fields(self):
        with self.assertRaises(ValueError):
            self.run_case(truth_xy=['1','1'])


if __name__=='__main__':
    unittest.main()
