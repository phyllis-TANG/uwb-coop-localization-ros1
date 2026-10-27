#!/usr/bin/env python3
"""Numerical weights, independent histories, hysteresis and causality checks."""
import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import numpy as np
from bridge import base_replay,imu_graph,PoseGraph,PoseObjective,frozen
from qconfig import default,values,validate
from qfrontend import Pipeline,semantic
from qgraph import WeightedPoseObjective,WeightedImuObjective,WeightedPoseGraph,WeightedImuGraph
from qpolicy import LinkPolicy
from qsimulate import generate,save,ORIGIN
from qio import read_jsonl,dump
from test_single_car_fixed_lag import problem


def collect(group='Q3',scenario='nominal',seed=101,duration=35_000_000_000,events=None,config=None):
    base,generated,_,_=generate(scenario,seed,duration)
    if config is None:config=default(group);config['base']=base;config['base']['arm']='F3' if group in ('Q1','Q3') else 'F0'
    output=[];graphs=[];ledger=[];events=generated if events is None else events
    p=Pipeline(config,events[0]['receive_epoch_ns'],publication_sink=output.append,graph_sink=graphs.append,ledger_sink=ledger.append)
    for event in events:p.ingest(event)
    p.finish();return p,output,graphs,ledger


def stable_output(rows):
    return [dict(pose=r['row']['pose'],status=r['row']['status'],state_epoch_ns=r['state_epoch_ns'],prior_matrix=r['row'].get('prior_matrix'),prior_offset=r['row'].get('prior_offset'),bias=r['row'].get('bias_rad_s'),marginalizations=r['row'].get('marginalizations')) for r in rows]


