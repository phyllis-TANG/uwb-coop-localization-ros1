#!/usr/bin/env python3
"""FGO factor, marginalization, hidden-heading and receipt-causality checks."""
import copy
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from configuration import default_config,validate,map_ns
from graph import Prior,Objective,WindowGraph,initial_prior,eliminate_oldest,predict
from integration import AngularBuffer,angular_covariance
from legacy import FixedLagReplay,PoseObjective,pose_prior,rotation,wrap
from frontend import ImuReplay,convert
from replay import execute,validate_events,COLUMNS
from simulate import generate,save,ORIGIN
from io_utils import gzip_writer,append,read_jsonl
from test_single_car_fixed_lag import problem
from test_single_car_sequential_replay import MODEL,POLICY


def interval(i,alpha=0.,valid=True,dt=1.):
    a=ORIGIN+round(i*1e9); b=a+round(dt*1e9)
    return dict(valid=valid,start_epoch_ns=a,end_epoch_ns=b,dt_ns=b-a,raw_angle_rad=alpha if valid else None,partial_angle_rad=alpha,segments=[],gaps=[] if valid else [dict(start_epoch_ns=a,end_epoch_ns=b)])


def setup_problem(arm='F3',n=4):
    model,t,local,obs,states,p=problem(n); c=default_config(arm); c['model']=model
    prior=initial_prior(model,c); intervals=[interval(i,wrap(local[i+1,2]-local[i,2])) for i in range(n-1)]
    if arm=='F3': states=np.column_stack((states,np.linspace(.01,.015,n)))
    return c,t,local,obs,states,prior,intervals


def stable(rows):
    keys=['state_time_s','availability_cutoff_s','status','accepted_graph','pose','antenna_xy_m','range_medians_m','range_sample_counts','local_odom','bias_rad_s','angular_valid','estimate_valid','prediction_yaw_source']
    return [{k:r.get(k) for k in keys} for r in rows]


