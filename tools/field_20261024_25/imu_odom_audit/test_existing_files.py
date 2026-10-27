import unittest
import existing_files


def sample(index,yaw,x,rate,gyro):
    common=dict(header_ns=index*50000000,record_index=index,yaw=yaw)
    o=dict(common,position=dict(x=x,y=0.),velocity=dict(x=.1,y=0.),angular_velocity=dict(z=rate))
    i=dict(common,angular_velocity=dict(z=gyro));i['record_index']+=100
    return o,i


class RelationshipTests(unittest.TestCase):
    def test_reported_velocity_integrator_and_biased_gyro_are_distinguished(self):
        pairs=[sample(i,0.,i*.005,0.,.01) for i in range(5)]
        result=existing_files.reported_relationship(dict(odom=[p[0] for p in pairs],imu=[p[1] for p in pairs]))
        self.assertLess(result['odom_xy_current_body_velocity_step_residual_m']['rms'],1e-15)
        self.assertEqual(result['odom_yaw_current_reported_rate_step_residual_rad']['rms'],0.)
        self.assertGreater(result['odom_yaw_raw_IMU_current_rate_step_residual_rad']['rms'],0.)
        self.assertFalse(result['firmware_identified']);self.assertFalse(result['independent_sensors_proven'])

    def test_long_gap_does_not_become_an_integration_check(self):
        pairs=[sample(0,0.,0.,0.,0.),sample(10,0.,1.,0.,0.)]
        result=existing_files.reported_relationship(dict(odom=[p[0] for p in pairs],imu=[p[1] for p in pairs]))
        self.assertEqual(result['eligible_adjacent_intervals'],0)
        self.assertIsNone(result['odom_xy_current_body_velocity_step_residual_m']['rms'])


if __name__=='__main__':unittest.main()