class WeightTests(unittest.TestCase):
    def problem(self,imu=False):
        m,t,l,o,x,p=problem(4);weights=[{key:[1.,.1,0.,.25][(i+j)%4] for j,key in enumerate(sorted(row))} for i,row in enumerate(o)]
        if imu:
            c=default('Q3')['base'];c['model']=m;x=np.column_stack((x,np.zeros(len(x))));prior=imu_graph.initial_prior(m,c)
            intervals=[dict(valid=True,start_epoch_ns=ORIGIN+i*10**9,end_epoch_ns=ORIGIN+(i+1)*10**9,dt_ns=10**9,raw_angle_rad=.08,gaps=[]) for i in range(3)]
            a=imu_graph.Objective(t,l,o,intervals,m,prior,c);b=WeightedImuObjective(t,l,o,intervals,m,prior,c,weights)
        else:a=PoseObjective(t,l,o,m,p);b=WeightedPoseObjective(t,l,o,m,p,weights)
        return a,b,x,weights
    def test_information_gain_exactly_once_and_cache(self):
        for imu in [False,True]:
            a,b,x,_=self.problem(imu);r,J=a.evaluate(x.ravel());rw,Jw=b.evaluate(x.ravel())
            for row,scale in b.weight_rows:
                self.assertAlmostEqual(rw[row]**2,r[row]**2*scale**2,places=11);np.testing.assert_allclose(Jw[row],J[row]*scale,atol=1e-13)
            for _ in range(3):np.testing.assert_array_equal(b.fun(x.ravel()),rw);np.testing.assert_array_equal(b.jac(x.ravel()),Jw)
    def test_weighted_jacobians_finite_difference(self):
        for imu in [False,True]:
            _,b,x,_=self.problem(imu);flat=x.ravel();eps=1e-6;num=np.column_stack([(b.fun(flat+np.eye(len(flat))[j]*eps)-b.fun(flat-np.eye(len(flat))[j]*eps))/(2*eps) for j in range(len(flat))]);np.testing.assert_allclose(b.jac(flat),num,atol=3e-6,rtol=3e-6)
    def test_only_UWB_rows_change(self):
        for imu in [False,True]:
            a,b,x,_=self.problem(imu);r,J=a.evaluate(x.ravel());rw,Jw=b.evaluate(x.ravel());indices={i for i,_ in b.weight_rows}
            others=[i for i in range(len(r)) if i not in indices];np.testing.assert_array_equal(rw[others],r[others]);np.testing.assert_array_equal(Jw[others],J[others])
    def test_unit_gain_graph_regression_through_marginalization(self):
        for imu in [False,True]:
            c=default('Q3' if imu else 'Q2')['base'];old=imu_graph.WindowGraph(c) if imu else PoseGraph(c['model']);new=WeightedImuGraph(c) if imu else WeightedPoseGraph(c)
            for t in range(35):
                local=np.array([.03*t,.001*t*t,.01*t]);interval=dict(valid=True,start_epoch_ns=ORIGIN+(t-1)*10**9,end_epoch_ns=ORIGIN+t*10**9,dt_ns=10**9,raw_angle_rad=.01,gaps=[])
                obs={k:float(np.linalg.norm(np.array([2.,2.,.2])-xyz))+c['model']['range_bias_m'][k] for k,xyz in c['model']['anchors_xyz_m'].items()}
                args=(t,local,obs,interval if t else None) if imu else (t,local,obs);a=old.update(*args);b=new.update(*args)
                np.testing.assert_array_equal(a['pose'],b['pose']);np.testing.assert_array_equal(a['prior_matrix'],b['prior_matrix']);np.testing.assert_array_equal(a['prior_offset'],b['prior_offset'])
            self.assertGreater(new.marginalizations,0);self.assertLessEqual(len(new.quality_weights),21)
    def test_weighted_marginal_information_affine_no_double_count(self):
        for imu in [False,True]:
            m,t,l,o,x,p=problem(4);c=default('Q3' if imu else 'Q2')['base'];c['model']=m
            graph=WeightedImuGraph(c) if imu else WeightedPoseGraph(c)
            if imu:x=np.column_stack((x,np.linspace(.001,.004,4)));p=imu_graph.initial_prior(m,c)
            weights=[{k:[.1,0.,1.][j%3] for j,k in enumerate(row)} for row in o];ids=[{k:f'{i}|{k}' for k in row} for i,row in enumerate(o)];graph.quality_weights=copy.deepcopy(weights);graph.quality_ids=copy.deepcopy(ids)
            intervals=[dict(valid=True,start_epoch_ns=ORIGIN+i*10**9,end_epoch_ns=ORIGIN+(i+1)*10**9,dt_ns=10**9,raw_angle_rad=.08,gaps=[]) for i in range(3)]
            full=WeightedImuObjective(t,l,o,intervals,m,p,c,weights) if imu else WeightedPoseObjective(t,l,o,m,p,weights);r,J=full.evaluate(x.ravel());d=x.shape[1]
            if imu:new,constant,info=graph._eliminate(x,t,l,o,intervals,m,p,c);retained=WeightedImuObjective(t[1:],l[1:],o[1:],intervals[1:],m,new,c,weights[1:])
            else:new,constant=graph._eliminate(x,t,l,o,m,p);info=graph.marginal_events[-1];retained=WeightedPoseObjective(t[1:],l[1:],o[1:],m,new,weights[1:])
            r2,J2=retained.evaluate(x[1:].ravel());A=J[:,:d];B=J[:,d:]-A@np.linalg.lstsq(A,J[:,d:],rcond=None)[0];rr=r-A@np.linalg.lstsq(A,r,rcond=None)[0]
            np.testing.assert_allclose(J2.T@J2,B.T@B,atol=1e-6,rtol=1e-9);np.testing.assert_allclose(J2.T@r2,B.T@rr,atol=1e-7,rtol=1e-8)
            self.assertAlmostEqual(r2@r2+constant,rr@rr,places=8);self.assertFalse(info['includes_retained_UWB']);self.assertEqual(set(info['consumed_quality_factor_ids']),set(ids[0].values()))
    def test_old_weights_not_revised_on_new_policy(self):
        c=default('Q2')['base'];gain=[1.]
        def provider(epoch,obs):return dict(weights={k:gain[0] for k in obs},ids={k:str(epoch)+'|'+k for k in obs})
        graph=WeightedPoseGraph(c,provider,origin=ORIGIN)
        for t in range(24):graph.update(t,np.zeros(3),{'node_10':4.})
        before=copy.deepcopy(graph.prior.matrix);gain[0]=0.;graph.update(24,np.zeros(3),{'node_10':100.})
        self.assertEqual(graph.quality_weights[-1]['node_10'],0.);self.assertTrue(all(r['node_10']==1. for r in graph.quality_weights[:-1]));self.assertGreater(np.linalg.norm(before),0.)


