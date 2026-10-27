import copy
import math
import unittest

import audit


class AssociationTests(unittest.TestCase):
    def test_exact_integer_epoch_pairing_retains_nanoseconds(self):
        epoch=1792925285431466217
        o=dict(header_ns=epoch,record_index=1)
        i=dict(header_ns=epoch+2,record_index=2)
        self.assertEqual(audit.nearest_pairs([o],[i],2),[(o,i)])
        self.assertEqual(i['header_ns']-o['header_ns'],2)

    def test_beyond_tolerance_is_missing_not_interpolated(self):
        self.assertEqual(audit.nearest_pairs([dict(header_ns=0,record_index=1)],
            [dict(header_ns=2000001,record_index=2)],2000000),[])

    def test_each_imu_record_is_paired_at_most_once(self):
        odom=[dict(header_ns=100,record_index=1),dict(header_ns=101,record_index=2)]
        imu=[dict(header_ns=102,record_index=3)]
        pairs=audit.nearest_pairs(odom,imu,10)
        self.assertEqual(len(pairs),1);self.assertEqual(pairs[0][0]['record_index'],2)


class SignalTests(unittest.TestCase):
    def test_normalization_is_only_a_temporary_copy(self):
        q=dict(x=0.,y=0.,z=.7,w=.7);before=copy.deepcopy(q)
        angle,norm=audit.yaw(q)
        self.assertAlmostEqual(angle,math.pi/2);self.assertNotEqual(norm,1.)
        self.assertEqual(q,before)

    def test_constant_rate_does_not_prove_zero_correlation(self):
        result=audit.regression([0.,0.,0.],[.001,.002,.001])
        self.assertFalse(result['identifiable']);self.assertIsNone(result['correlation'])

    def test_yaw_wrap_is_not_a_spurious_full_turn(self):
        odom=[dict(header_ns=0,record_index=0,yaw=math.pi-.01,angular_velocity=dict(z=0.)),
              dict(header_ns=100000000,record_index=1,yaw=-math.pi+.01,angular_velocity=dict(z=.2))]
        imu=[dict(header_ns=r['header_ns'],record_index=r['record_index']+10,
                  angular_velocity=dict(z=.2)) for r in odom]
        result,_=audit.relation(odom,imu,1)
        self.assertAlmostEqual(result['odom_accepted_increment_sum_rad'],.02)
        self.assertAlmostEqual(result['odom_yaw_increment_minus_current_rate_dt_rad']['maximum'],0.)


if __name__=='__main__':unittest.main()
