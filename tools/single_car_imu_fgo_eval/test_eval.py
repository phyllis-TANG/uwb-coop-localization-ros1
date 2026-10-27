import copy
import dataclasses
import math
import unittest
import numpy as np

from prepare import plain,legacy_view
from verify_packets import equal_raw
from verify_baseline import compare_publications,interpolate
from audit_contract import heading_sources,dependency_cutoff,marginal_prior,factor_accounting,coverage
from diagnose import interval_coverage


class EvalTests(unittest.TestCase):
    def test_integer_epoch_not_float(self):
        value=1792925285431505126
        self.assertIs(type(plain(np.int64(value))),int);self.assertEqual(plain(np.int64(value)),value)

    def test_nonfinite_preserved_with_reason(self):
        issues=[];self.assertEqual(plain([float('nan'),float('inf')],'gyro',issues),[None,None]);self.assertEqual(len(issues),2)
        with self.assertRaises(ValueError):equal_raw(0.,float('nan'))

    def test_gyro_sign_and_units_mutations_caught(self):
        raw={'angular_velocity':{'z':.12}}
        equal_raw(copy.deepcopy(raw),raw)
        for wrong in (-.12,.12*180/math.pi):
            with self.assertRaises(ValueError):equal_raw({'angular_velocity':{'z':wrong}},raw)

    def test_covariance_and_exact_integer_mutations(self):
        with self.assertRaises(ValueError):equal_raw({'cov':[0,0]},{'cov':[0,0,0]})
        with self.assertRaises(ValueError):equal_raw(1792925285431505126.,1792925285431505126)

    def test_actual_imu_versus_legacy_placeholder(self):
        row={'kind':'imu','message':{'angular_velocity':{'z':.1}},'receive_relative_s':.5,'header_relative_s':.4}
        old=legacy_view(row);self.assertIsNone(old['value']);self.assertIsNone(old['header_s']);self.assertEqual(row['message']['angular_velocity']['z'],.1)

    def test_duplicate_UWB_source_entries_retained(self):
        r={'kind':'uwb','receive_relative_s':1.,'header_relative_s':.9,'message':{'ranges':[{'anchor_id':'a','range':2.},{'anchor_id':'a','range':3.},{'anchor_id':'b','range':4.}]}}
        self.assertEqual(legacy_view(r)['value'],{'b':4.});self.assertEqual(len(r['message']['ranges']),3)

    def test_raw_message_covariance_numeric_check(self):
        with self.assertRaises(ValueError):equal_raw({'cov':[1.,0.]},{'cov':[0.,0.]})

    def test_interpolation_only_uses_given_arrived_bracket(self):
        available=[{'header_s':0.,'received_s':0.,'value':[0.,0.,0.]}, {'header_s':2.,'received_s':3.,'value':[2.,4.,1.]}]
        self.assertIsNone(interpolate(available[:1],1.)[0]);p,t=interpolate(available,1.);self.assertEqual(p,[1.,2.,.5]);self.assertEqual(t,3.)

    def test_future_dependency_rejected(self):
        record={'availability_cutoff_epoch_ns':100,'dependency_record_indices':[1]}
        dependency_cutoff(record,{1:{'receive_epoch_ns':100}})
        with self.assertRaises(ValueError):dependency_cutoff(record,{1:{'receive_epoch_ns':101}})

    def test_missing_IMU_dependency_not_fabricated(self):
        with self.assertRaises(ValueError):dependency_cutoff({'availability_cutoff_epoch_ns':100,'dependency_record_indices':[9]}, {})

    def heading_record(self):
        return {'mode':'F3','heading_sources':{'startup':'external_initial_heading','keyframe_prediction':'gyro_increment','optimizer_initial_guess':'gyro_prediction','failure_recovery':'not_applicable'}}

    def test_heading_coverage_requires_every_phase(self):
        r=self.heading_record();heading_sources(r);del r['heading_sources']['optimizer_initial_guess']
        with self.assertRaises(ValueError):heading_sources(r)

    def test_hidden_odom_in_prediction_or_optimization_rejected(self):
        for key in ('startup','keyframe_prediction','optimizer_initial_guess','failure_recovery'):
            r=self.heading_record();r['heading_sources'][key]='odom_prediction'
            with self.assertRaises(ValueError):heading_sources(r)

    def test_explicit_odom_fallback_separate(self):
        r=self.heading_record();r['heading_sources']['failure_recovery']='odom_prediction';r.update(odom_heading_fallback=True,fallback_reason='IMU gap')
        self.assertTrue(heading_sources(r)['must_report_separately'])

    def test_absolute_IMU_yaw_not_a_room_reference(self):
        r=self.heading_record();r['heading_sources']['startup']='imu_absolute_yaw'
        with self.assertRaises(ValueError):heading_sources(r)

    def system(self):
        rng=np.random.default_rng(79);j=rng.normal(size=(18,8));r=rng.normal(size=18)
        h=j.T@j;g=j.T@r;s=h[4:,4:]-h[4:,:4]@np.linalg.solve(h[:4,:4],h[:4,4:]);b=g[4:]-h[4:,:4]@np.linalg.solve(h[:4,:4],g[:4]);a=np.linalg.cholesky(s).T;c=np.linalg.solve(a.T,b)
        return j,r,a,c

    def test_full_bias_marginal_cross_terms(self):
        j,r,a,c=self.system();self.assertTrue(marginal_prior(j,r,a,c)['bias_cross_information_retained'])

    def test_lost_cross_information_or_affine_offset_rejected(self):
        j,r,a,c=self.system()
        with self.assertRaises(ValueError):marginal_prior(j,r,np.diag(np.diag(a)),c)
        with self.assertRaises(ValueError):marginal_prior(j,r,a,np.zeros(4))

    def test_rank_degenerate_elimination_explicit(self):
        j,r,a,c=self.system();j[:,:4]=0
        with self.assertRaises(ValueError):marginal_prior(j,r,a,c)

    def test_factor_double_counting_omission_and_duplicate(self):
        factor_accounting(['prior','gyro'],['prior','gyro'],['retained_uwb'])
        for eliminated,retained in [(['prior','gyro'],['gyro']),(['prior'],[]),(['prior','gyro','gyro'],[])]:
            with self.assertRaises(ValueError):factor_accounting(eliminated,['prior','gyro'],retained)

    def test_full_coverage_not_favorable_subset(self):
        good=lambda t:{'state_time_s':t,'pose':[0,0,0],'accepted_graph':True,'status':'graph'}
        arms={mode:[good(1),good(2),good(3)] for mode in ('F0','F1','F2','F3')}
        arms['F2'][1].update(pose=None,accepted_graph=False,status='missing_IMU')
        arms['F3'].pop();result=coverage(arms)
        self.assertEqual(result['per_mode']['F2']['scheduled_publications'],3);self.assertEqual(result['per_mode']['F3']['missing_publications'],1)
        self.assertEqual(result['common_finite_state_times_s'],[1])

    def test_all_four_modes_required(self):
        with self.assertRaises(ValueError):coverage({'F0':[]})

    def sample(self,h,receive,index):
        return {'header_epoch_ns':h,'receive_epoch_ns':receive,'record_index':index,'nonfinite_values':[]}

    def test_release_cutoff_excludes_late_IMU_bracket(self):
        rows=[self.sample(0,0,1),self.sample(50,50,2),self.sample(100,201,3)]
        result=interval_coverage(rows,0,100,200,100)
        self.assertFalse(result['both_arrived_boundary_brackets']);self.assertIsNone(result['right_bracket_record_index'])
        self.assertEqual(result,interval_coverage(rows+[self.sample(150,250,4)],0,100,200,100))

    def test_release_equality_and_missing_IMU(self):
        rows=[self.sample(0,0,1),self.sample(100,200,2)]
        self.assertTrue(interval_coverage(rows,0,100,200,100)['both_arrived_boundary_brackets'])
        self.assertFalse(interval_coverage([],0,100,200,100)['both_arrived_boundary_brackets'])

    def test_support_gap_kept_as_bad_interval(self):
        result=interval_coverage([self.sample(0,0,1),self.sample(1000,1000,2)],0,1000,2000,100)
        self.assertTrue(result['both_arrived_boundary_brackets']);self.assertTrue(result['support_gap_over_diagnostic_threshold'])


if __name__=='__main__':unittest.main()
