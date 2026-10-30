"""Synthetic ROS Imu availability regression tests; no hardware or bags needed."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as S
from unittest.mock import patch
import inspect_bag


def message(gyro_cov=0, accel_cov=0, gyro=(0., 0., 0.), accel=(0., 0., 0.)):
    return S(orientation=S(x=0., y=0., z=0., w=1.),
             orientation_covariance=[-1] + [0] * 8,
             angular_velocity=S(**dict(zip('xyz', gyro))),
             angular_velocity_covariance=[gyro_cov] + [0] * 8,
             linear_acceleration=S(**dict(zip('xyz', accel))),
             linear_acceleration_covariance=[accel_cov] + [0] * 8,
             header=S(stamp=S(sec=0, nanosec=0), frame_id='imu'))


def screen(messages):
    class Reader:
        def __init__(self, paths):
            self.connections = [S(topic='/imu', msgtype='sensor_msgs/msg/Imu', msgcount=len(messages))]
            self.start_time = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def messages(self, **kwargs):
            for index in range(len(messages)):
                yield self.connections[0], index * 1000000000, index
        def deserialize(self, raw, msgtype): return messages[raw]
    with tempfile.TemporaryDirectory() as folder:
        bag = Path(folder) / 'synthetic.txt'
        bag.write_text('Synthetic fixture, not a ROS bag.', encoding='utf-8')
        with patch.object(inspect_bag, 'AnyReader', Reader):
            return inspect_bag.inspect(S(bag=bag, topic=['/imu'], static_start=0,
                                        static_end=len(messages)-1))['imu']['/imu']


class AvailabilityTests(unittest.TestCase):
    def test_unreported_is_not_zero_measurement(self):
        item = screen([message(-1, -1), message(-1, -1)])
        self.assertEqual(item['unreported_gyro_count'], 2)
        self.assertEqual(item['unreported_accel_count'], 2)
        self.assertEqual(item['nonfinite_gyro_accel_rows'], 0)
        result = item['operator_declared_static']
        self.assertEqual(result['valid_gyro_sample_count'], 0)
        self.assertIsNone(result['gyro_xyz_mean_deg_s'])
        self.assertIsNone(result['gyro_xyz_std_deg_s'])
        self.assertNotIn('yaw_first_to_last_deg', result)

    def test_provided_zero_with_unknown_covariance_is_valid(self):
        item = screen([message(), message()])
        self.assertEqual(item['unreported_gyro_count'], 0)
        result = item['operator_declared_static']
        self.assertEqual(result['valid_gyro_sample_count'], 2)
        self.assertEqual(result['gyro_xyz_mean_deg_s'], [0., 0., 0.])

    def test_mixed_missing_and_nonfinite_values_are_excluded(self):
        item = screen([message(-1, 0, gyro=(100., 100., 100.)),
                       message(0, -1, gyro=(1., 2., 3.)),
                       message(0, 0, gyro=(float('nan'), 0., 0.))])
        self.assertEqual(item['nonfinite_gyro_accel_rows'], 1)
        self.assertEqual(item['unreported_accel_count'], 1)
        result = item['operator_declared_static']
        self.assertEqual(result['valid_gyro_sample_count'], 1)
        self.assertAlmostEqual(result['gyro_xyz_mean_deg_s'][0], 57.29577951308232)


if __name__ == '__main__':
    unittest.main()
