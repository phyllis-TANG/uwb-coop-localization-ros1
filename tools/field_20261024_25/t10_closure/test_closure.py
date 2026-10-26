"""Fail-closed transfer, record identity and strict/exploratory separation tests."""
import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest

import common
from intake import exact_record, select_csv
from inspect_video import select_frames
from run_ready import strict_inputs, verify_bindings
import interface


def template():
    return json.loads((common.ROOT/'tools/field_20261024_25/parameter_clock_prep/results/T10_input_template.json').read_text())


class ClosureTests(unittest.TestCase):
    def test_manifest_media_only_change_allowed(self):
        old=json.loads(common.git_blob(common.OLD_COMMIT,'docs/field_tests/20261024_25/manifest.json'))
        current=json.loads((common.SESSION/'manifest.json').read_text())
        self.assertIn('assets',common.verify_manifest_compatibility(old,current))

    def test_manifest_formal_change_rejected(self):
        old=json.loads(common.git_blob(common.OLD_COMMIT,'docs/field_tests/20261024_25/manifest.json'))
        new=copy.deepcopy(old);new['formal_bags'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):common.verify_manifest_compatibility(old,new)

    def test_selected_mov_change_rejected(self):
        old=json.loads(common.git_blob(common.OLD_COMMIT,'docs/field_tests/20261024_25/manifest.json'))
        new=copy.deepcopy(old);next(r for r in new['motion_videos'] if r['experiment_id']=='T10')['sha256']='0'*64
        with self.assertRaises(ValueError):common.verify_manifest_compatibility(old,new)

    def test_wrong_attempt_rejected(self):
        t=template();t['source_bag_sha256']='0'*64
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_holdout_rejected(self):
        t=template();t['experiment_id']='T11'
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_pending_template_stays_null(self):
        t=template();before=copy.deepcopy(t);strict_inputs(t);config,ready=interface.compile_template(t)
        self.assertEqual(t,before)
        for car in ('car1','car2'):
            self.assertIsNone(config['vehicles'][car]['antenna_body_xy_m']['value'])
            self.assertTrue(ready['methods']['joint'][car])
            self.assertIsNone(t['vehicles'][car]['antenna_height_m']['uncertainty_m'])

    def test_marker_cannot_be_base(self):
        t=template();t['vehicles']['car1']['antenna_body_xy_m'].update(status='provided',value=[.07,-.13],source_kind='operator_record')
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_engineering_geometry_is_not_strict(self):
        t=template();t['vehicles']['car1']['antenna_body_xy_m'].update(status='provided',value=[.1,.1],source_kind='engineering_assumption')
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_engineering_clock_is_not_strict(self):
        t=template();t['clock_groups']['car1_ros_host'].update(status='provided',uncertainty_ns=100,source_kind='engineering')
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_zero_clock_uncertainty_is_not_evidence(self):
        t=template();t['clock_groups']['car1_ros_host'].update(status='provided',uncertainty_ns=0,source_kind='calibration')
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_zero_sample_uncertainty_rejected(self):
        t=template();t['vehicles']['car1']['sample_time_adjustments']['odom'].update(status='provided',uncertainty_ns=0,semantics='sampling')
        with self.assertRaises(ValueError):strict_inputs(t)

    def test_source_record_ns_preserved(self):
        r={'experiment_id':'T10','vehicle_id':'car1','source_file_sha256':common.BAG_SHA,'topic':'/car1/odom',
           'record_index':'3','header_epoch_ns':'1792925284331894800','receive_epoch_ns':'1792925285431505126','frame_id':'car1/odom','child_frame_id':'car1/base_footprint'}
        got=exact_record(r);self.assertEqual(got['header_epoch_ns'],1792925284331894800)
        self.assertIs(type(got['receive_epoch_ns']),int)

    def test_record_vehicle_isolation(self):
        t=template();b=t['vehicles']['car1']['initial_record_binding']
        b.update(status='provided',record_index=117,header_epoch_ns=100,receive_epoch_ns=200)
        row={'vehicle_id':'car2','source_file_sha256':common.BAG_SHA,'record_index':'117','header_epoch_ns':'100','receive_epoch_ns':'200'}
        with self.assertRaises(ValueError):verify_bindings(t,[row])

    def test_exact_record_matching(self):
        t=template();b=t['vehicles']['car1']['initial_record_binding']
        b.update(status='provided',record_index=3,header_epoch_ns=100,receive_epoch_ns=200)
        row={'vehicle_id':'car1','source_file_sha256':common.BAG_SHA,'record_index':'3','header_epoch_ns':'100','receive_epoch_ns':'200'}
        verify_bindings(t,[row]);row['header_epoch_ns']='101'
        with self.assertRaises(ValueError):verify_bindings(t,[row])

    def test_pts_sampling_is_not_frame_over_30(self):
        rows=[{'frame_index':'0','pts_ticks':'0','time_base_num':'1','time_base_den':'600'},
              {'frame_index':'30','pts_ticks':'900','time_base_num':'1','time_base_den':'600'},
              {'frame_index':'60','pts_ticks':'1201','time_base_num':'1','time_base_den':'600'}]
        self.assertEqual(select_frames(rows,[1.49])[0]['frame_index'],'30')

    def test_packet_t10_only_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'source.csv';dst=Path(td)/'selected.csv'
            src.write_text('experiment_id,source_file_sha256,record_index\nT10,'+common.BAG_SHA+',3\nT11,other,4\n')
            self.assertEqual(select_csv(src,dst,'experiment_id','T10'),1)
            self.assertEqual(len(list(csv.DictReader(dst.open()))),1)
            with self.assertRaises(FileExistsError):select_csv(src,dst,'experiment_id','T10')

    def test_new_output_required(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileExistsError):common.start(Path(td),'test')


if __name__=='__main__':unittest.main()
