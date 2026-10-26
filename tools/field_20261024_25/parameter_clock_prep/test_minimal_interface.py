import copy
import json
from pathlib import Path
import sys
import unittest

import numpy as np

import interface
model=interface.model
sys.path.insert(0,str(interface.BASELINE))
import synthetic_validation


def config():return json.loads((interface.BASELINE/"synthetic_config.json").read_text())


def minimal(c):
    c=copy.deepcopy(c)
    for cc in c["vehicles"].values():
        old=cc.pop("antenna_body_xyz_m")
        base=cc.pop("base_height_m")
        cc["antenna_body_xy_m"]=dict(old,value=old["value"][:2])
        cc["antenna_height_m"]=dict(old,value=base["value"]+old["value"][2],uncertainty_m=None)
    return c


class MinimalGeometryTests(unittest.TestCase):
    def test_minimal_and_legacy_predictions_and_jacobians_match(self):
        a=config();b=minimal(a)
        model.validate_config(b)
        for car in model.CARS:
            for angle in [-3.1,-1.2,0.,2.7]:
                x=np.array([1.3,-.8,angle]);v=np.array([-.3,.02,.4])
                pa,ja=model.antenna_at(x,v,.045,a["vehicles"][car])
                pb,jb=model.antenna_at(x,v,.045,b["vehicles"][car])
                np.testing.assert_array_equal(pa,pb)
                np.testing.assert_array_equal(ja,jb)

    def test_base_height_and_lever_z_are_unidentifiable_separately(self):
        a=config();b=copy.deepcopy(a)
        b["vehicles"]["car1"]["base_height_m"]["value"]+=.7
        b["vehicles"]["car1"]["antenna_body_xyz_m"]["value"][2]-=.7
        pa,ja=model.antenna_at(np.array([1.,2.,.8]),np.zeros(3),0.,a["vehicles"]["car1"])
        pb,jb=model.antenna_at(np.array([1.,2.,.8]),np.zeros(3),0.,b["vehicles"]["car1"])
        np.testing.assert_allclose(pa,pb,atol=1e-15)
        np.testing.assert_array_equal(ja,jb)

    def test_minimal_height_removes_only_vertical_blocker(self):
        c=json.loads((interface.BASELINE/"field_config.json").read_text())
        cc=c["vehicles"]["car1"]
        cc["antenna_height_m"]={"status":"provided","value":.17,"source":"operator height","uncertainty_m":None}
        r=model.readiness(c)["independent"]["car1"]
        self.assertNotIn("car1:base_height_m:unknown",r)
        self.assertNotIn("car1:antenna_height_m:unknown",r)
        self.assertIn("car1:antenna_body_xy_m:unknown",r)
        self.assertIn("car1:initial_room_pose:unknown",r)

    def test_known_minimal_geometry_needs_no_fake_legacy_fields(self):
        c=minimal(config())
        self.assertFalse(any(v for m in model.readiness(c).values() for v in m.values()))
        self.assertNotIn("base_height_m",c["vehicles"]["car1"])
        self.assertNotIn("antenna_body_xyz_m",c["vehicles"]["car1"])

    def test_conflicting_old_and_new_values_are_rejected(self):
        for key,value in [("antenna_height_m",.99),("antenna_body_xy_m",[.99,.99])]:
            c=config();c["vehicles"]["car1"][key]={"status":"provided","value":value,"source":"conflicting record"}
            with self.assertRaisesRegex(ValueError,"conflicting"):model.validate_config(c)

    def test_unknown_uncertainty_does_not_become_zero(self):
        c=minimal(config());model.validate_config(c)
        self.assertIsNone(c["vehicles"]["car1"]["antenna_height_m"]["uncertainty_m"])

    def test_clock_pending_and_declared_signed_adjustment(self):
        self.assertEqual(interface.compile_clock({"status":"pending"},{"status":"pending"},"host")["status"],"pending")
        group={"status":"provided","source_origin_ns":100,"destination_origin_ns":200,"rate_numerator":1,"rate_denominator":1,
               "uncertainty_ns":3,"valid_source_interval_ns":[100,1000],"source":"known clock events"}
        adjustment={"status":"provided","offset_ns":-7,"uncertainty_ns":4,"source":"measured sample latency"}
        c=interface.compile_clock(group,adjustment,"host")
        self.assertEqual(model.map_time({"header_epoch_ns":110},c),203)
        self.assertEqual(c["uncertainty_ns"],7)

    def test_exact_initial_binding_is_enforced(self):
        import test_model
        c=config();row=test_model.odom()["row"]
        bind={k:row[k] for k in ("source_file_sha256","record_index","header_epoch_ns","receive_epoch_ns")}
        bind.update(status="provided",source="explicit initialization event",record_index=999)
        c["vehicles"]["car1"]["initial_record_binding"]=bind
        engine=model.Baseline("independent",c)
        self.assertEqual(engine.process({"kind":"odom","row":row})["status"],"initial_binding_mismatch")
        self.assertIsNone(engine.snapshot(row["receive_epoch_ns"])["car1"]["pose"])
        c["vehicles"]["car1"]["initial_record_binding"]["record_index"]=row["record_index"]
        self.assertEqual(model.Baseline("independent",c).process({"kind":"odom","row":row})["status"],"initialized")

    def test_calibrated_clock_interval_is_enforced_without_extrapolation(self):
        c=config();clock=c["vehicles"]["car1"]["odom_clock"]
        origin=clock["source_origin_ns"]
        clock["valid_source_interval_ns"]=[origin,origin+100]
        self.assertEqual(model.map_time({"header_epoch_ns":origin+50},clock),origin+50)
        with self.assertRaises(model.ClockIntervalError):model.map_time({"header_epoch_ns":origin+101},clock)

    def test_only_one_sensitivity_leaf_changes(self):
        import sensitivity
        c=sensitivity.minimal_synthetic_config()
        protocol=json.loads(sensitivity.PROTOCOL.read_text())
        for condition in protocol["conditions"]:
            expected=[] if condition["path"] is None else [tuple(condition["path"])]
            self.assertEqual(sensitivity.changed_leaves(c,sensitivity.perturb(c,condition)),expected)

    def test_templates_preserve_manual_height_but_not_nominal_initialization(self):
        import audit
        manifest=json.loads((audit.replay.SESSION/"manifest.json").read_text())
        geometry=json.loads((audit.replay.SESSION/"geometry.json").read_text())
        for trial,template in audit.templates(geometry,manifest,{}).items():
            c,r=interface.compile_template(template)
            self.assertIsNone(c["vehicles"]["car1"]["initial_room_pose"]["value"])
            self.assertEqual(c["vehicles"]["car1"]["antenna_height_m"]["value"],.17)
            self.assertEqual(c["vehicles"]["car2"]["antenna_height_m"]["value"],.20)
            self.assertNotIn("base_height_m",c["vehicles"]["car1"])
            self.assertEqual(c["vehicles"]["car1"]["range_clock"]["status"],"pending")
            self.assertTrue(r["methods"]["joint"]["car1"])
            if trial=="T12":self.assertEqual(template["vehicles"]["car1"]["initial_antenna_xy_room_m"]["candidate_records"][0]["value"],[None,None])

    def test_base_initialization_is_derived_only_with_complete_bound_inputs(self):
        import audit
        manifest=json.loads((audit.replay.SESSION/"manifest.json").read_text())
        geometry=json.loads((audit.replay.SESSION/"geometry.json").read_text())
        t=audit.templates(geometry,manifest,{})["T08"];cc=t["vehicles"]["car1"]
        for name,value in [("initial_antenna_xy_room_m",[1.,2.]),("initial_body_yaw_room_rad",np.pi/2),("antenna_body_xy_m",[.1,.2])]:
            cc[name].update(status="provided",value=value,source="explicit unit fixture",source_kind="engineering")
        c,r=interface.compile_template(t)
        self.assertIsNone(c["vehicles"]["car1"]["initial_room_pose"]["value"])
        cc["initial_record_binding"].update(status="provided",record_index=1,header_epoch_ns=100,receive_epoch_ns=101,source="explicit source record")
        c,r=interface.compile_template(t)
        np.testing.assert_allclose(c["vehicles"]["car1"]["initial_room_pose"]["value"],[1.2,1.9,np.pi/2],atol=1e-14)
        self.assertTrue(r["methods"]["independent"]["car1"])  # clocks remain pending

    def test_per_topic_clock_groups_do_not_force_unproven_shared_clock(self):
        import audit
        manifest=json.loads((audit.replay.SESSION/"manifest.json").read_text())
        geometry=json.loads((audit.replay.SESSION/"geometry.json").read_text())
        t=audit.templates(geometry,manifest,{})["T08"]
        t["vehicles"]["car2"]["clock_group_ids"]={"odom":"car2_ros_host","uwb":"unconfirmed_nlink_clock"}
        t["clock_groups"]["unconfirmed_nlink_clock"]={"status":"pending"}
        c,r=interface.compile_template(t)
        self.assertEqual(c["vehicles"]["car2"]["range_clock"]["source_clock_id"],"unconfirmed_nlink_clock")
        self.assertEqual(c["vehicles"]["car2"]["range_clock"]["status"],"pending")


if __name__=="__main__":unittest.main()
