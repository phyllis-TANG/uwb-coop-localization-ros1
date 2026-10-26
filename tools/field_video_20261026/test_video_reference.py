import tempfile
from pathlib import Path
import unittest
import cv2
import numpy as np
import common
import download_ranges
import observations
import time_events
import event_sync
import background_geometry
import manual_timing


class Coordinates(unittest.TestCase):
    def test_rotation_matches_actual_pixel_arrays(self):
        im=np.arange(4*7).reshape(4,7).astype(np.uint8)
        for angle,k in [(0,0),(90,1),(-90,3),(180,2)]:
            H,size=common.encoded_to_display(7,4,angle)
            rotated=np.rot90(im,k)
            self.assertEqual((rotated.shape[1],rotated.shape[0]),size)
            for y in range(4):
                for x in range(7):
                    q=common.transform_pixels([[x,y]],H)[0].round().astype(int)
                    self.assertEqual(rotated[q[1],q[0]],im[y,x])

    def test_rotation_round_trip(self):
        q=np.array([[0,0],[3839,2159],[100.25,900.7]])
        H,_=common.encoded_to_display(3840,2160,-90)
        np.testing.assert_allclose(common.transform_pixels(common.transform_pixels(q,H),np.linalg.inv(H)),q)

    def test_unhandled_rotation_rejected(self):
        with self.assertRaises(ValueError):common.encoded_to_display(100,50,37)

    def test_actual_not_nominal_marker_size(self):
        q=common.marker_object_points()
        self.assertAlmostEqual(np.linalg.norm(q[1]-q[0]),.144)
        self.assertNotAlmostEqual(np.linalg.norm(q[1]-q[0]),.15)

    def test_camera_to_room_direction_and_raised_plane(self):
        # Camera 2m above floor, looking down. Same pixel hits different XY at board height.
        T=np.eye(4);T[:3,:3]=np.diag([1,-1,-1]);T[:3,3]=[1,2,2]
        K=np.array([[1000,0,500],[0,1000,300],[0,0,1]],float)
        floor=common.intersect_room_plane([1000,300],K,np.zeros(5),T,0)
        board=common.intersect_room_plane([1000,300],K,np.zeros(5),T,.37)
        np.testing.assert_allclose(floor,[2,2,0]);np.testing.assert_allclose(board,[1.815,2,.37])
        self.assertGreater(abs(floor[0]-board[0]),.18)

    def test_plane_behind_camera_rejected(self):
        with self.assertRaises(ValueError):common.intersect_room_plane([0,0],np.eye(3),np.zeros(5),np.eye(4),-1)

    def test_nominal_room_pose_direction(self):
        room=np.array([[2,2,0],[3,2,0],[2,4,0],[3,4,0]],float)
        R=np.diag([1.,-1.,-1.]);center=np.array([2.5,3.,2.])
        K=np.array([[1200.,0,1000],[0,1200,600],[0,0,1.]])
        rv=cv2.Rodrigues(R)[0];tv=-R@center
        pixels=cv2.projectPoints(room,rv,tv,K,np.zeros(5))[0].reshape(-1,2)
        result=background_geometry.room_pose(pixels,room,K,np.zeros(5))
        recovered=np.array(result['T_room_camera'])
        np.testing.assert_allclose(recovered[:3,3],center,atol=1e-6)
        np.testing.assert_allclose(recovered[:3,:3],R.T,atol=1e-6)

    def test_body_offset_rotates_before_room_translation(self):
        result=common.antenna_from_body_offset([2,3,.37],np.pi/2,[.07,-.13,-.20])
        np.testing.assert_allclose(result,[2.13,3.07,.17])
        with self.assertRaises(ValueError):common.antenna_from_body_offset([2,3,.37],None,[.07,-.13,-.20])


class Contracts(unittest.TestCase):
    def test_strict_json_cannot_hide_nan(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):common.write_json(Path(tmp)/'bad.json',{'x':float('nan')})

    def test_output_cannot_overwrite_an_existing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'x.json';common.write_json(p,{'x':1})
            with self.assertRaises(FileExistsError):common.write_json(p,{'x':2})

    def test_tracking_never_claims_decoded_detection(self):
        r=observations.row_state({},1,np.zeros((4,2)),'lk_manual_seed_v1')
        self.assertEqual(r['detected'],0);self.assertEqual(r['tracked'],1)
        self.assertEqual(r['observation_status'],'tracked')

    def test_failed_row_preserves_missing_not_zero_corners(self):
        r=observations.row_state({},1,None,'failed_v1',{'reason':'out_of_frame'})
        self.assertNotIn('corner0_x_px',r);self.assertEqual(r['invalid_reason'],'out_of_frame')

    def test_synthetic_decoded_marker_identity(self):
        import json
        config=json.loads(Path(observations.__file__).with_name('observation_config.json').read_text())
        im=np.full((500,800),255,np.uint8)
        dictionary=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
        im[100:340,100:340]=cv2.aruco.generateImageMarker(dictionary,0,240)
        im[100:340,450:690]=cv2.aruco.generateImageMarker(dictionary,1,240)
        found,_=observations.decode(im,observations.detectors(config))
        self.assertEqual(set(found),{0,1})

    def test_range_response_exact_identity(self):
        download_ranges.validate_range('HTTP/1.1 206\r\nContent-Range: bytes 10-19/100\r\n',10,10,19,100)
        for header,n in [('Content-Range: bytes 0-9/100\r\n',10),('Content-Range: bytes 10-19/99\r\n',10),('Content-Range: bytes 10-19/100\r\n',9),('HTTP/1.1 200\r\n',10)]:
            with self.assertRaises(ValueError):download_ranges.validate_range(header,n,10,19,100)