class IntegrationTests(unittest.TestCase):
    def ident(self,t,receipt=None,index=1): return dict(mapped_header_epoch_ns=t,header_epoch_ns=t,receive_epoch_ns=t if receipt is None else receipt,record_index=index,source_file_sha256='fixture',topic='imu')
    def test_constant_and_split_composition(self):
        b=AngularBuffer()
        for i in range(21): b.add(self.ident(ORIGIN+i*50_000_000,index=i),.2)
        whole=b.integrate(ORIGIN,ORIGIN+1_000_000_000,ORIGIN+2_000_000_000)
        a=b.integrate(ORIGIN,ORIGIN+445_000_000,ORIGIN+2_000_000_000); c=b.integrate(ORIGIN+445_000_000,ORIGIN+1_000_000_000,ORIGIN+2_000_000_000)
        self.assertTrue(whole['valid']); self.assertAlmostEqual(whole['raw_angle_rad'],.2); self.assertAlmostEqual(a['raw_angle_rad']+c['raw_angle_rad'],whole['raw_angle_rad'])
    def test_new_endpoint_not_used_backwards(self):
        b=AngularBuffer(); b.add(self.ident(ORIGIN),.1); b.add(self.ident(ORIGIN+50_000_000,index=2),100.)
        r=b.integrate(ORIGIN,ORIGIN+50_000_000,ORIGIN+1_000_000_000); self.assertAlmostEqual(r['raw_angle_rad'],.005); self.assertEqual(len(r['segments']),1)
    def test_later_receipt_is_invisible(self):
        b=AngularBuffer(); b.add(self.ident(ORIGIN,ORIGIN+2_000_000_000),.2)
        r=b.integrate(ORIGIN,ORIGIN+50_000_000,ORIGIN+1_000_000_000); self.assertFalse(r['valid']); self.assertFalse(r['segments'])
    def test_gap_and_recovery(self):
        b=AngularBuffer(); b.add(self.ident(ORIGIN),.2)
        r=b.integrate(ORIGIN,ORIGIN+1_000_000_000,ORIGIN+2_000_000_000); self.assertFalse(r['valid']); self.assertIsNone(r['raw_angle_rad']); self.assertEqual(r['gaps'][0]['start_epoch_ns'],ORIGIN+100_000_000)
        b.add(self.ident(ORIGIN+1_000_000_000,index=2),.3); self.assertTrue(b.integrate(ORIGIN+1_000_000_000,ORIGIN+1_050_000_000,ORIGIN+2_000_000_000)['valid'])
    def test_future_source_rejected(self):
        self.assertEqual(AngularBuffer().add(self.ident(ORIGIN,ORIGIN-1),.1),'angular_source_after_receipt')
    def test_duplicates_and_out_of_order(self):
        b=AngularBuffer(); b.add(self.ident(ORIGIN),.1)
        for t in [ORIGIN,ORIGIN-1]: self.assertEqual(b.add(self.ident(t,ORIGIN+1,index=2),.1),'duplicate_or_out_of_order_angular_source')
    def test_nonfinite_and_capacity(self):
        b=AngularBuffer(capacity=2); self.assertEqual(b.add(self.ident(ORIGIN),float('nan')),'nonfinite_angular_rate')
        b.add(self.ident(ORIGIN),.1); b.add(self.ident(ORIGIN+1),.1)
        with self.assertRaises(BufferError): b.add(self.ident(ORIGIN+2),.1)
    def test_exact_ns_and_prune(self):
        b=AngularBuffer()
        for i in range(100): b.add(self.ident(ORIGIN+i,index=i),1.)
        b.prune(ORIGIN+90); self.assertEqual(len(b.rows),10)
        r=b.integrate(ORIGIN+91,ORIGIN+92,ORIGIN+100); self.assertEqual(r['dt_ns'],1); self.assertAlmostEqual(r['raw_angle_rad'],1e-9)
    def test_joint_angle_bias_covariance_numerical_integral(self):
        dt=1.3; g=.03; b=.002; S=angular_covariance(dt,g,b); n=10000; numeric=np.diag([g*g*dt,0.])
        for s in (np.arange(n)+.5)*dt/n:
            v=np.array([-(dt-s),1.]); numeric+=np.outer(v,v)*b*b*dt/n
        np.testing.assert_allclose(S,numeric,atol=1e-13); self.assertLess(S[0,1],0.); self.assertGreater(np.linalg.eigvalsh(S).min(),0.)
    def test_equal_cutoff_and_exact_hold_boundary(self):
        b=AngularBuffer();b.add(self.ident(ORIGIN,ORIGIN+1_000_000_000),.2)
        self.assertTrue(b.integrate(ORIGIN,ORIGIN+100_000_000,ORIGIN+1_000_000_000)['valid'])
        self.assertFalse(b.integrate(ORIGIN,ORIGIN+100_000_001,ORIGIN+1_000_000_000)['valid'])
    def test_invalid_integration_interval(self):
        with self.assertRaises(ValueError): AngularBuffer().integrate(1.,2,3)


