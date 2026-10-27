#!/usr/bin/env python3
"""Numerical, causal and adapter contract regression; no field files involved."""
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
from configuration import synthetic_config, with_mode, validate, readiness
from dynamics import transition, process_covariance, range_geometry, wrap
from imu_filter import make_filter, ImuFilter, LegacyAdapter
from io_utils import append, gzip_writer, read_jsonl, clean
from legacy import model, CARS, ESTIMATE_COLUMNS
from replay import replay_events, event_key, validate_events, EXTRA_COLUMNS
from simulate import generate, save, truth_step


def run(events, config, method='independent'):
    f = make_filter(method, config); details=[]
    for e in sorted(events,key=event_key): details.append(f.process(e))
    return f, details


def sample(kind, car='car1', t=0, delay=5_000_000, record=1, **kwargs):
    config, events, _, _ = generate('nominal', 1, 100_000_000)
    row = copy.deepcopy(next(e['row'] for e in events if e['kind']==kind and e['row']['vehicle_id']==car))
    origin=config['vehicles'][car]['odom_clock']['source_origin_ns']
    row.update(header_epoch_ns=origin+t, receive_epoch_ns=origin+t+delay, record_index=record, **kwargs)
    return dict(kind=kind,row=row)


class Dynamics(unittest.TestCase):
    def test_motion_jacobian(self):
        for rate in [0.,.3,-.3,1e-8]:
            for yaw in [3.1415,-3.1415,1.2]:
                for vel in [(-.3,.12),(.2,-.14),(0.,0.)]:
                    state=np.array([1.,2.,yaw,.015]); _,F=transition(state,vel,rate,.073,True)
                    numerical=np.zeros((4,4)); eps=1e-6
                    for j in range(4):
                        d=np.eye(4)[j]*eps; a,_=transition(state+d,vel,rate,.073,True); b,_=transition(state-d,vel,rate,.073,True)
                        diff=a-b; diff[2]=wrap(diff[2]); numerical[:,j]=diff/(2*eps)
                    np.testing.assert_allclose(F,numerical,atol=2e-8)
    def test_fixed_state_jacobian(self):
        x=np.array([1.,2.,1.,0.]); _,F=transition(x,[-.1,.2],.2,.1,False); numerical=np.zeros((4,4))
        for j in range(4):
            d=np.eye(4)[j]*1e-6; numerical[:,j]=(transition(x+d,[-.1,.2],.2,.1,False)[0]-transition(x-d,[-.1,.2],.2,.1,False)[0])/2e-6
        np.testing.assert_allclose(F,numerical,atol=1e-9)
    def test_range_jacobian(self):
        c=synthetic_config(); state=np.r_[c['vehicles']['car1']['initial_room_pose']['value'],.02,c['vehicles']['car2']['initial_room_pose']['value'],-.01]
        vehicles={car:dict(lever_xy=model.antenna_offset_xy(c['vehicles'][car]),height=model.antenna_height(c['vehicles'][car])) for car in CARS}
        for car,target in [('car1','node_0'),('car2','node_1'),('car1','node_8'),('car2','node_10')]:
            _,H=range_geometry(state,vehicles,c['anchors_xyz_m']['value'],car,target); num=[]
            for j in range(8):
                d=np.eye(8)[j]*1e-6; num.append((range_geometry(state+d,vehicles,c['anchors_xyz_m']['value'],car,target)[0]-range_geometry(state-d,vehicles,c['anchors_xyz_m']['value'],car,target)[0])/2e-6)
            np.testing.assert_allclose(H,num,atol=2e-9); self.assertEqual(H[3],0.); self.assertEqual(H[7],0.)
    def test_Q_against_quadrature_and_cross_units(self):
        state=np.array([0.,0.,1.,.02]); vel=[-.3,.1]; rate=.2; dt=.1
        Q=process_covariance(state,vel,rate,dt,True,.04,.025,.0007)
        theta=state[2]+(rate-state[3])*dt/2; vx=math.cos(theta)*vel[0]-math.sin(theta)*vel[1]; vy=math.sin(theta)*vel[0]+math.cos(theta)*vel[1]
        A=np.zeros((4,4)); A[:2,2]=[-vy,vx]; A[2,3]=-1; C=np.diag(np.square([.04,.04,.025,.0007]))
        numerical=np.zeros((4,4)); n=2000
        for t in (np.arange(n)+.5)*dt/n:
            E=np.eye(4)+A*t+A@A*t*t/2; numerical+=E@C@E.T*dt/n
        np.testing.assert_allclose(Q,numerical,atol=1e-13)
        self.assertAlmostEqual(Q[2,3],-(.0007**2)*dt**2/2); self.assertAlmostEqual(Q[3,3],.0007**2*dt)
        self.assertGreater(np.linalg.eigvalsh(Q).min(),0.)
    def test_reverse_lateral_and_wrap_independent_truth(self):
        for yaw in [3.14,-3.14,1.1]:
            for v in [(-.2,.1,.3),(.3,-.2,-.5),(.1,.2,0.)]:
                got,_=transition([1.,2.,yaw,.02],v[:2],v[2]+.02,.2,True)
                np.testing.assert_allclose(got[:3],truth_step([1.,2.,yaw],v,.2),atol=1e-13)
    def test_invalid_dt(self):
        with self.assertRaises(ValueError): transition([0]*4,[0,0],0,-.1,True)
    def test_fixed_bias_covariance_zero(self):
        Q=process_covariance([0,0,0,0],[.1,.1],.1,.1,False,.04,.025,.0007)
        np.testing.assert_array_equal(Q[3],np.zeros(4))


