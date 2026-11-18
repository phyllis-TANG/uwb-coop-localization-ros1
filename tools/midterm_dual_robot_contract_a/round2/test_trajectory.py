import copy
import unittest
from trajectory import *

class Boundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=ROOT/ref.RUNTIME_DIR
        cls.cfg=json.loads((base/'geometry.json').read_bytes())
        cls.data=(base/'events.jsonl.gz').read_bytes()
        cls.frames=groups(cls.data,cls.cfg)

    def test_reference(self):
        epochs=replay(self.data,self.cfg)
        self.assertEqual(len(epochs),63)
        for c,expected in zip(epochs[9]['cars'],(.560967,.559045)):
            self.assertAlmostEqual(c['hcpl']['original'],expected,6)

    def test_rejected_values_cannot_contaminate_next_epoch(self):
        trajectories=[]
        for magnitude in (100,-100):
            f=Filter(self.cfg)
            for t in range(1,6):
                frames=copy.deepcopy(self.frames[t])
                if t in (3,4):
                    frames['car1','uwb']['value']['node_0']+=magnitude
                    before=f.transfer.copy()
                    bias=f.x[4:].copy()
                    cov=f.P.copy()
                r=f.step(t,frames)
                if t in (3,4):
                    self.assertEqual(r['action'],'REJECT')
                    np.testing.assert_array_equal(f.transfer,before)
                    np.testing.assert_array_equal(f.x[4:],bias)
                    np.testing.assert_allclose(f.P,cov+ref.Q)
            self.assertTrue(r['range_reaccepted'])
            trajectories.append(f.x)
        np.testing.assert_array_equal(*trajectories)

    def test_missing_and_late(self):
        lines=[json.loads(line) for line in gzip.decompress(self.data).splitlines()]
        for e in lines:
            if e['source_observation_id']=='car1:uwb:40':
                e['receive_epoch_ns']=e['header_epoch_ns']+NS+1
        raw=gzip.compress(b'\n'.join(json.dumps(e).encode() for e in sorted(lines,key=lambda e:e['receive_epoch_ns'])))
        eps=replay(raw,self.cfg)
        self.assertEqual(eps[1]['action'],'MISSING_RANGE')
        self.assertIsNone(eps[1]['all_arrived'])
        self.assertGreaterEqual(eps[1]['start'],3)
        self.assertTrue(eps[2]['range_reaccepted'])
        self.assertIsNone(eps[1]['cars'][0]['hcpl']['history'])

    def test_holding_expiry_and_replacement(self):
        eps=replay(self.data,self.cfg)[:2]
        eps[0]['ready']=1.05
        eps[1]['ready']=3.15
        eps[1]['cars'][0]['hcpl']['history']=.1
        rows=display(eps)[::2]
        self.assertIsNone(rows[20]['xy'])
        self.assertEqual(rows[60]['state_time'],1)
        self.assertIsNone(rows[61]['xy'])
        self.assertEqual(rows[63]['status']['history'],'AVAILABLE')
        self.assertEqual(rows[63]['xy'],eps[1]['cars'][0]['xy'])
        self.assertEqual(eps[1]['first_display'],3.15)

if __name__=='__main__':
    unittest.main()