class PolicyTests(unittest.TestCase):
    def setUp(self):self.p=LinkPolicy(values(default('Q3')));self.t=0
    def step(self,s,reason=None):self.t+=10**9;return self.p.step(ORIGIN+self.t,s,reason)
    def test_persistence_and_disable(self):
        self.assertEqual(self.step(2.)['state'],'normal');self.assertEqual(self.step(2.)['state'],'downweighted');self.assertEqual(self.step(4.)['state'],'downweighted');self.assertEqual(self.step(4.)['state'],'disabled')
    def test_recovery_hysteresis(self):
        self.step(4);self.step(4)
        states=[self.step(.2)['state'] for _ in range(6)];self.assertEqual(states,['disabled','disabled','recovering','recovering','recovering','normal'])
    def test_unknown_not_healthy_and_holds_gain(self):
        initial=self.step(None,'GEOMETRY');self.assertEqual(initial['state'],'unknown');self.assertEqual(initial['information_multiplier'],1.)
        self.step(4);self.step(4);r=self.step(None,'NO_LINK');self.assertEqual(r['state'],'unknown');self.assertEqual(r['information_multiplier'],0.);self.assertFalse(r['monitorable'])
    def test_unknown_breaks_persistence(self):
        self.step(2);self.step(None,'GEOMETRY');self.assertEqual(self.step(2)['state'],'normal')
    def test_recovery_relapse(self):
        self.step(4);self.step(4)
        for _ in range(3):self.step(.1)
        self.assertEqual(self.step(2)['state'],'downweighted')
    def test_no_rewrite_same_factor(self):
        self.p.step(ORIGIN,1.)
        with self.assertRaises(ValueError):self.p.step(ORIGIN,.1)


