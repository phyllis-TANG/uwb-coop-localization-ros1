import copy
import json
import math
from pathlib import Path
import unittest

import numpy as np

import model

ORIGIN = 1792925285431466217


def config():
    return json.loads(Path(__file__).with_name("synthetic_config.json").read_text())


def odom(car="car1", offset=0, receive_offset=None, pose=(0.,0.,0.), index=0, twist=(0.,0.,0.)):
    row = dict(experiment_id="synthetic", vehicle_id=car, source_file_sha256="f"*64,
        record_index=index, receive_epoch_ns=ORIGIN+(offset+5_000_000 if receive_offset is None else receive_offset),
        header_epoch_ns=ORIGIN+offset, frame_id=car+"/odom", child_frame_id=car+"/base_footprint",
        position_x=pose[0], position_y=pose[1], position_z=-888.,
        orientation_x=0., orientation_y=0., orientation_z=math.sin(pose[2]/2), orientation_w=math.cos(pose[2]/2),
        linear_x=twist[0], linear_y=twist[1], angular_z=twist[2])
    return {"kind":"odom", "row":row}


def range_event(car="car1", target="node_2", offset=10_000_000, receive_offset=None, value=3., index=100, li=0):
    row = dict(experiment_id="synthetic", vehicle_id=car, source_file_sha256="f"*64,
        record_index=index, link_index=li, receive_epoch_ns=ORIGIN+(offset+12_000_000 if receive_offset is None else receive_offset),
        header_epoch_ns=ORIGIN+offset, tag_id=model.TAGS[car], target_id=target,
        source="raw", primary_observation=1, valid=1, range_m=value,
        raw_frame_id="frame:"+str(index), bridge_frame_id="bridge:"+str(index), pairing_status="paired_equal")
    return {"kind":"range", "row":row}


def initialized(method="joint", cfg=None):
    engine=model.Baseline(method, cfg or config())
    engine.process(odom(index=0))
    engine.process(odom("car2",index=1))
    return engine


class GeometryTests(unittest.TestCase):
    def test_nonzero_heading_reverse_and_relative_odom_frame(self):
        state=np.array([2.,3.,math.pi/2])
        old=np.array([10.,-2.,.7])
        local=model.rotation(.7)@np.array([-1.,0.])
        new=np.r_[old[:2]+local,.7]
        result,_=model.compose_odom(state,old,new)
        np.testing.assert_allclose(result,[2.,2.,math.pi/2],atol=1e-12)

    def test_yaw_crosses_both_sides_without_two_pi_jump(self):
        for sign in (1,-1):
            old=np.array([0.,0.,sign*math.radians(179)])
            new=np.array([0.,0.,-sign*math.radians(179)])
            result,_=model.compose_odom(np.array([0.,0.,.3]),old,new)
            self.assertAlmostEqual(result[2],.3+sign*math.radians(2))

    def test_rotated_lever_and_slant_not_horizontal(self):
        cc=config()["vehicles"]["car1"]
        point,jac=model.antenna_at(np.array([1.,2.,math.pi/2]),np.zeros(3),0.,cc)
        np.testing.assert_allclose(point,[1.12,2.22,.19],atol=1e-14)
        self.assertGreater(np.linalg.norm(point-[0.,0.,2.]),np.linalg.norm(point[:2]))

    def test_asynchronous_projection_jacobian_matches_numeric(self):
        cc=config()["vehicles"]["car2"]
        state=np.array([1.2,2.3,-2.7]);twist=np.array([-.3,.02,.4])
        _,jac=model.antenna_at(state,twist,.045,cc)
        numeric=np.zeros((3,3))
        for k in range(3):
            d=np.zeros(3);d[k]=1e-6
            numeric[:,k]=(model.antenna_at(state+d,twist,.045,cc)[0]-model.antenna_at(state-d,twist,.045,cc)[0])/2e-6
        np.testing.assert_allclose(jac,numeric,atol=3e-10)

    def test_zero_angular_rate_limit(self):
        a=model.twist_translation(np.array([-.3,.05,0.]),.2)
        b=model.twist_translation(np.array([-.3,.05,1e-10]),.2)
        np.testing.assert_allclose(a,[-.06,.01],atol=1e-14)
        np.testing.assert_allclose(a,b,atol=1e-11)