class FactorTests(unittest.TestCase):
    def test_F1_equals_old_objective_when_angles_match(self):
        c,t,l,o,x,p,a=setup_problem('F1'); old=PoseObjective(t,l,o,c['model'],pose_prior(c['model'])); new=Objective(t,l,o,a,c['model'],p,c)
        r,J=old.evaluate(x.ravel()); r2,J2=new.evaluate(x.ravel())
        np.testing.assert_allclose(J.T@J,J2.T@J2,atol=1e-10); np.testing.assert_allclose(J.T@r,J2.T@r2,atol=1e-10); self.assertAlmostEqual(r@r,r2@r2)
    def test_F1_F2_same_rate_and_translation(self):
        c,t,l,o,x,p,a=setup_problem('F1'); one=Objective(t,l,o,a,c['model'],p,c); c['arm']='F2'; two=Objective(t,l,o,a,c['model'],p,c)
        np.testing.assert_array_equal(one.fun(x.ravel()),two.fun(x.ravel())); np.testing.assert_array_equal(one.jac(x.ravel()),two.jac(x.ravel()))
    def test_augmented_analytic_jacobian_and_cross_prior(self):
        c,t,l,o,x,p,a=setup_problem(); p=Prior(x[0]+[.01,-.02,.03,.002],[[4,.3,-.2,.4],[0,3,.7,-.2],[0,0,8,1.],[0,0,0,33.]], [.2,-.3,.1,.02])
        for missing in [False,True]:
            aa=copy.deepcopy(a)
            if missing: aa[1]=interval(1,valid=False)
            objective=Objective(t,l,o,aa,c['model'],p,c); flat=x.ravel(); step=1e-6
            num=np.column_stack([(objective.fun(flat+np.eye(len(flat))[i]*step)-objective.fun(flat-np.eye(len(flat))[i]*step))/(2*step) for i in range(len(flat))])
            np.testing.assert_allclose(objective.jac(flat),num,atol=3e-6,rtol=3e-6)
    def test_bias_sign_and_RW_whitening(self):
        c=default_config('F3'); c['model']=copy.deepcopy(MODEL); p=initial_prior(c['model'],c)
        x=np.zeros((2,4)); x[:,3]=.025; a=[interval(0,.025)]; obj=Objective([0,1],np.zeros((2,3)),[{},{}],a,c['model'],p,c)
        self.assertLess(np.linalg.norm(obj.fun(x.ravel())[-2:]),1e-12)
        x[1,2]=.05; self.assertGreater(np.linalg.norm(obj.fun(x.ravel())[-2:]),1.)
    def test_wrap_crosses_pi(self):
        c=default_config('F2'); c['model']=copy.deepcopy(MODEL); p=initial_prior(c['model'],c); x=np.array([[0,0,math.pi-.01],[0,0,-math.pi+.01]])
        obj=Objective([0,1],np.zeros((2,3)),[{},{}],[interval(0,.02)],c['model'],p,c)
        self.assertAlmostEqual(obj.fun(x.ravel())[-1],0.,places=12)
    def test_missing_angular_is_not_zero_factor(self):
        c,t,l,o,x,p,a=setup_problem(); a[0]=interval(0,valid=False); obj=Objective(t,l,o,a,c['model'],p,c)
        full=Objective(t,l,o,[interval(i,.08) for i in range(len(t)-1)],c['model'],p,c)
        self.assertEqual(len(full.fun(x.ravel()))-len(obj.fun(x.ravel())),1)
    def test_interval_dt_mismatch_rejected(self):
        c,t,l,o,x,p,a=setup_problem();a[0]['dt_ns']+=1
        with self.assertRaises(ValueError):Objective(t,l,o,a,c['model'],p,c)
    def test_stationary_zero_lever_no_bias_information_gain(self):
        c=default_config('F3');c['model']=copy.deepcopy(MODEL);g=WindowGraph(c)
        obs={k:float(np.linalg.norm(np.array([0,0,.2])-v)) for k,v in MODEL['anchors_xyz_m'].items()}
        for t in range(8):r=g.update(t,np.zeros(3),obs,None if t==0 else interval(t-1,.025))
        self.assertAlmostEqual(r['bias_rad_s'],0.,places=10)
        objective=Objective(g.times,g.local,g.observations,g.intervals,c['model'],g.prior,c);J=objective.jac(np.array(g.states).ravel());P=np.linalg.inv(J.T@J)
        self.assertGreaterEqual(P[-1,-1],.03**2-1e-10)
    def test_nonfinite_prior_rejected(self):
        with self.assertRaises(ValueError): Prior(np.zeros(4),np.eye(4)*float('nan'),np.zeros(4))


