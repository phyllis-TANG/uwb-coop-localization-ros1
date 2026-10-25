import copy
import json
import math
import unittest

import numpy as np

import comparison_adapter as a


def observation(t=0,car="car1",target="node_2",value=2.,source="raw",idx=0):
    return {"experiment_id":"T08","vehicle_id":car,"tag_id":a.TAGS[car],"target_id":target,
            "range_m":value,"source":source,"primary_observation":1 if source=="raw" else 0,
            "valid":1,"receive_epoch_ns":t,"record_index":idx,"link_index":0,"pairing_status":"raw_only"}


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.config=json.loads(a.CONFIG.read_text())
        self.initial={"car1":np.array([1.,1.,0.]),"car2":np.array([3.,2.,.2])}
        self.odom={c:np.zeros(3) for c in a.TAGS}

    def test_future_stale_bridge_and_ambiguous_are_not_consumed(self):
        ambiguous=dict(observation(2,idx=2),pairing_status="ambiguous_header")
        adapter=a.ArrivalAdapter([observation(0,idx=0),observation(100,idx=1),ambiguous,
                                  observation(3,source="bridge",idx=3)],max_age_ns=10)
        self.assertEqual(len(adapter.take(5)),1)
        self.assertEqual(adapter.take(50),[])
        self.assertEqual(len(adapter.take(100)),1)
        self.assertEqual(adapter.take(101),[])
        with self.assertRaisesRegex(ValueError,"monotonic"):
            adapter.take(99)

    def test_identity_and_duplicate_trace_rows_are_rejected(self):
        r=observation()
        with self.assertRaisesRegex(ValueError,"identity"):
            a.ArrivalAdapter([dict(r,tag_id="node_0")],10)
        with self.assertRaisesRegex(ValueError,"duplicate"):
            a.ArrivalAdapter([r,r],10)
        with self.assertRaisesRegex(ValueError,"one experiment"):
            a.ArrivalAdapter([r,dict(observation(idx=1),experiment_id="T10")],10)

    def test_lever_arm_rotation_and_slant_geometry(self):
        p=a.antenna(np.array([1.,2.,math.pi/2]),"car1",self.config)
        np.testing.assert_allclose(p,[1.02,2.1,.2],atol=1e-14)
        self.assertAlmostEqual(a.wall_distance(np.array([1.,2.,math.pi/2]),"car1","node_2",self.config),np.linalg.norm(p-[0.,0.,2.]))

    def test_odom_alignment_reverse_and_yaw_wrap(self):
        initial=copy.deepcopy(self.initial)
        initial["car1"][2]=math.pi/2
        method=a.FixedComparison(initial,self.odom,self.config)
        odom=copy.deepcopy(self.odom)
        odom["car1"]=np.array([-1.,0.,-.2])
        states,d=method.step(odom,[],"odom_only")
        np.testing.assert_allclose(states["car1"],[1.,0.,math.pi/2-.2],atol=1e-12)
        self.assertEqual(d["wall_factors"],0)

    def test_independent_is_invariant_to_peer_value(self):
        left=a.FixedComparison(self.initial,self.odom,self.config)
        right=a.FixedComparison(self.initial,self.odom,self.config)
        x,_=left.step(self.odom,[observation(target="node_0",value=1.)],"independent")
        y,_=right.step(self.odom,[observation(target="node_0",value=999.)],"independent")
        for c in a.TAGS:np.testing.assert_array_equal(x[c],y[c])

    def test_independent_car1_does_not_change_with_car2_wall_data(self):
        rows=[observation(value=2.8)]
        x,_=a.FixedComparison(self.initial,self.odom,self.config).step(self.odom,rows,"independent")
        rows.append(observation(car="car2",value=100.,idx=1))
        y,_=a.FixedComparison(self.initial,self.odom,self.config).step(self.odom,rows,"independent")
        np.testing.assert_array_equal(x["car1"],y["car1"])

    def test_one_wall_factor_stays_marked_underconstrained(self):
        _,d=a.FixedComparison(self.initial,self.odom,self.config).step(self.odom,[observation()],"independent")
        self.assertTrue(d["measurement_degraded"])
        self.assertEqual(d["wall_factors_by_car"],{"car1":1,"car2":0})

    def test_collinear_local_geometry_is_reported_degraded(self):
        config=copy.deepcopy(self.config)
        config["body_to_antenna_xyz_m"]={c:[0.,0.,.2] for c in a.TAGS}
        config["anchors_xyz_m"]={target:[float(i),0.,2.] for i,target in enumerate(sorted(a.WALLS))}
        initial={c:np.array([1.,0.,0.]) for c in a.TAGS}
        rows=[observation(car=c,target=target,value=a.wall_distance(initial[c],c,target,config),idx=i)
              for c in a.TAGS for i,target in enumerate(sorted(a.WALLS))]
        _,d=a.FixedComparison(initial,self.odom,config).step(self.odom,rows,"independent")
        self.assertEqual(d["wall_xy_local_rank_by_car"],{"car1":1,"car2":1})
        self.assertTrue(d["measurement_degraded"])

    def test_odometry_never_interpolates_future_and_ignores_driver_z(self):
        base={"experiment_id":"T08","vehicle_id":"car2","frame_id":"car2/odom",
            "child_frame_id":"car2/base_footprint","position_x":1.,"position_y":2.,"position_z":999.,
            "orientation_x":0.,"orientation_y":0.,"orientation_z":0.,"orientation_w":1.}
        rows=[dict(base,receive_epoch_ns=10,record_index=0),dict(base,receive_epoch_ns=30,record_index=1,position_x=999.)]
        adapter=a.OdomArrivalAdapter(rows,max_age_ns=10)
        states=adapter.take(15)
        self.assertIsNone(states["car1"])
        np.testing.assert_array_equal(states["car2"],[1.,2.,0.])
        self.assertIsNone(adapter.take(25)["car2"])
        self.assertEqual(adapter.take(30)["car2"][0],999.)

    def test_missing_links_predict_and_report_degradation(self):
        method=a.FixedComparison(self.initial,self.odom,self.config)
        x,d=method.step(self.odom,[],"joint")
        for c in a.TAGS:np.testing.assert_allclose(x[c],self.initial[c],atol=1e-12)
        self.assertTrue(d["measurement_degraded"])
        self.assertEqual(d["peer_factors"],0)

    def test_directional_peer_is_one_factor_and_changes_joint(self):
        method=a.FixedComparison(self.initial,self.odom,self.config)
        rows=[observation(target="node_0",value=1.),observation(car="car2",target="node_1",value=1.,idx=1)]
        x,d=method.step(self.odom,rows,"joint")
        self.assertEqual(d["peer_factors"],1)
        before=np.linalg.norm(a.antenna(self.initial["car1"],"car1",self.config)-a.antenna(self.initial["car2"],"car2",self.config))
        after=np.linalg.norm(a.antenna(x["car1"],"car1",self.config)-a.antenna(x["car2"],"car2",self.config))
        self.assertLess(after,before)

    def test_noiseless_fixture_reproducible_all_methods(self):
        first=a.synthetic(self.config)
        second=a.synthetic(self.config)
        self.assertEqual(first,second)
        self.assertEqual(len(first[0]),3*2*10)
        self.assertLess(max(d["synthetic_state_error_m"] for d in first[1]),1e-8)

    def test_field_configuration_cannot_be_assumed(self):
        config=copy.deepcopy(self.config)
        config["scope"]="field"
        with self.assertRaisesRegex(ValueError,"synthetic"):
            a.FixedComparison(self.initial,self.odom,config)


if __name__=="__main__":unittest.main()