class PipelineTests(unittest.TestCase):
    def test_disabled_path_native_F0_F3_exact(self):
        for group in ('Q0','Q1'):
            base,events,_,_=generate('nominal',101,35_000_000_000);base['arm']='F0' if group=='Q0' else 'F3';native=[];base_replay.execute(events,base,native.append);p,out,_,_=collect(group,events=events)
            self.assertEqual(len(native),len(out))
            for a,b in zip(native,out):
                for k in ('pose','prior_matrix','prior_offset','status','local_odom','range_medians_m','range_sample_counts'):self.assertEqual(a[k],b['row'][k],k)
            self.assertFalse(p.shadows)
    def test_enable_with_all_unit_weights_same_as_frozen(self):
        for group in ('Q2','Q3'):
            c=default(group);c['base']['model']['initial_heading_deg']=170.;c['controller']['warn_score']['value']=10000.;c['controller']['disable_score']['value']=20000.
            _,a,_,_=collect('Q0' if group=='Q2' else 'Q1',duration=35_000_000_000);_,b,_,_=collect(group,config=c,duration=35_000_000_000);self.assertEqual(stable_output(a),stable_output(b))
    def test_excluded_shadow_never_consumes_target_in_history_or_prior(self):
        _,events,_,_=generate('nominal',101,35_000_000_000);poison=copy.deepcopy(events)
        for e in poison:
            if e['kind']=='uwb':e['value']['node_10']+=1.7
        for group in ('Q2','Q3'):
            p,a,ga,la=collect(group,events=events);q,b,gb,lb=collect(group,events=poison)
            sa=[semantic(r) for r in ga if r['role']=='node_10'];sb=[semantic(r) for r in gb if r['role']=='node_10'];self.assertEqual(sa,sb)
            self.assertGreater(p.shadows['node_10'].graph.marginalizations,0);self.assertIsNot(p.main.graph.prior,p.shadows['node_10'].graph.prior)
            self.assertFalse(np.shares_memory(p.main.graph.prior.matrix,p.shadows['node_10'].graph.prior.matrix))
            for r in sa:
                self.assertTrue(all('node_10' not in obs for obs in r['row']['objective_snapshot']['observations']));self.assertTrue(all(all(g==1 for g in row.values()) for row in r['row']['objective_snapshot']['quality_weights']))
    def test_prefix_no_future_mutation(self):
        _,events,_,_=generate('uwb_step',101,35_000_000_000);changed=copy.deepcopy(events);cutoff=ORIGIN+30_000_000_000
        for e in changed:
            if e['receive_epoch_ns']>cutoff:
                if e['kind']=='uwb':e['value']={k:v+1. for k,v in e['value'].items()}
                if e['kind']=='imu':e['value']['angular_velocity_rad_s'][2]+=.2
        _,a,ga,la=collect(events=events);_,b,gb,lb=collect(events=changed)
        past=lambda rs:[r for r in rs if r['availability_cutoff_epoch_ns']<=cutoff]
        self.assertEqual(stable_output(past(a)),stable_output(past(b)));self.assertEqual([semantic(r) for r in past(ga)],[semantic(r) for r in past(gb)])
        ignore={'frozen_host_epoch_ns','frozen_host_monotonic_ns'}
        self.assertEqual([{k:v for k,v in r.items() if k not in ignore} for r in past(la)],[{k:v for k,v in r.items() if k not in ignore} for r in past(lb)])
    def test_unknown_geometry_and_missing_are_not_healthy(self):
        _,out,_,ledger=collect('Q3','weak_missing',duration=35_000_000_000)
        rows=[r for r in ledger if ORIGIN+15*10**9<r['state_epoch_ns']<ORIGIN+30*10**9]
        self.assertTrue(rows);self.assertTrue(all(r['policy']['state']=='unknown' for r in rows));self.assertTrue(any(r['actual_information_multiplier'] is None for r in rows))
        self.assertTrue(all(not r['information_admitted'] for r in rows if r['raw_aggregate_m'] is None))
    def test_ledger_frozen_before_main_and_source_cutoff(self):
        _,out,graphs,ledger=collect('Q3','uwb_step',duration=35_000_000_000);refs={r['record_id']:r for r in graphs}
        for r in ledger:
            if r['reference_record_id'] is not None:
                ref=refs[r['reference_record_id']];self.assertEqual(ref['excluded_target'],r['target']);self.assertEqual(ref['availability_cutoff_epoch_ns'],r['availability_cutoff_epoch_ns'])
            for dep in r['target_dependencies']:self.assertLessEqual(dep['identity']['receive_epoch_ns'],r['availability_cutoff_epoch_ns'])
        self.assertTrue(all(r['frozen_before_main_solve'] for r in ledger));self.assertTrue(any(r['actual_information_multiplier']<1 for r in ledger if r['actual_information_multiplier'] is not None))
    def test_postfit_residual_is_diagnostic_only(self):
        _,out,_,_=collect('Q3','uwb_step',duration=25_000_000_000)
        for r in out:
            for f in r['postfit_factor_diagnostics']:
                self.assertTrue(f['not_used_for_quality']);self.assertAlmostEqual(f['actual_weighted_residual']**2,f['quality_information_multiplier']*f['original_pseudo_huber_residual']**2)
    def test_generator_injections_sign_and_common_error(self):
        _,normal,_,_=generate('nominal',101,35_000_000_000);_,step,_,_=generate('uwb_step',101,35_000_000_000)
        for a,b in zip(normal,step):
            if a['kind']=='uwb':
                for k in a['value']:self.assertAlmostEqual(b['value'][k]-a['value'][k],.6 if k=='node_10' and ORIGIN+12*10**9<=a['header_epoch_ns']<ORIGIN+32*10**9 else 0.)
        _,events,truth,_=generate('common_turn_error',101,35_000_000_000);self.assertAlmostEqual(next(r for r in truth if r['epoch_ns']==ORIGIN+20*10**9)['bias_rad_s'],.025)
    def test_no_truth_labels_in_online_events(self):
        _,events,_,_=generate('gyro_drift',101,100_000_000)
        self.assertTrue(all(not ({'truth','true_pose','true_bias','fault_label','scenario'}&set(e)) for e in events))
    def test_buffers_and_total_graph_bound(self):
        p,out,_,_=collect('Q3',duration=40_000_000_000)
        self.assertEqual(len(p.shadows),4)
        for f in [p.main,*p.shadows.values()]:
            self.assertLessEqual(len(f.graph.times),21);self.assertLessEqual(f.graph.peak_transient_states,22);self.assertLessEqual(len(f.graph.quality_weights),21)
        self.assertLessEqual(len(p.recent.rows['uwb']),512);self.assertFalse(p.pending)
    def test_quality_off_explicit_ablation(self):
        c=default('Q3');c['quality_enabled']=False;c['base']['model']['initial_heading_deg']=170.
        p,a,_,_=collect(config=c,duration=25_000_000_000);_,b,_,_=collect('Q1',duration=25_000_000_000);self.assertFalse(p.shadows);self.assertEqual(stable_output(a),stable_output(b))
    def test_cli_outputs_and_paced_available_time(self):
        with tempfile.TemporaryDirectory(prefix='quality-fgo-') as tmp:
            root=Path(tmp);save(root/'input','nominal',101,5_000_000_000);c=default('Q3');c['base']['model']['initial_heading_deg']=170.;c['timing']['paced']=True;dump(root/'config.json',c)
            command=[sys.executable,str(Path(__file__).with_name('qrun.py')),'--events-jsonl',str(root/'input/events.jsonl.gz'),'--config',str(root/'config.json'),'--output',str(root/'run')];r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
            availability=list(read_jsonl(root/'run/availability.jsonl.gz'));self.assertEqual(len(availability),4)
            for row in availability:self.assertGreaterEqual(row['actual_release_delay_s'],1.);self.assertEqual(row['available_receive_epoch_ns'],ORIGIN+10_000_000+row['data_flushed_host_monotonic_ns']-row['host_anchor_monotonic_ns'])
            from qaudit import audit
            from qio import sha,gzip_writer,append
            good=audit(root/'run',sample_every=1);self.assertEqual(good['status'],'PASS',good)
            original=list(read_jsonl(root/'run/quality_ledger.jsonl.gz'));bad=copy.deepcopy(original);entry=next(r for r in bad if r['engineering_score'] is not None);entry['engineering_score']+=.3
            path=root/'run/quality_ledger.jsonl.gz';path.unlink()
            with gzip_writer(path) as stream:
                for item in bad:append(stream,item)
            metadata=json.loads((root/'run/run.json').read_text())
            for record in metadata['outputs']:
                if record['relative_path']=='quality_ledger.jsonl.gz':record['sha256']=sha(path);record['size_bytes']=path.stat().st_size
            dump(root/'run/run.json',metadata)
            broken=audit(root/'run');self.assertEqual(broken['status'],'FAIL');self.assertTrue(any('score differs' in e for e in broken['errors']),broken)
            r=subprocess.run(command,capture_output=True,text=True);self.assertEqual(r.returncode,1)
    def test_bad_units_and_reference_scale_rejected(self):
        c=default('Q3');c['controller']['score_scale_m']['units']='variance'
        with self.assertRaises(ValueError):validate(c)
        c=default('Q3');c['controller']['clear_score']['value']=5.
        with self.assertRaises(ValueError):validate(c)