class MarginalTests(unittest.TestCase):
    def test_full_linearized_information_affine_cost_and_no_double_count(self):
        c,t,l,o,x,p,a=setup_problem(); full=Objective(t,l,o,a,c['model'],p,c); r,J=full.evaluate(x.ravel())
        new,constant,info=eliminate_oldest(x,t,l,o,a,c['model'],p,c); remaining=Objective(t[1:],l[1:],o[1:],a[1:],c['model'],new,c); r2,J2=remaining.evaluate(x[1:].ravel())
        old=J[:,:4]; residual_projected=r-old@np.linalg.lstsq(old,r,rcond=None)[0]; reduced=J[:,4:]-old@np.linalg.lstsq(old,J[:,4:],rcond=None)[0]
        np.testing.assert_allclose(J2.T@J2,reduced.T@reduced,atol=1e-6,rtol=1e-9); np.testing.assert_allclose(J2.T@r2,reduced.T@residual_projected,atol=1e-7,rtol=1e-8)
        self.assertGreater(np.linalg.norm(new.offset),1e-4); self.assertGreater(np.linalg.norm(new.matrix[:3,3]),.01); self.assertFalse(info['includes_retained_UWB'])
        for delta in np.random.default_rng(5).normal(0,.005,(5,4*(len(t)-1))):
            d0=np.linalg.lstsq(old,-r-J[:,4:]@delta,rcond=None)[0]; expected=np.linalg.norm(r+old@d0+J[:,4:]@delta)**2
            self.assertAlmostEqual(expected,np.linalg.norm(r2+J2@delta)**2+constant,places=7)
    def test_rank_deficient_prior_retained_without_invention(self):
        c=default_config('F3'); c['model']=copy.deepcopy(MODEL); x=np.zeros((2,4)); p=Prior(x[0],np.zeros((0,4)),np.zeros(0))
        carried,_,info=eliminate_oldest(x,[0,1],np.zeros((2,3)),[{},{}],[interval(0,valid=False)],c['model'],p,c)
        self.assertTrue(info['rank_deficient']); self.assertLess(info['old_rank'],4); self.assertEqual(np.linalg.norm(carried.matrix),0.)
    def test_bias_cross_information_propagates_over_many_marginalizations(self):
        c=default_config('F3'); c['model']=copy.deepcopy(MODEL); g=WindowGraph(c)
        for t in range(100): g.update(t,np.zeros(3),{},None if t==0 else interval(t-1))
        self.assertEqual(g.marginalizations,79); self.assertEqual(len(g.states),21); self.assertEqual(g.peak_transient_states,22)
        P=np.linalg.inv(g.prior.matrix.T@g.prior.matrix); qb=.0007**2; qg=math.radians(2)**2; v=.03**2; T=79
        self.assertAlmostEqual(P[3,3],v+T*qb,places=10); self.assertAlmostEqual(P[2,3],-T*v-qb*T*T/2,places=9)
        self.assertAlmostEqual(P[2,2],math.radians(5)**2+T*qg+T*T*v+qb*T**3/3,places=7)
    def test_before_first_marginalization_identical_to_full_history(self):
        c,t,l,o,_,_,a=setup_problem(n=10); fixed=WindowGraph(c,20); full=WindowGraph(c,None)
        for i in range(10):
            one=fixed.update(t[i],l[i],o[i],None if i==0 else a[i-1]); two=full.update(t[i],l[i],o[i],None if i==0 else a[i-1]); np.testing.assert_array_equal(one['pose'],two['pose'])
    def test_exact_nonlinear_full_history_and_fixed_window(self):
        c=default_config('F3'); c['model']=copy.deepcopy(MODEL); c['model']['base_to_antenna_body_xy_m']=[.12,-.08]; c['model']['start_antenna_xyz_m']=[.12,-.08,.2]
        g=WindowGraph(c,20); full=WindowGraph(c,None)
        for t in range(35):
            pose=np.array([.03*t,.002*t*t,.01*t]); xy=pose[:2]+rotation(pose[2])@np.array([.12,-.08]); obs={k:float(np.linalg.norm(np.r_[xy,.2]-p)) for k,p in MODEL['anchors_xyz_m'].items()}
            one=g.update(t,pose,obs,None if t==0 else interval(t-1,.01)); two=full.update(t,pose,obs,None if t==0 else interval(t-1,.01))
            np.testing.assert_allclose(one['pose'],pose,atol=2e-9); np.testing.assert_allclose(one['pose'],two['pose'],atol=2e-9)
        self.assertEqual(g.marginalizations,14)
    def test_missing_stationary_yaw_rank_is_reported(self):
        c=default_config('F3'); c['model']=copy.deepcopy(MODEL); g=WindowGraph(c)
        for t in range(3): r=g.update(t,np.zeros(3),{},None if t==0 else interval(t-1,valid=t!=1))
        self.assertTrue(r['accepted_graph']); self.assertFalse(r['estimate_valid']); self.assertIn('rank_deficient',r['status'])


