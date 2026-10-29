import copy
import json
import math
import unittest
import numpy as np
from binding import graph, legacy, frontend
from common import ROOT
from engine import TrackedGraph, filtered
from influence import Primitives, Influence, noise_matrix
from monitors import four_anchor, separation, antenna, antenna_jacobian
from decisions import declarations, network


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT/'tools/two_car_fixed_lag_fgo_v1/config.json').read_text())

    def fixture(self):
        config = copy.deepcopy(self.config)
        pose = graph.joint_initial(config).point
        observations = {c:{k:float(np.linalg.norm(antenna(pose[3*i:3*i+3],config['models'][c])-xyz))
                           for k,xyz in config['models'][c]['anchors_xyz_m'].items()} for i,c in enumerate(legacy.CARS)}
        peer = float(np.linalg.norm(antenna(pose[:3],config['models']['car1'])-antenna(pose[3:],config['models']['car2'])))
        return config,pose,observations,peer

    def test_cli_import_namespace(self):
        import run as runner
        self.assertEqual(runner.evaluate.__module__,'evaluate')
        from pathlib import Path
        self.assertEqual(Path(runner.evaluate.__code__.co_filename).parent,Path(__file__).parent)

    def test_known_four_anchor_model(self):
        config,p,obs,peer = self.fixture()
        for car in legacy.CARS:
            value=four_anchor(obs[car],config['models'][car],{k:17 for k in obs[car]},'engineering_0.2m')
            self.assertTrue(value['computable']); self.assertEqual(value['df'],2)
            self.assertLess(value['statistic'],1e-18)

    def test_missing_invalid_unobservable(self):
        config,p,obs,peer=self.fixture(); model=config['models']['car1']
        self.assertFalse(four_anchor({},model,{},'engineering_0.2m')['computable'])
        bad=copy.deepcopy(obs['car1']);bad['node_10']=float('nan')
        self.assertFalse(four_anchor(bad,model,{},'engineering_0.2m')['computable'])
        for k in model['anchors_xyz_m']:model['anchors_xyz_m'][k]=[1.,1.,2.]
        self.assertFalse(four_anchor(obs['car1'],model,{},'engineering_0.2m')['computable'])

    def test_correlated_linear_least_squares_known_covariance(self):
        a=np.array([[1.,0.],[0.,1.],[1.,1.],[1.,-1.]])
        kf=np.linalg.pinv(a); ks=np.zeros_like(kf);ks[:,:2]=np.linalg.pinv(a[:2])
        d=np.array([.1,-.2]);out=separation(d,[0.,0.],kf,ks)
        self.assertTrue(out['computable'])
        expected=(kf-ks)@(kf-ks).T
        np.testing.assert_allclose(out['covariance'],expected,atol=1e-15)
        # A nested single excluded scalar produces rank one, so must reject 2D test.
        self.assertEqual(out['rank'],2)

    def test_shared_noise_not_independent(self):
        kf=np.array([[1.,0.,1.,0.],[0.,1.,0.,1.]])
        ks=np.array([[1.,0.,0.,0.],[0.,1.,0.,0.]])
        out=separation([.2,.3],[0.,0.],kf,ks)
        np.testing.assert_allclose(out['covariance'],np.eye(2))
        np.testing.assert_allclose(out['cross_covariance'],np.eye(2))
        self.assertAlmostEqual(out['statistic'],.13)
        np.testing.assert_allclose(out['independent_sum_covariance'],3*np.eye(2))
        self.assertFalse(separation([1,1],[0,0],ks,ks)['computable'])

    def test_antenna_rotated_jacobian(self):
        model=self.config['models']['car1']; p=np.array([1.,2.,2.9]); actual=antenna_jacobian(p,model)
        numeric=np.column_stack([(antenna(p+np.eye(3)[i]*1e-6,model)[:2]-antenna(p-np.eye(3)[i]*1e-6,model)[:2])/2e-6 for i in range(3)])
        np.testing.assert_allclose(actual,numeric,atol=1e-9)

    def test_all_source_history_and_noise_no_leak(self):
        config,p,obs,peer=self.fixture(); primitives=Primitives()
        for group in ('car1_absolute','car2_absolute','peer'):
            a=TrackedGraph(config,primitives,group);b=TrackedGraph(config,primitives,group)
            maina=graph.WindowGraph(config,True);mainb=graph.WindowGraph(config,True)
            for t in range(1,27):
                changed=copy.deepcopy(obs); pv=peer
                if group=='peer':pv += .7
                else:
                    car=group.split('_')[0]
                    for k in changed[car]:changed[car][k] += .3
                local=np.zeros((2,3))
                a.update(t,local,obs,peer);b.update(t,local,changed,pv)
                maina.update(t,local,obs,peer);mainb.update(t,local,changed,pv)
            self.assertGreater(a.marginalizations,0)
            self.assertEqual(a.history(),b.history())
            self.assertGreater(np.linalg.norm(maina.states[-1]-mainb.states[-1]),1e-3)
            prefix='peer|' if group=='peer' else 'wall|'+group.split('_')[0]+'|'
            self.assertFalse(any(k.startswith(prefix) for k in a.noise.record()['prior_noise_columns']))
            self.assertFalse(np.shares_memory(a.prior.matrix,b.prior.matrix))

    def test_frozen_graph_identity_through_marginalization(self):
        config,p,obs,peer=self.fixture();a=TrackedGraph(config,Primitives());b=graph.WindowGraph(config,True)
        for t in range(1,27):
            local=np.array([[.001*t,0.,.001*t],[0.,.002*t,-.001*t]])
            ra=a.update(t,local,obs,peer);rb=b.update(t,local,obs,peer)
            self.assertEqual(ra['pose'],rb['pose']);self.assertEqual(a.snapshot(),b.snapshot())
            self.assertEqual(a.eliminated_constant,b.eliminated_constant)

    def test_noise_derivative_finite_difference(self):
        config,p,obs,peer=self.fixture();times=[1.,2.];states=np.array([p,p]);local=np.zeros((2,2,3));obs=[copy.deepcopy(obs),copy.deepcopy(obs)]
        obj=graph.Objective(times,local,obs,[peer,peer],config,graph.joint_initial(config),True)
        b,j=noise_matrix(obj,states,Influence(Primitives()).prior_b,Primitives())
        eps=1e-6
        plus=copy.deepcopy(obs);minus=copy.deepcopy(obs)
        plus[0]['car1']['node_10']+=eps*.2;minus[0]['car1']['node_10']-=eps*.2
        def residual(o):return graph.Objective(times,local,o,[peer,peer],config,graph.joint_initial(config),True).fun(states.ravel())
        numeric=(residual(plus)-residual(minus))/(2*eps)
        np.testing.assert_allclose(numeric,b[:,Primitives().index['wall|car1|1|node_10']],atol=1e-8)

    def test_missing_odom_does_not_republish_stale_history(self):
        from engine import IntegrityReplay
        config,p,obs,peer=self.fixture();saved=[];worker=IntegrityReplay(config,saved.append,0)
        bins={car:dict(observations={},sample_counts={},local_odom=None) for car in legacy.CARS}
        worker.publish(dict(state_time_s=3.,accepted_graph=False,status='missing_odom_bracket',
            bins=bins,availability_cutoff_s=4.,update_wall_s=0.,marginalization_details=[]))
        row=saved[0]
        self.assertNotIn('linear_evidence',row)
        self.assertTrue(all(not ds['available'] for pair in row['monitor']['declarations'].values() for ds in pair))
        self.assertTrue(all(not details for details in row['marginal_evidence'].values()))

    def test_unsupported_odom_covariance_gap_is_explicit_unknown(self):
        config,p,obs,peer=self.fixture();g=TrackedGraph(config,Primitives())
        for stamp in (1,3,4):result=g.update(stamp,np.zeros((2,3)),obs,peer)
        self.assertTrue(result['accepted_graph'])
        self.assertIsNone(g.noise.last_k)
        self.assertIn('odom|',g.noise.record()['failure_reason'])

    def test_real_solver_failure_is_unknown(self):
        from unittest.mock import patch
        from engine import MonitoredGraph
        config,p,obs,peer=self.fixture();g=MonitoredGraph(config)
        for t in (1,2):g.update(t,np.zeros((2,3)),obs,peer)
        with patch.object(graph,'least_squares',side_effect=ValueError('controlled solver failure')):
            result=g.update(3,np.zeros((2,3)),obs,peer)
        self.assertFalse(result['accepted_graph'])
        self.assertEqual(result['status'],'predict_only_solver_error')
        self.assertTrue(all(not v['computable'] for pair in g.current['ss'].values() for v in pair))
        self.assertEqual(g.current['b0']['state'],'unknown')

    def test_known_linear_qr_history_matches_batch(self):
        # Independent 1D two-epoch linear model, shared prior/odometry and
        # two measurement groups; QR boundary noise agrees with full batch.
        j=np.array([[2.,0.],[-3.,3.],[4.,0.],[0.,5.]])
        b=-np.eye(4)
        batch=-np.linalg.pinv(j)@b
        q,_=np.linalg.qr(j[:3,:1],mode='complete')
        jp=q[:,1:].T@j[:3,1:]
        bp=q[:,1:].T@b[:3]
        j_reduced=np.vstack([jp,[[5.]]]); b_reduced=np.vstack([bp,b[3:]])
        reduced=-np.linalg.pinv(j_reduced)@b_reduced
        np.testing.assert_allclose(reduced[0],batch[1],atol=1e-14)
        # Keeping full/sub correlation differs from treating them independent.
        sub=np.array([[2.,0.],[-3.,3.],[0.,5.]])
        bs=b[[0,1,3]];k_sub=-np.linalg.pinv(sub)@bs
        diff=batch[1]-k_sub[1]
        variance=float(diff@diff)
        self.assertGreater(variance,0)
        self.assertLess(variance,float(batch[1]@batch[1]+k_sub[1]@k_sub[1]))

    def test_failure_unknown_never_success(self):
        unknown=dict(computable=False,statistic=None,reason='FAILED')
        m=dict(b0=dict(state='unknown',reason='STARTUP',engineering_q=None),
               b1={noise:{c:unknown for c in legacy.CARS} for noise in ['engineering_0.2m','raw_0.04m','median_iid_asymptotic']},
               ss={g:[unknown,unknown] for g in ['car1_absolute','car2_absolute','peer']})
        for group in declarations(m,True).values():
            for d in group:self.assertFalse(d['available']);self.assertFalse(d['alarm']);self.assertFalse(d['computable'])
        self.assertTrue(network([dict(alarm=True,computable=True),dict(alarm=False,computable=False)])['alarm'])


if __name__=='__main__':unittest.main()