class Timing(unittest.TestCase):
    def test_event_offset_and_drift_recovered_without_positions(self):
        t=np.array([1,20,40,62.]);r=time_events.fit_events(t,1.0002*t+12.3,np.ones(4)*.2)
        self.assertAlmostEqual(r['a'],1.0002,places=8);self.assertAlmostEqual(r['b_relative_s'],12.3,places=8)

    def test_two_events_cannot_validate_drift(self):
        with self.assertRaises(ValueError):time_events.fit_events([1,30],[10,39],[.1,.1])

    def test_short_event_span_rejected(self):
        with self.assertRaises(ValueError):time_events.fit_events([1,2,3],[11,12,13],[.1,.1,.1])

    def test_missing_events_not_fabricated(self):
        self.assertEqual(time_events.intervals([0,1,2],[False]*3),[])

    def test_real_observation_boundaries(self):
        r=time_events.intervals(np.arange(0,2,.1),[False]*3+[True]*10+[False]*7,bridge_gap=.2)[0]
        np.testing.assert_allclose(r['start_bracket_s'],[.2,.3]);np.testing.assert_allclose(r['end_bracket_s'],[1.2,1.3])

    def test_no_video_events_does_not_forge_sync(self):
        r=event_sync.align([],[])
        self.assertIsNone(r['model']);self.assertEqual(r['status'],'pending')

    def test_candidate_event_fit_is_not_approved_clock_sync(self):
        v=[dict(vehicle_id='car1',kind='motion_start',time_s=10),
           dict(vehicle_id='car1',kind='motion_end',time_s=30),
           dict(vehicle_id='car2',kind='motion_end',time_s=60)]
        r=[dict(x,time_s=x['time_s']+5) for x in v]
        fit=event_sync.align(v,r)
        self.assertAlmostEqual(fit['candidate_model']['a'],1.,places=8)
        self.assertAlmostEqual(fit['candidate_model']['b_relative_s'],5.,places=8)
        self.assertFalse(fit['accepted_for_continuous_reference']);self.assertIsNone(fit['model'])

    def test_matching_never_reuses_one_odom_event(self):
        v=[dict(vehicle_id='car1',kind='motion_start',time_s=10)]*2
        r=[dict(vehicle_id='car1',kind='motion_start',time_s=15)]
        self.assertEqual(len(event_sync.pair_at_offset(v,r,5)),1)

    def test_visibility_recovery_is_not_a_motion_onset(self):
        rows=[]
        for i,t in enumerate(np.arange(0,12,.5)):
            valid=t>=4
            center_x=(t-4)*10 if t<8 else 40
            row=dict(video_time_s=str(t),vehicle_id='car2',observation_status='tracked' if valid else 'failed')
            if valid:
                for k,(x,y) in enumerate([(0,0),(10,0),(10,10),(0,10)]):
                    row[f'corner{k}_x_px']=str(x+center_x);row[f'corner{k}_y_px']=str(y)
            rows.append(row)
        result=event_sync.image_motion(rows)
        self.assertFalse(any(e['kind']=='motion_start' for e in result['events']))
        self.assertTrue(any(e['kind']=='motion_end' for e in result['events']))

    def test_single_boundary_cannot_pick_one_repeated_stage(self):
        video=[dict(vehicle_id='car2',kind='motion_end',time_s=150)]
        ros=[dict(vehicle_id='car2',kind='motion_end',time_s=t) for t in [90,110,140]]
        result=event_sync.align(video,ros)
        self.assertEqual(result['status'],'pending_single_event_stage_ambiguity')
        self.assertIsNone(result['candidate_model']);self.assertEqual(len(result['candidate_offset_family']),3)

    def test_cropped_flow_preserves_global_pixel_coordinates(self):
        rng=np.random.default_rng(42);im=rng.integers(0,255,(600,900),dtype=np.uint8)
        q=np.float32([[300,200],[450,200],[450,350],[300,350]])
        moved=cv2.warpAffine(im,np.float32([[1,0,4],[0,1,3]]),(900,600))
        pts=manual_timing.cropped_features(im,q)
        cfg=dict(minimum_inliers=8,forward_backward_threshold_px=1.5,ransac_threshold_px=2.,minimum_inlier_fraction=.6)
        predicted,diagnostic=manual_timing.cropped_track(im,moved,pts,q,cfg)
        self.assertIsNotNone(predicted);np.testing.assert_allclose(predicted,q+[4,3],atol=.15)


if __name__=='__main__':unittest.main()
