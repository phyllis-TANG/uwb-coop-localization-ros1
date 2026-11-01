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
from analyze import summarize_frames, recovery, interval


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

    def test_metric_unknown_denominators_and_run_intervals(self):
        frames=[]
        for t in range(4):
            frames.append(dict(time_s=t,published=t>0,valid=t>=2,paired_valid=t>=2,failed=False,
                squared_error_m2=None if t==0 else [.04,.09,.01][t-1],
                delta_squared_error_vs_M2_m2=None if t==0 else [0.,.02,-.01][t-1],
                four_wall_statistic=1.+t,posterior_wall_rms_m=.1,
                unchanged_stat_error_changed=False,unchanged_stat_error_worse=False))
        r=summarize_frames(frames,0,4,1e-12)
        self.assertEqual([r[k] for k in ('window_s','finite_s','valid_s','paired_valid_s','unknown_or_invalid_s','no_publication_s','harm_duration_s')],[4,3,2,2,2,1,1])
        self.assertAlmostEqual(r['delta_mse_vs_M2_m2'],.005)
        self.assertEqual(interval([2.,2.,2.,2.]),dict(n=4,mean=2.,lo95=2.,hi95=2.,minimum=2.,maximum=2.))

    def test_recovery_first_confirmation_reexcursion_and_censoring(self):
        frames=[dict(time_s=t,paired_nominal_valid=True,paired_nominal_displacement_m=.04 if t<4 or t==10 else .01,
                     availability_cutoff_s=t+1,prior_cross_information_norm=.2,prior_affine_norm=.1) for t in range(20)]
        r=recovery(frames,4,20,.02,3,8)
        self.assertEqual((r['first_recovery_start_s'],r['first_recovery_confirm_state_s'],r['first_recovery_confirm_receipt_cutoff_s'],r['first_recovery_after_factor_exit_start_s'],r['reexcursion_or_invalid_s']),(4,6,7,11,1))
        for f in frames:f['paired_nominal_displacement_m']=.04
        self.assertTrue(recovery(frames,4,20,.02,3,8)['right_censored'])


if __name__=='__main__':unittest.main(verbosity=2)