class EvaluationTests(unittest.TestCase):
    def test_thirteen_consecutive_seconds_is_one_episode(self):
        from qevaluate import episode_summary
        rows=[];available={}
        for i in range(14):
            pid=str(i);rows.append(dict(publication_id=pid,state_epoch_ns=ORIGIN+i*10**9,policy=dict(information_multiplier=.1 if i<13 else 1.,state='downweighted' if i<13 else 'normal',monitorable=True)));available[pid]=dict(available_receive_epoch_ns=ORIGIN+(i+1)*10**9)
        r=episode_summary(rows,available);self.assertEqual(r['attenuation_episodes'],1);self.assertAlmostEqual(r['attenuated_duration_s'],13.);self.assertAlmostEqual(r['monitorable_duration_s'],13.)
    def test_conditional_fault_denominator_requires_consecutive_known(self):
        from qevaluate import event_evaluate
        event=dict(event_id='fixture',target='node_10',start_epoch_ns=ORIGIN,end_epoch_ns=ORIGIN+5*10**9);rows=[];available={}
        for i,known in enumerate([True,False,True]):
            pid=str(i);rows.append(dict(publication_id=pid,state_epoch_ns=ORIGIN+i*10**9,policy=dict(information_multiplier=1.,state='normal',monitorable=known)));available[pid]=dict(available_receive_epoch_ns=ORIGIN+(i+1)*10**9)
        self.assertFalse(event_evaluate(event,rows,available,[])['monitorable_event']);rows[1]['policy']['monitorable']=True;self.assertTrue(event_evaluate(event,rows,available,[])['monitorable_event'])
    def test_alarm_delay_uses_available_not_state_time(self):
        from qevaluate import event_evaluate
        event=dict(event_id='fixture',target='node_10',start_epoch_ns=ORIGIN+2*10**9,end_epoch_ns=ORIGIN+5*10**9);rows=[];available={}
        for i,gain in enumerate([1.,1.,.1,.1]):
            pid=str(i);rows.append(dict(publication_id=pid,state_epoch_ns=ORIGIN+i*10**9,policy=dict(information_multiplier=gain,state='normal' if gain==1 else 'downweighted',monitorable=True)));available[pid]=dict(available_receive_epoch_ns=ORIGIN+(i+1)*10**9+100_000_000)
        r=event_evaluate(event,rows,available,[]);self.assertAlmostEqual(r['alarm_delay_s'],1.1);self.assertIsNone(r['alarm_recovery_delay_s'])

