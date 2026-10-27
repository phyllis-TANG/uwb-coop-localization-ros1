import copy
import unittest
import numpy as np
from verify_fgo import expected_segments,check_edge,raw_adapter_check,marginal_check

class ReadbackTests(unittest.TestCase):
    def controls(self):
        return [dict(header_epoch_ns=t,receive_epoch_ns=t+1,record_index=i,source_file_sha256='a',topic='imu',rate=1.) for i,t in enumerate((0,40,80,120))]
    def test_arrival_cutoff_and_latest_left_hold(self):
        c=self.controls();p=expected_segments(c,20,100,100,50)
        self.assertEqual([(x[0],x[1],x[2],x[3]['record_index'] if x[3] else None) for x in p],[('segment',20,40,0),('segment',40,80,1),('segment',80,100,2)])
    def test_delayed_sample_and_expired_hold_create_gaps(self):
        c=self.controls();c[1]['receive_epoch_ns']=200;c[2]['receive_epoch_ns']=200
        p=expected_segments(c,20,100,100,50)
        self.assertEqual([(x[0],x[1],x[2]) for x in p],[('segment',20,50),('gap',50,100)])
    def test_future_endpoint_not_interpolated(self):
        p=expected_segments(self.controls()[1:],20,60,100,50)
        self.assertEqual([(x[0],x[1],x[2]) for x in p],[('gap',20,40),('segment',40,60)])
    def test_axis_sign_mutation_not_hidden_by_resealing(self):
        rich=[dict(kind='imu',case_id='004023',record_index=1,source_file_sha256='a',topic='imu',header_epoch_ns=1,receive_epoch_ns=2,raw_message_sha256='b',message={'angular_velocity':{'x':0,'y':0,'z':.1},'header':{'frame_id':'gyro_link'}})]
        flat=[{k:v for k,v in rich[0].items() if k!='message'}];flat[0]['value']={'angular_velocity_rad_s':[0,0,-.1],'frame_id':'gyro_link','units':'rad/s'}
        with self.assertRaisesRegex(ValueError,'real gyro'):raw_adapter_check(rich,flat)