class ReplayTests(unittest.TestCase):
    def test_F0_original_default_exact_including_fallback(self):
        c,events,_,_=generate('nominal',101,8_000_000_000); c.pop('arm'); old=[]; f=FixedLagReplay(c['model'],c['replay'],old.append); origin=events[0]['receive_epoch_ns']
        for e in events:f.ingest(convert(e,c,origin))
        f.finish(); new=[]; execute(events,c,new.append)
        for a,b in zip(old,new):
            for k in a:
                if k not in ('update_wall_s','solve_wall_s','marginal_wall_s','estimated_worker_start_s','estimated_worker_finish_s','estimated_worker_queue_s'): self.assertEqual(a[k],b[k],k)
    def test_frontend_same_bins_and_translation_all_arms(self):
        c,events,_,_=generate('nominal',102,6_000_000_000); sets=[]
        for arm in ('F0','F1','F2','F3'):
            cfg=copy.deepcopy(c); cfg['arm']=arm; rows=[]; execute(events,cfg,rows.append); sets.append(rows)
        for rows in sets[1:]:
            for a,b in zip(sets[0],rows):
                for key in ['state_time_s','availability_cutoff_s','local_odom','range_medians_m','range_sample_counts']: self.assertEqual(a[key],b[key])
    def test_start_prediction_and_failed_solve_do_not_use_odom_yaw(self):
        c=default_config('F3'); c['optimizer']['max_nfev']=1; c['model']=copy.deepcopy(MODEL); c['model']['initial_heading_deg']=12.; c['model']['base_to_antenna_body_xy_m']=[.12,-.08]
        g=WindowGraph(c); local=np.zeros(3); initial=math.radians(12)
        for t in range(3):
            local[2]=-.7*t; obs={k:float(np.linalg.norm(np.array([0,0,.2])-xyz))+.5 for k,xyz in MODEL['anchors_xyz_m'].items()}
            r=g.update(t,local,obs,None if t==0 else interval(t-1,.1)); self.assertAlmostEqual(r['pose'][2],initial+.1*t)
        self.assertEqual(r['status'],'predict_only_solver_failed'); self.assertFalse(r['odom_yaw_fallback'])
    def test_missing_gyro_prediction_holds_not_odom_fallback(self):
        c=default_config('F3'); c['model']=copy.deepcopy(MODEL); g=WindowGraph(c); g.update(0,np.zeros(3),{})
        r=g.update(1,np.array([0.,0.,1.2]),{},interval(0,valid=False)); self.assertEqual(r['pose'][2],0.); self.assertFalse(r['estimate_valid']); self.assertEqual(r['prediction_yaw_source'],'held_yaw_initial_guess_missing_angular')
    def test_prefix_invariance_after_marginalization(self):
        c,events,_,_=generate('nominal',103,32_000_000_000); c['arm']='F3'; complete=[]; execute(events,c,complete.append); cutoff=ORIGIN+28_000_000_000
        changed=copy.deepcopy(events)
        for e in changed:
            if e['receive_epoch_ns']>cutoff:
                if e['kind']=='imu': e['value']['angular_velocity_rad_s'][2]=2.
                if e['kind']=='uwb': e['value']={k:v+.5 for k,v in e['value'].items()}
        mutated=[]; execute(changed,c,mutated.append); select=lambda rows:[r for r in rows if r['availability_cutoff_epoch_ns']<=cutoff]
        self.assertEqual(stable(select(complete)),stable(select(mutated)))
        truncated=[e for e in events if e['receive_epoch_ns']<=cutoff]; truncated.append(dict(kind='clock',case_id=events[0]['case_id'],record_index=99999,receive_epoch_ns=cutoff,value=None))
        short=[]; execute(truncated,c,short.append); self.assertEqual(stable(select(complete)),stable(short)); self.assertGreater(complete[-1]['marginalizations'],0)
    def test_gap_recovery_and_frozen_publications(self):
        c,events,_,_=generate('imu_gap',104,26_000_000_000); c['arm']='F3'; rows=[]; replay=execute(events,c,rows.append)
        missing=[r for r in rows if r.get('angular_interval') and not r['angular_valid']]; self.assertGreaterEqual(len(missing),4); self.assertTrue(all(not r['estimate_valid'] for r in missing))
        self.assertTrue(rows[-1]['angular_valid']); self.assertGreater(rows[-1]['missing_angular_edges_cumulative'],0); self.assertEqual(replay.rejections['duplicate_or_out_of_order_angular_source'],1)
        for r in rows:
            edge=r.get('angular_interval')
            if edge:
                for s in edge['segments']:
                    self.assertLessEqual(s['dependency']['receive_epoch_ns'],r['availability_cutoff_epoch_ns']); self.assertLessEqual(s['dependency']['mapped_header_epoch_ns'],s['start_epoch_ns'])
    def test_axis_sign_units_and_nonfinite_negative(self):
        c,events,_,_=generate('nominal',105,3_000_000_000); c['arm']='F2'; altered=copy.deepcopy(events)
        for e in altered:
            if e['kind']=='imu': e['value']['angular_velocity_rad_s'][2]*=-1
        c['angular']['body_z_in_imu_frame']['value']=[0,0,-1]; a=[];execute(altered,c,a.append); c['angular']['body_z_in_imu_frame']['value']=[0,0,1]; b=[];execute(events,c,b.append)
        self.assertEqual(stable(a),stable(b))
        for e in altered:
            if e['kind']=='imu': e['value']['units']='deg/s'
        r=[]; replay=execute(altered,c,r.append); self.assertGreater(replay.rejections['unsupported_gyro_units'],0); self.assertFalse(r[-1]['angular_valid'])
    def test_F3_no_imu_quaternion_or_odom_angular_z_observation(self):
        c,events,_,_=generate('nominal',106,5_000_000_000); c['arm']='F3'; changed=copy.deepcopy(events)
        for e in changed:
            if e['kind']=='odom': e['value']['angular_z_rad_s']='unused'
            if e['kind']=='imu': e['value']['quaternion']='unused'
        a=[]; b=[];execute(events,c,a.append);execute(changed,c,b.append); self.assertEqual(stable(a),stable(b))
    def test_eof_missing_odom_no_extrapolation(self):
        c,events,_,_=generate('nominal',107,4_000_000_000); c['arm']='F3'; keep=[e for e in events if e['kind']!='odom' or e['header_epoch_ns']==ORIGIN]; rows=[];execute(keep,c,rows.append)
        self.assertTrue(rows); self.assertTrue(all(r['pose'] is None for r in rows))
    def test_integer_mapping_and_holdout_reject(self):
        c,events,_,_=generate('nominal',108,100_000_000); self.assertEqual(map_ns(ORIGIN+1,c['clock_maps']['imu']),ORIGIN+1)
        events[0]['header_epoch_ns']=float(events[0]['header_epoch_ns'])
        with self.assertRaises(ValueError): validate_events(events,c)
        events[0]['header_epoch_ns']=ORIGIN; c['scope']='field'
        for e in events:e['case_id']='T09'
        with self.assertRaisesRegex(ValueError,'holdout'):validate_events(events,c)
    def test_legacy_pose_translation_yaw_dependency_disclosed_not_erased(self):
        c,t,l,o,x,p,a=setup_problem(); changed=l.copy(); changed[:-1,2]+=.4
        one=Objective(t,l,o,a,c['model'],p,c);two=Objective(t,changed,o,a,c['model'],p,c)
        self.assertGreater(np.linalg.norm(one.fun(x.ravel())-two.fun(x.ravel())),.1)
    def test_new_config_cannot_promote_synthetic_to_field(self):
        c=default_config();c['scope']='field'
        with self.assertRaises(ValueError):validate(c)
    def test_generator_bias_drift_and_range_sign(self):
        _,_,truth,_=generate('gyro_constant_bias',109,1_000_000_000);self.assertEqual(truth[-1]['bias_rad_s'],.025)
        _,_,truth,_=generate('gyro_drift',109,1_000_000_000);self.assertNotEqual(truth[0]['bias_rad_s'],truth[-1]['bias_rad_s'])
        _,a,_,_=generate('nominal',109,36_000_000_000);_,b,_,_=generate('range_bias',109,36_000_000_000)
        for e,f in zip(a,b):
            if e['kind']=='uwb':
                for k in e['value']:self.assertAlmostEqual(f['value'][k]-e['value'][k],.3 if k=='node_10' and ORIGIN+12_000_000_000<=e['header_epoch_ns']<ORIGIN+35_000_000_000 else 0.)
    def test_nonfinite_quality_is_preserved_as_flag(self):
        from io_utils import clean
        flags=[];row=clean({'quality_rssi':float('nan'),'gyro':float('inf')},flags=flags)
        self.assertEqual(row,{'quality_rssi':None,'gyro':None});self.assertEqual({f['original'] for f in flags},{'nan','inf'})
    def test_invalid_axis_and_noise_units_rejected(self):
        c=default_config();c['angular']['body_z_in_imu_frame']['value']=[0,0,2]
        with self.assertRaises(ValueError):validate(c)
        c=default_config();c['angular']['bias_random_walk_rad_s_sqrt_s']['units']='rad/s'
        with self.assertRaises(Exception):validate(c)
    def test_generator_determinism_and_no_labels(self):
        a=generate('nominal',110,100_000_000);b=generate('nominal',110,100_000_000);self.assertEqual(a,b)
        self.assertTrue(all(not({'true_pose','truth','fault_label','true_bias'}&set(e)) for e in a[1]))
    def test_cli_outputs_and_no_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='imu-fgo-test-') as tmp:
            root=Path(tmp);save(root/'inputs','nominal',111,4_000_000_000); c=json.loads((root/'inputs/template.json').read_text());c['arm']='F3';(root/'config.json').write_text(json.dumps(c))
            command=[sys.executable,str(Path(__file__).with_name('replay.py')),'--events-jsonl',str(root/'inputs/events.jsonl.gz'),'--config',str(root/'config.json'),'--output',str(root/'run')]
            r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            expected={'run.json','config.json','published.csv','updates.jsonl.gz','input_decisions.jsonl.gz','final_active_graph.json','summary.json'};self.assertEqual({p.name for p in (root/'run').iterdir()},expected)
            with (root/'run/published.csv').open() as stream:reader=csv.DictReader(stream);self.assertEqual(reader.fieldnames,COLUMNS);self.assertEqual(len(list(reader)),3)
            from audit import audit
            report=audit(root/'run',root/'inputs/events.jsonl.gz',stride=1);self.assertEqual(report['status'],'PASS',report);self.assertGreater(report['counts']['objective_cost_checks'],0)
            records=list(read_jsonl(root/'run/updates.jsonl.gz'));records[-1]['prediction_pose'][2]+=.1
            (root/'run/updates.jsonl.gz').unlink()
            with gzip_writer(root/'run/updates.jsonl.gz') as stream:
                for record in records:append(stream,record)
            self.assertEqual(audit(root/'run',root/'inputs/events.jsonl.gz')['status'],'FAIL')
            r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,1);self.assertIn('FileExistsError',r.stderr)


if __name__=='__main__':unittest.main(verbosity=2)