class Causality(unittest.TestCase):
    def setUp(self): self.c=synthetic_config(); self.o=self.c['vehicles']['car1']['odom_clock']['source_origin_ns']
    def test_legacy_default_and_off_exact(self):
        c,events,_,_=generate('nominal',2,2_000_000_000); c.pop('imu_prototype'); self.assertIsInstance(make_filter('joint',c),LegacyAdapter)
        for method in ['independent','joint']:
            base=model.Baseline(method,c); adapter=make_filter(method,c)
            for e in events:
                if e['kind']!='imu': self.assertEqual(base.process(e),adapter.process(e))
                else: adapter.process(e)
                self.assertEqual(base.snapshot(e['row']['receive_epoch_ns']),adapter.snapshot(e['row']['receive_epoch_ns']))
        off=with_mode(synthetic_config(),'legacy_odom_pose'); f,_=run(events,off,'joint')
        self.assertEqual(f.snapshot(events[-1]['row']['receive_epoch_ns']),base.snapshot(events[-1]['row']['receive_epoch_ns']))
        self.assertIsNone(f.provenance('car1')['gyro_bias_rad_s'])
    def test_no_odom_pose_or_imu_orientation_observation(self):
        c,events,_,_=generate('nominal',3,2_000_000_000); changed=copy.deepcopy(events)
        for e in changed:
            if e['kind']=='odom':
                e['row'].update(position_x=12345.,position_y=-12345.,orientation_x='unused',orientation_z='unused',angular_z='unused')
            if e['kind']=='imu': e['row']['orientation_w']='unused'
        a,_=run(events,c); b,_=run(changed,c)
        np.testing.assert_array_equal(a.x,b.x); np.testing.assert_array_equal(a.P,b.P)
    def test_body_odom_ignores_imu(self):
        c,events,_,_=generate('nominal',4,1_000_000_000); c=with_mode(c,'body_odom_rate')
        a,_=run(events,c); b,_=run([e for e in events if e['kind']!='imu'],c)
        np.testing.assert_array_equal(a.x,b.x); self.assertIsNone(a.provenance('car1')['last_imu'])
    def test_all_propagation_endpoints_causal(self):
        c,events,_,_=generate('nominal',5,2_000_000_000)
        for tick,_,ds,_,_ in replay_events(events,c):
            for d in ds:
                self.assertLessEqual(d['input']['row']['receive_epoch_ns'],tick)
                for p in d['decision']['propagations']:
                    for key in ('velocity','angular'):
                        self.assertLessEqual(p[key]['sample_epoch_ns'],p['from_epoch_ns'])
                        self.assertLessEqual(p[key]['receive_epoch_ns'],d['input']['row']['receive_epoch_ns'])
                    self.assertEqual(p['dt_ns'],p['to_epoch_ns']-p['from_epoch_ns'])
    def test_future_suffix_cannot_change_past_publication(self):
        c,events,_,_=generate('nominal',5,1_000_000_000); changed=copy.deepcopy(events)
        for e in changed:
            if e['row']['receive_epoch_ns']>self.o+600_000_000:
                if e['kind']=='imu': e['row']['angular_velocity_z']=100.
                if e['kind']=='odom': e['row']['linear_x']=100.
                if e['kind']=='range': e['row']['range_m']=100.
        a=[s for t,s,*_ in replay_events(events,c) if t<=self.o+500_000_000]
        b=[s for t,s,*_ in replay_events(changed,c) if t<=self.o+500_000_000]
        self.assertEqual(a,b)
    def test_missing_range_target_rejected(self):
        c,events,_,_=generate('nominal',5,100_000_000)
        for e in events:
            if e['kind']=='range': e['row'].pop('target_id')
        _,ds=run(events,c); self.assertTrue(any(d['status']=='unknown_range_target' for d in ds))
    def test_future_control_rejected(self):
        f=ImuFilter('independent',self.c); e=sample('imu',delay=-1)
        self.assertEqual(f.process(e)['status'],'future_measurement_time')
    def test_stale_control_rejected(self):
        f=ImuFilter('independent',self.c); self.assertEqual(f.process(sample('imu',delay=201_000_000))['status'],'stale_measurement_on_arrival')
    def test_duplicate_identity(self):
        f=ImuFilter('independent',self.c); e=sample('odom'); f.process(e)
        self.assertEqual(f.process(e)['status'],'duplicate_trace')
    def test_duplicate_source(self):
        f=ImuFilter('independent',self.c); f.process(sample('odom'))
        self.assertEqual(f.process(sample('odom',delay=6_000_000,record=2))['status'],'duplicate_or_out_of_order_source_time')
    def test_late_control_not_backfilled(self):
        f=ImuFilter('independent',self.c)
        for e in [sample('imu',delay=3_000_000),sample('odom',record=2),sample('odom',t=50_000_000,record=3)]: f.process(e)
        before=f.x.copy(); d=f.process(sample('imu',t=40_000_000,delay=30_000_000,record=4))
        self.assertEqual(d['status'],'late_control_before_state_not_backfilled'); np.testing.assert_array_equal(before,f.x)
    def test_new_endpoint_not_used_backwards(self):
        f=ImuFilter('independent',self.c)
        f.process(sample('imu',delay=3_000_000,angular_velocity_z=0.)); f.process(sample('odom',linear_x=0.,linear_y=0.,record=2))
        before=f.x.copy(); d=f.process(sample('imu',t=50_000_000,record=3,angular_velocity_z=100.))
        self.assertTrue(d['propagations']); np.testing.assert_allclose(f.x,before,atol=1e-14)
        self.assertEqual(d['propagations'][0]['observed_rate_rad_s'],0.)
    def test_same_source_different_arrival_order(self):
        for imu_first in (True,False):
            f=ImuFilter('independent',self.c)
            events=[sample('imu',delay=3_000_000 if imu_first else 6_000_000),sample('odom',record=2)]
            for e in sorted(events,key=event_key): f.process(e)
            self.assertEqual(f.times['car1'],self.o); self.assertIsNotNone(f.controls['car1']['imu'])
            self.assertFalse(f.snapshot(self.o+6_000_000)['car1']['unobserved_motion_gap'])
    def test_publication_has_no_predict_to_receive(self):
        f,_=run([sample('imu',delay=3_000_000),sample('odom',record=2)],self.c)
        a=f.snapshot(self.o+10_000_000); b=f.snapshot(self.o+50_000_000)
        self.assertEqual(a['car1']['pose'],b['car1']['pose']); self.assertEqual(a['car1']['state_epoch_ns'],self.o)
    def test_gap_invalid_and_explicit_recovery(self):
        c,events,_,_=generate('imu_dropout',6,18_000_000_000); saw_invalid=False; saw_recovery=False; car2_valid=0; car2_rows=0; f=ImuFilter('independent',c)
        for e in events:
            d=f.process(e)
            if self.o+14_300_000_000<e['row']['receive_epoch_ns']<self.o+16_500_000_000:
                snap=f.snapshot(e['row']['receive_epoch_ns']); saw_invalid |= not snap['car1']['valid']; car2_valid+=int(snap['car2']['valid']); car2_rows+=1
            if d['gap_reanchors']:
                saw_recovery=True
                for p in d['gap_reanchors']: self.assertTrue(p['missing_motion_not_integrated']); self.assertTrue(p['pose_mean_held'])
        self.assertTrue(saw_invalid and saw_recovery); self.assertTrue(f.provenance('car1')['unobserved_motion_gap']); self.assertGreater(car2_valid/car2_rows,.85); self.assertEqual(f.gap_counts['car2'],0)
    def test_units_and_frame_negative(self):
        for fields,status in [({'angular_velocity_units':'deg/s'},'unsupported_gyro_units'),({'frame_id':'wrong'},'invalid_imu_frame'),({'angular_velocity_z':float('nan')},'invalid_gyro_vector')]:
            self.assertEqual(ImuFilter('independent',self.c).process(sample('imu',**fields))['status'],status)
    def test_axis_mapping_explicit_sign(self):
        self.c['imu_prototype']['vehicles']['car1']['gyro_axis_body_z_in_imu_frame']['value']=[0.,0.,-1.]
        f=ImuFilter('independent',self.c); f.process(sample('imu',angular_velocity_z=-.2)); self.assertEqual(f.controls['car1']['imu']['value'],.2)
    def test_bad_axis_rejected(self):
        self.c['imu_prototype']['vehicles']['car1']['gyro_axis_body_z_in_imu_frame']['value']=[0,0,2]
        with self.assertRaises(ValueError): validate(self.c)
    def test_numerical_failure_not_valid(self):
        f,_=run([sample('imu',delay=3_000_000),sample('odom',record=2)],self.c)
        f.P[0,0]=-10.
        detail=f.process(sample('odom',t=50_000_000,record=3))
        self.assertTrue(detail['numerical_failures']); self.assertFalse(f.snapshot(self.o+55_000_000)['car1']['valid'])
    def test_integer_clock_single_ns_and_interval(self):
        clock=copy.deepcopy(self.c['imu_prototype']['vehicles']['car1']['imu_clock'])
        row=sample('imu')['row']; row['header_epoch_ns']+=1
        self.assertEqual(model.map_time(row,clock),self.o+1)
        clock['valid_source_interval_ns']=[self.o,self.o]
        with self.assertRaises(model.ClockIntervalError): model.map_time(row,clock)
    def test_receive_order_guard(self):
        f=ImuFilter('independent',self.c); f.process(sample('odom',t=50_000_000))
        with self.assertRaises(ValueError): f.process(sample('imu'))
    def test_nan_retained_in_decision(self):
        e=sample('imu',angular_velocity_z=float('nan')); e['row']['quality_rssi']=float('nan')
        _,_,ds,_,_=next(replay_events([e],self.c)); self.assertEqual(len(ds[0]['nonfinite_input_fields']),2)
        self.assertIsNone(ds[0]['input']['row']['quality_rssi']); self.assertEqual(ds[0]['decision']['status'],'invalid_gyro_vector')


