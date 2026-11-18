"""Check the archived startup, corruption rejection and the reported missed alarm."""
import copy
import csv
import gzip
import unittest
from audit import validate
from timeline import DOC,load
from a_interface import check_radius
from handoff import packet


class GroundEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record=load(DOC/'runs/101_nominal/records.json.gz')[24]

    def test_missing_joint_pair(self):
        r=copy.deepcopy(self.record)
        r['region']['joint'][0][1].pop()
        with self.assertRaises(AssertionError):validate(r)

    def test_omitted_anchor_cell(self):
        r=copy.deepcopy(self.record)
        r['region']['cells'][0].pop()
        with self.assertRaises(AssertionError):validate(r)

    def test_clipped_root(self):
        r=copy.deepcopy(self.record)
        r['region']['roots'][0][0][0]+=1
        with self.assertRaises(AssertionError):validate(r)

    def test_undersized_pl(self):
        r=copy.deepcopy(self.record)
        r['region']['pl'][1]-=.001
        with self.assertRaises(AssertionError):check_radius(r)

    def test_ground_frame(self):
        p=packet(2026111901,'wall',29,'p')
        self.assertEqual(p['A_height_validation'],'UNSUPPORTED_FRAME_OR_DOMAIN')
        self.assertFalse(p['full_A_ground_accepted'])

    def test_archived_example(self):
        with gzip.open(DOC/'runs/2026111901_wall/ticks.csv.gz','rt') as f:
            rows=[r for r in csv.DictReader(f) if r['view']=='delivery' and r['car']=='1' and r['method']=='B2' and r['AL_m']=='0.1']
        self.assertEqual(len(rows),1280)
        self.assertEqual(rows[0]['status'],'STARTUP')
        last=rows[620]
        self.assertEqual((last['time_s'],last['state_s'],last['status']),('31.0','29','AVAILABLE'))
        self.assertAlmostEqual(float(last['error_m']),.2605951721363497)
        self.assertEqual(rows[621]['status'],'EXPIRED')


if __name__=='__main__':unittest.main()
