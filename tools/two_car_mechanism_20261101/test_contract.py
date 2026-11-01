"""New wrapper/storage contracts, only exposed development seed7."""
import copy
import gzip
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from support import DOC, ROOT, compact, digest, expanded_rows, protocol, write_lines
from inputs import make
from bindings import generator


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=protocol(DOC/'PROTOCOL_DEV.json')
        cls.cases={c:make(cls.p,'development',7,'static_moving',c) for c in ('nominal','car1_wall_14')}

    def test_original_cycle_and_noise_retained_over_three_periods(self):
        spec=self.cases['nominal'][4]
        old=json.loads((ROOT/'tools/two_car_sim_dev_20261101/development_static_moving.json').read_text())
        self.assertEqual(spec['noise'],old['noise'])
        self.assertEqual(spec['gyro_bias_rad_s'],old['gyro_bias_rad_s'])
        self.assertEqual(spec['duration_s'],96)
        for t in (0.,7.,16.,25.,32.,41.,63.,77.,95.):
            for car in ('car1','car2'):
                a=generator.design(t,car,spec)
                b=generator.design(t%32,car,old)
                for x,y in zip(a[0],b[0]):self.assertAlmostEqual(x,y,places=13)
                self.assertAlmostEqual(a[1],b[1],places=13)
                self.assertAlmostEqual(a[2],b[2],places=13)

    def test_actual_common_random_numbers_and_fault_support(self):
        c,e,t,l,s=self.cases['nominal']
        cf,ef,tf,lf,sf=self.cases['car1_wall_14']
        self.assertEqual(c,cf);self.assertEqual(t,tf)
        changed=0
        badbins=set()
        for a,b in zip(e,ef):
            self.assertEqual(a['source_observation_id'],b['source_observation_id'])
            self.assertEqual(a['receive_epoch_ns'],b['receive_epoch_ns'])
            self.assertFalse({'truth','labels','fault','condition'}.intersection(a))
            time=(a['header_epoch_ns']-generator.EPOCH_NS)/1e9
            active=a['kind']=='uwb' and a['vehicle_id']=='car1' and 24<=time<38
            for key,value in a['value'].items():
                if active and key in c['models']['car1']['anchors_xyz_m']:
                    self.assertAlmostEqual(b['value'][key]-value,.30,places=14)
                    changed+=1
                    badbins.update(k for k in range(1,96) if abs(k-time)<=.400000001)
                else:self.assertEqual(value,b['value'][key])
            if a['kind']!='clock':
                self.assertGreaterEqual(a['receive_epoch_ns']-a['header_epoch_ns'],10_000_000)
                self.assertLessEqual(a['receive_epoch_ns']-a['header_epoch_ns'],40_000_000)
        self.assertEqual(changed,1120)
        self.assertEqual((min(badbins),max(badbins)),(24,38))
        self.assertEqual(min(k for k in range(38,96) if k-20>max(badbins)),59)

    def test_partition_guard_and_old_guard_preserved(self):
        with self.assertRaises(ValueError):make(self.p,'test',20261101201,'static_moving','nominal')
        with self.assertRaises(ValueError):make(self.p,'development',7,'static_moving','car2_wall_14')
        spec=copy.deepcopy(self.cases['nominal'][4]);spec['seed']=20261101201
        with self.assertRaises(ValueError):generator.validate(spec)

    def test_lossless_journal_and_semantic_corruption_on_saved_real_run(self):
        archive=ROOT/'docs/research/two_car_sim_dev_20261101/artifacts/uwb-sim-imu-dev-20261101.tar.gz'
        with tarfile.open(archive) as tar:
            raw=tar.extractfile('evidence/smoke-v1/runs/nominal/M3/updates.jsonl.gz').read()
        original=[json.loads(x) for x in gzip.decompress(raw).splitlines()]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'updates.jsonl.gz'
            write_lines(path,[compact(row) for row in original])
            restored=list(expanded_rows(path))
            self.assertEqual([r['snapshot'] for r in original],[r['snapshot'] for r in restored])
            self.assertEqual(len(restored),31)
            bad=[compact(row) for row in original]
            bad[-1]=copy.deepcopy(bad[-1])
            bad[-1]['bins']['car1']['observations']['node_2']+=.01
            other=Path(td)/'bad.jsonl.gz';write_lines(other,bad)
            with self.assertRaises(ValueError):list(expanded_rows(other))


if __name__=='__main__':unittest.main(verbosity=2)
