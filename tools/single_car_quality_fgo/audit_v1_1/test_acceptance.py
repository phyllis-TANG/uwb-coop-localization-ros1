import copy
import unittest
from acceptance import expected_cells,matrix_gate,recovery,exposure

class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.protocol={'validation':{'scenarios':['normal','fault'],'seeds':[1,2]},'groups':{'Q0':'F0','Q1':'F3','Q2':'QC','Q3':'QC'}}
        self.state={'stage':'validation','status':'DONE','cells':[dict(cell_id=c,status='DONE',returncode=0) for c in sorted(expected_cells(self.protocol))],'evaluation_errors':[]}
    def test_complete(self):self.assertFalse(matrix_gate(self.state,self.protocol)[1])
    def test_empty_subset_not_complete(self):
        self.state['cells']=[];self.assertTrue(matrix_gate(self.state,self.protocol)[1])
    def test_one_missing_subset_not_complete(self):
        self.state['cells'].pop();self.assertTrue(matrix_gate(self.state,self.protocol)[1])
    def test_duplicate_replacing_missing_not_complete(self):
        self.state['cells'][-1]=copy.deepcopy(self.state['cells'][0]);self.assertTrue(matrix_gate(self.state,self.protocol)[1])
    def test_nonzero_return_or_failure_rejected(self):
        for k,v in [('returncode',1),('status','FAILED')]:
            s=copy.deepcopy(self.state);s['cells'][0][k]=v;self.assertTrue(matrix_gate(s,self.protocol)[1])
    def test_checkpoint_in_progress_rejected(self):
        self.state['status']='IN_PROGRESS';self.assertTrue(matrix_gate(self.state,self.protocol)[1])
    def test_unexpected_cell_rejected(self):
        self.state['cells'].append(dict(cell_id='extra',status='DONE',returncode=0));self.assertTrue(matrix_gate(self.state,self.protocol)[1])
    def rows(self):
        rows=[dict(publication_id=str(i),state_epoch_ns=i*10**9,policy=dict(state=mode,monitorable=known,information_multiplier=g)) for i,(mode,known,g) in enumerate([('recovering',True,.25),('normal',True,1.),('normal',True,1.),('normal',True,1.)])]
        av={r['publication_id']:dict(available_receive_epoch_ns=r['state_epoch_ns']+1_100_000_000) for r in rows};return rows,av
    def test_onset_is_not_online_confirmation(self):
        rows,av=self.rows();r=recovery(rows,av,0,True);self.assertEqual(r['recovery_onset_available_epoch_ns'],2_100_000_000);self.assertEqual(r['online_confirm_available_epoch_ns'],4_100_000_000)
    def test_incomplete_recovery_confirmation_censored(self):
        rows,av=self.rows();r=recovery(rows[:3],av,0,True);self.assertTrue(r['censored']);self.assertIsNone(r['online_confirm_available_epoch_ns'])
    def test_unknown_hold_has_separate_denominator(self):
        rows,av=self.rows();rows[1]['policy']=dict(state='unknown',monitorable=False,information_multiplier=.25);r=exposure(rows,av);self.assertEqual(r['known_link_s'],2.);self.assertEqual(r['unknown_link_s'],1.);self.assertEqual(r['known_lowered_positive_s'],1.);self.assertEqual(r['unknown_held_lowered_positive_s'],1.)

if __name__=='__main__':unittest.main(verbosity=2)