class ClockAndReadinessTests(unittest.TestCase):
    def test_exact_integer_affine_clock_at_epoch_and_negative_delta(self):
        c=config()["vehicles"]["car1"]["odom_clock"]
        c.update(source_origin_ns=ORIGIN,destination_origin_ns=ORIGIN+19,rate_numerator=3,rate_denominator=2)
        self.assertEqual(model.map_time({"header_epoch_ns":ORIGIN+7},c),ORIGIN+30)
        self.assertEqual(model.map_time({"header_epoch_ns":ORIGIN-7},c),ORIGIN+8)

    def test_unknown_field_values_block_room_but_allow_local_odom(self):
        field=json.loads(Path(__file__).with_name("field_config.json").read_text())
        model.validate_config(field)
        r=model.readiness(field)
        self.assertFalse(r["odom_only"]["car1"])
        self.assertIn("car1:antenna_body_xyz_m:unknown",r["independent"]["car1"])
        self.assertIn("car2:range_clock:unknown",r["joint"]["car1"])

    def test_visual_reference_absence_does_not_block_known_models(self):
        self.assertFalse(any(b for method in model.readiness(config()).values() for b in method.values()))

    def test_independent_vehicle_readiness_is_not_coupled(self):
        c=config();c["vehicles"]["car2"]["initial_room_pose"]["value"]=None
        r=model.readiness(c)
        self.assertFalse(r["independent"]["car1"])
        self.assertTrue(r["independent"]["car2"])
        self.assertTrue(r["joint"]["car1"])

    def test_synthetic_parameters_cannot_be_relabelled_as_field(self):
        c=config();c["scope"]="field"
        with self.assertRaisesRegex(ValueError,"synthetic parameter"):model.validate_config(c)

    def test_invalid_covariance_or_weight_is_rejected(self):
        c=config();c["weights"]["peer_sigma_m"]["value"]=0.
        with self.assertRaisesRegex(ValueError,"fixed weight"):model.validate_config(c)
        c=config();c["vehicles"]["car1"]["initial_covariance_diagonal"]["value"][0]=-1.
        with self.assertRaisesRegex(ValueError,"covariance"):model.validate_config(c)