class DiagnosticTests(unittest.TestCase):
    def test_raw_motion_conflict_never_controls_UWB(self):
        base,events,_,_=generate('nominal',101,8_000_000_000);config=default('Q3');config['base']=base;config['base']['arm']='F3';a=[];b=[]
        left=Pipeline(config,events[0]['receive_epoch_ns'],publication_sink=a.append);right=Pipeline(config,events[0]['receive_epoch_ns'],publication_sink=b.append);original=right.diag_gyro.integrate
        def fake(*args):
            r=original(*args)
            if r['valid']:r['raw_angle_rad']+=1.
            return r
        right.diag_gyro.integrate=fake
        for e in events:left.ingest(e);right.ingest(e)
        left.finish();right.finish();self.assertEqual(stable_output(a),stable_output(b));self.assertTrue(all(r['motion_conflict_diagnostic']['not_used_for_quality'] for r in b))
    def test_common_angle_fault_can_have_small_motion_disagreement(self):
        _,events,_,_=generate('common_turn_error',101,35_000_000_000);_,rows,_,_=collect('Q1',events=events);differences=[r['motion_conflict_diagnostic']['raw_odom_rate_minus_gyro_rad'] for r in rows if ORIGIN+15*10**9<r['state_epoch_ns']<ORIGIN+30*10**9];self.assertLess(np.mean(np.abs(differences)),.005)


if __name__=='__main__':unittest.main(verbosity=2)