class FusionAndContract(unittest.TestCase):
    def test_independent_isolation(self):
        c,events,_,_=generate('nominal',7,2_000_000_000)
        a,_=run(events,c); b,_=run([e for e in events if not(e['kind']=='range' and(e['row']['vehicle_id']=='car2' or e['row']['target_id']=='node_0'))],c)
        np.testing.assert_array_equal(a.x[:4],b.x[:4]); np.testing.assert_array_equal(a.P[:4,:4],b.P[:4,:4]); np.testing.assert_array_equal(a.P[:4,4:],np.zeros((4,4)))
    def test_joint_cross_covariance_and_reverse_gate(self):
        c,events,_,_=generate('nominal',8,1_000_000_000); f,ds=run(events,c,'joint')
        self.assertTrue(any(d['status']=='peer_updated' for d in ds)); self.assertGreater(np.linalg.norm(f.P[:4,4:]),0.)
        self.assertTrue(any(d['status']=='excluded_correlated_reverse_direction' for d in ds))
    def test_bias_fixed_and_estimated(self):
        c,events,_,_=generate('gyro_constant_bias',9,10_000_000_000); a,_=run(events,with_mode(c,'body_imu_fixed_bias')); b,_=run(events,c)
        self.assertEqual(a.x[3],0.); self.assertEqual(a.P[3,3],0.); self.assertNotEqual(b.x[3],0.); self.assertGreater(b.P[3,3],0.)
    def test_stationary_zero_lever_bias_unobservable(self):
        c,events,_,_=generate('stationary_unobservable',10,4_000_000_000)
        # Exact zero body velocity isolates the analytic unobservable case.
        for e in events:
            if e['kind']=='odom': e['row'].update(linear_x=0.,linear_y=0.)
        f,_=run(events,c); self.assertEqual(f.x[3],0.); self.assertGreaterEqual(f.P[3,3],.03**2)
        self.assertEqual(np.linalg.matrix_rank(f.wall_gramian['car1'],tol=1e-9),2)
    def test_constant_timevarying_bias_and_sign_injections(self):
        _,_,truth,_=generate('gyro_constant_bias',11,100_000_000); self.assertEqual(truth[0]['vehicles']['car1']['gyro_bias_rad_s'],.020); self.assertEqual(truth[-1]['vehicles']['car2']['gyro_bias_rad_s'],-.015)
        _,_,truth,_=generate('gyro_timevarying_bias',11,1_000_000_000); self.assertNotEqual(truth[0]['vehicles']['car1']['gyro_bias_rad_s'],truth[-1]['vehicles']['car1']['gyro_bias_rad_s'])
    def test_range_injection_exact_difference(self):
        # Same generator random draws; only one defined link and interval changes.
        _,a,_,labels=generate('nominal',12,25_000_000_000); _,b,_,_=generate('range_bias',12,25_000_000_000)
        for ea,eb in zip(a,b):
            if ea['kind']=='range':
                r=ea['row']; expected=.30 if r['vehicle_id']=='car1' and r['target_id']=='node_2' and labels['injection_interval_ns'][0]<=r['header_epoch_ns']<labels['injection_interval_ns'][1] else 0.
                self.assertAlmostEqual(eb['row']['range_m']-r['range_m'],expected)
    def test_reproducible_generation(self):
        a=generate('gyro_timevarying_bias',13,100_000_000); b=generate('gyro_timevarying_bias',13,100_000_000); self.assertEqual(a,b)
    def test_no_truth_or_fault_fields_in_events(self):
        _,events,_,_=generate('gyro_constant_bias',14,100_000_000)
        for e in events:
            self.assertFalse({'truth','bias','fault','gyro_bias_rad_s'} & set(e['row']))
    def test_pending_clock_is_blocked(self):
        c=synthetic_config(); c['imu_prototype']['vehicles']['car1']['imu_clock'].update(status='pending', source='not verified', source_origin_ns=None, destination_origin_ns=None, rate_numerator=None, rate_denominator=None, uncertainty_ns=None)
        f=ImuFilter('independent',c); self.assertTrue(f.blocked['car1']); self.assertFalse(f.blocked['car2']); self.assertFalse(f.snapshot(0)['car1']['valid'])
    def test_source_frame_motion_only(self):
        c,events,_,_=generate('nominal',15,100_000_000); p=c['imu_prototype']; p.update(frame_mode='source_odometry_motion_only',ranges_enabled=False,fusion_methods=['independent'])
        for cc in c['vehicles'].values():
            for name in ['initial_room_pose','antenna_body_xyz_m','base_height_m']: cc[name]={'status':'pending','source':'not available'}
        c['anchors_xyz_m']={'status':'pending','source':'not available'}
        f,ds=run(events,c); self.assertFalse(any(f.blocked.values())); self.assertEqual(f.snapshot(events[-1]['row']['receive_epoch_ns'])['car1']['frame_id'],'car1/odom')
        self.assertTrue(any(d['status']=='excluded_source_frame_ranges' for d in ds))
    def test_field_synthetic_assumptions_not_promoted(self):
        c=synthetic_config(); c['scope']='field'
        with self.assertRaises(ValueError): validate(c)
    def test_exact_integer_ns_and_holdout_gate(self):
        c,events,_,_=generate('nominal',1,100_000_000); events[0]['row']['header_epoch_ns']=float(events[0]['row']['header_epoch_ns'])
        with self.assertRaises(ValueError): validate_events(events,c)
        events[0]['row']['header_epoch_ns']=1; c['scope']='field'; events[0]['row']['experiment_id']='T09'
        with self.assertRaisesRegex(ValueError,'holdout'): validate_events(events,c)
    def test_no_mixed_experiment_history(self):
        c,events,_,_=generate('nominal',1,100_000_000); events[0]['row']['experiment_id']='other'
        with self.assertRaises(ValueError): validate_events(events,c)
    def test_cli_contract_no_overwrite_and_pose_marginal(self):
        with tempfile.TemporaryDirectory(prefix='imu-contract-') as tmp:
            root=Path(tmp); save(root/'input','nominal',17,200_000_000)
            command=[sys.executable,str(Path(__file__).with_name('replay.py')),'--events-jsonl',str(root/'input/events.jsonl.gz'),'--config',str(root/'input/config.template.json'),'--output',str(root/'run')]
            result=subprocess.run(command,capture_output=True,text=True); self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual({p.name for p in (root/'run').iterdir()},{'run.json','config.json','estimate.csv','decisions.jsonl.gz','summary.json'})
            with (root/'run/estimate.csv').open() as stream: reader=csv.DictReader(stream); self.assertEqual(reader.fieldnames,ESTIMATE_COLUMNS+EXTRA_COLUMNS); rows=list(reader)
            self.assertTrue(any(r['last_imu_record_index'] for r in rows)); cov=json.loads(next(r['pose_covariance'] for r in rows if r['pose_covariance'])); self.assertEqual(np.shape(cov),(3,3))
            from audit import audit
            report=audit(root/'run',root/'input/events.jsonl.gz',stride=1); self.assertEqual(report['status'],'PASS',report)
            self.assertGreater(report['counts']['sampled_F_Q'],0); self.assertGreater(report['counts']['sampled_H_Joseph'],0)
            # Serialized-evidence corruption must fail independently of the estimator.
            records=list(read_jsonl(root/'run/decisions.jsonl.gz'))
            segment=next(s for record in records if record['record_type']=='event_decision' for s in record['decision'].get('propagations',[]))
            segment['angular']['sample_epoch_ns']=segment['from_epoch_ns']+1
            (root/'run/decisions.jsonl.gz').unlink()
            with gzip_writer(root/'run/decisions.jsonl.gz') as stream:
                for record in records: append(stream,record)
            self.assertEqual(audit(root/'run',root/'input/events.jsonl.gz')['status'],'FAIL')
            result=subprocess.run(command,capture_output=True,text=True); self.assertEqual(result.returncode,1); self.assertIn('FileExistsError',result.stderr)
    def test_deterministic_gzip(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ['a','b']:
                with gzip_writer(Path(tmp)/name) as stream: append(stream,dict(x=1))
            self.assertEqual((Path(tmp)/'a').read_bytes(),(Path(tmp)/'b').read_bytes())


if __name__=='__main__': unittest.main(verbosity=2)