class CausalFilterTests(unittest.TestCase):
    def test_uninitialized_is_null_not_zero(self):
        state=model.Baseline("joint",config()).snapshot(ORIGIN)
        self.assertIsNone(state["car1"]["pose"])
        self.assertFalse(state["car1"]["valid"])

    def test_invalid_quaternion_does_not_initialize_zero_yaw(self):
        engine=model.Baseline("joint",config())
        e=odom();e["row"]["orientation_w"]=0.
        self.assertEqual(engine.process(e)["status"],"invalid_odometry")
        self.assertIsNone(engine.snapshot(ORIGIN+10_000_000)["car1"]["pose"])

    def test_reverse_peer_is_logged_with_own_time_and_never_averaged(self):
        engine=initialized()
        first=engine.process(range_event(target="node_0",value=2.8))
        self.assertEqual(first["status"],"peer_updated")
        before=engine.x.copy();cov=engine.P.copy()
        reverse=engine.process(range_event("car2","node_1",offset=30_000_000,value=999.,index=101))
        self.assertEqual(reverse["status"],"excluded_correlated_reverse_direction")
        self.assertEqual(reverse["measurement_epoch_ns"],ORIGIN+30_000_000)
        np.testing.assert_array_equal(before,engine.x)
        np.testing.assert_array_equal(cov,engine.P)

    def test_peer_projects_both_vehicles_to_one_directed_measurement_time(self):
        engine=initialized()
        engine.process(odom("car2",offset=20_000_000,pose=(.02,0.,.1),index=5,twist=(.3,0.,.1)))
        e=range_event(target="node_0",offset=40_000_000,value=3.)
        expected=[]
        for car,age in [("car1",.04),("car2",.02)]:
            expected.append(model.antenna_at(engine.x[engine._slice(car)],engine.twist[car],age,engine.config["vehicles"][car])[0])
        d=engine.process(e)
        self.assertAlmostEqual(d["expected_range_m"],np.linalg.norm(expected[0]-expected[1]))
        self.assertEqual(d["support_age_ns"],{"car1":40_000_000,"car2":20_000_000})

    def test_independent_peer_and_other_vehicle_are_isolated(self):
        one=initialized("independent");two=initialized("independent")
        one.process(range_event(value=2.8))
        two.process(range_event(value=2.8))
        two.process(range_event("car2",value=88.,offset=30_000_000,index=102))
        d=two.process(range_event(target="node_0",offset=40_000_000,value=999.,index=103))
        self.assertEqual(d["status"],"excluded_independent_peer")
        np.testing.assert_array_equal(one.x[:3],two.x[:3])
        np.testing.assert_array_equal(one.P[:3,:3],two.P[:3,:3])

    def test_trace_and_bridge_duplicates_do_not_halve_covariance(self):
        engine=initialized("independent");event=range_event()
        engine.process(event)
        before=engine.P.copy()
        self.assertEqual(engine.process(event)["status"],"duplicate_trace")
        bridge=copy.deepcopy(event);bridge["row"].update(record_index=999,source="bridge",primary_observation=0)
        self.assertEqual(engine.process(bridge)["status"],"excluded_bridge_duplicate")
        np.testing.assert_array_equal(before,engine.P)

    def test_same_header_different_trace_and_fixed_rate_are_explicit(self):
        engine=initialized("independent")
        engine.process(range_event())
        self.assertEqual(engine.process(range_event(index=101))["status"],"duplicate_or_out_of_order_link_time")
        self.assertEqual(engine.process(range_event(offset=40_000_000,index=102))["status"],"excluded_fixed_rate_thinning")

    def test_late_range_and_out_of_order_odometry_are_rejected(self):
        engine=initialized()
        engine.process(odom(offset=50_000_000,index=4))
        self.assertEqual(engine.process(range_event(offset=10_000_000,receive_offset=80_000_000))["status"],"measurement_before_odometry_anchor:car1")
        self.assertEqual(engine.process(odom(offset=20_000_000,receive_offset=90_000_000,index=5))["status"],"duplicate_or_out_of_order_odometry")

    def test_future_measurement_time_and_stale_peer_support(self):
        engine=initialized()
        self.assertEqual(engine.process(range_event(offset=40_000_000,receive_offset=30_000_000))["status"],"future_measurement_time")
        self.assertEqual(engine.process(range_event(target="node_0",offset=90_000_000,index=104))["status"],"stale_odometry_support:car1")

    def test_car2_disconnect_does_not_block_car1_wall_update(self):
        engine=initialized()
        engine.process(odom(offset=300_000_000,index=4))
        peer=engine.process(range_event(target="node_0",offset=310_000_000,index=105))
        self.assertEqual(peer["status"],"stale_odometry_support:car2")
        wall=engine.process(range_event(offset=320_000_000,index=106))
        self.assertEqual(wall["status"],"wall_updated")
        self.assertFalse(engine.snapshot(ORIGIN+350_000_000)["car2"]["valid"])

    def test_collinear_wall_geometry_stays_degraded(self):
        c=config()
        c["anchors_xyz_m"]["value"]={t:[float(i),0.,2.] for i,t in enumerate(model.WALLS)}
        for car in model.CARS:
            c["vehicles"][car]["antenna_body_xyz_m"]["value"]=[0.,0.,.2]
            c["vehicles"][car]["initial_room_pose"]["value"]=[1.,0.,0.]
        engine=initialized("independent",c)
        for i,target in enumerate(model.WALLS):
            distance=float(np.linalg.norm(np.array([1.,0.,.2])-np.array(c["anchors_xyz_m"]["value"][target])))
            self.assertEqual(engine.process(range_event(target=target,value=distance,index=100+i))["status"],"wall_updated")
        s=engine.snapshot(ORIGIN+40_000_000)["car1"]
        self.assertEqual(s["wall_xy_local_rank"],1)
        self.assertTrue(s["geometry_degraded"])

    def test_nonfinite_range_is_null_in_strict_json_audit(self):
        engine=initialized()
        d=engine.process(range_event(value=float("nan")))
        self.assertEqual(d["status"],"invalid_range")
        self.assertIsNone(d["range_m"])
        json.dumps(d,allow_nan=False)

    def test_numerical_failure_preserves_pose_and_marks_fallback(self):
        engine=initialized()
        before=engine.x.copy()
        engine.P[0,0]=float("nan")
        d=engine.process(range_event())
        self.assertEqual(d["status"],"numerical_range_failed_hold")
        np.testing.assert_array_equal(before,engine.x)
        s=engine.snapshot(ORIGIN+40_000_000)["car1"]
        self.assertFalse(s["valid"])
        self.assertEqual(s["fallback_status"],"numerical_update_failed_hold")

    def test_source_local_odom_keeps_original_frame_z_and_unmapped_clock(self):
        c=json.loads(Path(__file__).with_name("field_config.json").read_text())
        engine=model.Baseline("odom_only",c)
        e=odom(pose=(10.,-2.,2.4));e["row"]["header_epoch_ns"]+=1_000_000_000
        self.assertEqual(engine.process(e)["status"],"initialized")
        s=engine.snapshot(ORIGIN+10_000_000)["car1"]
        np.testing.assert_allclose(s["pose"],[10.,-2.,2.4])
        self.assertEqual(s["frame_id"],"car1/odom")
        self.assertIsNone(s["state_epoch_ns"])
        self.assertIsNone(s["covariance"])
        self.assertFalse(s["time_model_provided"])


if __name__=="__main__":unittest.main()
