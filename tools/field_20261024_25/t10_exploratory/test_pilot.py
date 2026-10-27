import copy
import json
import math
import unittest

import numpy as np
import pilot


class PilotChecks(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(pilot.PROTOCOL.read_text())
        self.origin = 1000000000000000000
        self.odom = [dict(vehicle_id=c, header_epoch_ns=str(self.origin+2010000000),
            receive_epoch_ns=str(self.origin+2030000000), record_index=str(i+1))
            for i,c in enumerate(pilot.model.CARS)]
        self.ranges = [dict(r, header_epoch_ns=str(self.origin+2020000000)) for r in self.odom]

    def config(self, profile=0):
        return pilot.configuration(self.protocol, self.protocol['profiles'][profile], self.odom, self.ranges, self.origin)

    def test_exact_three_dimensional_slant_ranges_recover_antenna_xy(self):
        anchors={'node_2':[5.,5.,2.7], 'node_3':[5.,2.,2.4], 'node_8':[0.,2.,2.3], 'node_10':[3.,0.,2.4]}
        for p,h in [(np.array([1.,2.]),.17),(np.array([4.,1.]),.20),(np.array([3.,3.]),.17)]:
            ranges=[np.linalg.norm(np.r_[p,h]-a) for a in anchors.values()]
            result=pilot.uwb_solution(anchors,list(anchors),ranges,h)
            self.assertTrue(result.success)
            np.testing.assert_allclose(result.x,p,atol=1e-7)

    def test_initial_antenna_preserved_when_base_lever_changes(self):
        for profile in range(7):
            config=self.config(profile)
            for car in pilot.model.CARS:
                cc=config['vehicles'][car]
                computed=pilot.antenna_xy(cc['initial_room_pose']['value'],cc['antenna_body_xy_m']['value'])
                np.testing.assert_allclose(computed,self.protocol['nominal_antenna_xy_m'][car],atol=1e-14)

    def test_every_physical_unknown_is_explicit_assumption(self):
        config=self.config()
        self.assertFalse(config['strict_field_acceptance'])
        for car in pilot.model.CARS:
            for field in ['initial_room_pose','antenna_body_xy_m','odom_clock','range_clock']:
                self.assertEqual(config['vehicles'][car][field]['source_kind'],'engineering_assumption')
            self.assertIn('NOT_calibrated_bound',config['vehicles'][car]['odom_clock']['uncertainty_role'])
        self.assertTrue(all(v is None for k,v in self.protocol['evaluation'].items() if k!='reference_scope'))

    def test_clock_adjustment_preserves_integer_nanoseconds(self):
        config=self.config(6)
        clock=config['vehicles']['car2']['odom_clock']
        row={'header_epoch_ns':self.origin+2010000001}
        clock['valid_source_interval_ns']=[self.origin,self.origin+10000000000]
        self.assertEqual(pilot.model.map_time(row,clock),row['header_epoch_ns'])
        self.assertEqual(self.config()['vehicles']['car1']['odom_clock']['destination_origin_ns'],self.origin-20000000)

    def test_holdout_and_wrong_attempt_refused(self):
        for key,value in [('experiment_id','T11'),('bag_sha256','0'*64)]:
            saved=copy.deepcopy(self.protocol);self.protocol[key]=value
            with self.assertRaises(ValueError):self.config()
            self.protocol=saved

    def test_original_strict_inputs_remain_unprovided(self):
        self.config()
        old=json.loads((pilot.ROOT/'docs/field_tests/20261024_25/t10_closure_20261027/results/T10_strict_baseline_config.json').read_text())
        self.assertTrue(pilot.model.readiness(old)['joint']['car1'])
        for car in pilot.model.CARS:
            self.assertIsNone(old['vehicles'][car]['initial_room_pose']['value'])
            self.assertIsNone(old['vehicles'][car]['antenna_body_xy_m']['value'])


if __name__=='__main__':unittest.main()
