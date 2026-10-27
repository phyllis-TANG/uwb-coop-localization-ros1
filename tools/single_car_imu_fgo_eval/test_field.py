import copy
import unittest
from adapt_field import adapt,config_for

class FieldTests(unittest.TestCase):
    def row(self):
        return dict(kind='imu',case_id='004023',record_index=2,source_file_sha256='a'*64,topic='/car2/imu',header_epoch_ns=1792281742000000001,receive_epoch_ns=1792281742005000001,raw_message_sha256='b'*64,message={'header':{'frame_id':'gyro_link'},'angular_velocity':dict(x=.01,y=-.02,z=.03)})
    def test_adapter_real_vector_and_exact_identity(self):
        r=self.row();out=adapt(r)
        self.assertEqual(out['value']['angular_velocity_rad_s'],[.01,-.02,.03]);self.assertEqual(out['header_epoch_ns'],r['header_epoch_ns']);self.assertEqual(out['raw_message_sha256'],r['raw_message_sha256'])
    def test_adapter_does_not_normalize_sign_or_units(self):
        r=self.row();r['message']['angular_velocity']['z']=-.03
        self.assertEqual(adapt(r)['value']['angular_velocity_rad_s'][2],-.03)
    def test_adapter_refuses_float_epoch(self):
        for key in ('receive_epoch_ns','header_epoch_ns','record_index'):
            r=self.row();r[key]=float(r[key])
            with self.assertRaises(ValueError):adapt(r)
    def test_declared_unknown_physics_not_zero_error(self):
        legacy={k:{} for k in ('model','replay','optimizer','frontend')};template={'angular':{'body_z_in_imu_frame':{},'imu_frame_id':{},'bias_initial_rad_s':{'value':0}},'clock_maps':{},'assumptions':[]}
        protocol=dict(A_commit='test',axis_hypothesis=[0,0,1],clock_API_disclosure_scale_ns=100000000)
        configs=[config_for(template,legacy,a,'gyro_link',protocol) for a in ('F0','F1','F2','F3')]
        for c in configs:
            self.assertIn('not verified',c['angular']['body_z_in_imu_frame']['source'])
            self.assertIn('NOT a physical error bound',c['clock_maps']['imu']['source'])
            self.assertEqual(c['clock_maps']['imu']['value']['uncertainty_ns'],100000000)
        copies=copy.deepcopy(configs)
        for c in copies:c.pop('arm')
        self.assertTrue(all(c==copies[0] for c in copies))
