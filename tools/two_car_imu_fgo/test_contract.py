"""Pre-matrix contracts. Fixed tolerances are preregistered in CHECKPOINT_01."""
import copy
import json
import math
import unittest
from unittest.mock import patch
import numpy as np
from scipy.optimize import least_squares
from configuration import default_config
from core import Objective,WindowGraph,initial,eliminate,car_config,CARS
from frontend import execute
from pinned import f0,f0_front,f0_sim,single,integration
from simulate import make_case
import independent as ind


def interval(t,rate=.02,valid=True):
    return dict(valid=valid,start_epoch_ns=t*10**9,end_epoch_ns=(t+1)*10**9,dt_ns=10**9,
                raw_angle_rad=rate if valid else None,partial_angle_rad=rate,segments=[],gaps=[] if valid else [dict(start_epoch_ns=t*10**9,end_epoch_ns=(t+1)*10**9)])

def fixture(n=4):
    c=default_config();t=np.arange(n,dtype=float);local=np.zeros((n,2,3));states=np.tile(initial(c).point,(n,1));obs=[];peers=[]
    for k in range(n):
        row={}
        for i,car in enumerate(CARS):
            states[k,4*i:4*i+4]+=[.04*k,.007*k*k,.02*k,.002*i]
            local[k,i]=[.03*k,.003*k*k,.01*k]
            xyz=ind.ant(states[k,4*i:4*i+4],c['models'][car])
            row[car]={key:float(np.linalg.norm(xyz-v))+.005 for key,v in c['models'][car]['anchors_xyz_m'].items()}
        obs.append(row);peers.append(float(np.linalg.norm(ind.ant(states[k,:4],c['models']['car1'])-ind.ant(states[k,4:],c['models']['car2'])))+.08)
    edges=[{car:interval(k,.018+.002*i) for i,car in enumerate(CARS)} for k in range(n-1)]
    return c,t,local,obs,peers,edges,states,initial(c)


def strip_times(value):
    if isinstance(value,dict):return {k:strip_times(v) for k,v in value.items() if not ('wall_s' in k or k.startswith('estimated_worker'))}
    if isinstance(value,list):return [strip_times(v) for v in value]
    return value


class Contracts(unittest.TestCase):
    def test_disabled_exact_original_six_dimensional(self):
        c,e,_,_=make_case(7,'nominal')
        e=[r for r in e if r['receive_epoch_ns']<=f0_sim.EPOCH_NS+27*10**9]
        for new,old in [('M0','D0'),('M1','D1')]:
            a=[];r=f0_front.JointReplay(c,old,a.append,e[0]['receive_epoch_ns'])
            for raw in e:r.ingest(raw)
            r.finish();b=[];q=execute(e,c,new,b.append)
            self.assertIs(type(q.graph),f0.WindowGraph)
            self.assertEqual(len(a),len(b));self.assertGreater(a[-1]['marginalizations'],0)
            for x,y in zip(a,b):
                for key in ('pose','prediction_pose','snapshot','optimizer','marginalization_details','bins','state_epoch_ns'):
                    self.assertEqual(x[key],y[key],key)
                self.assertEqual(y['bias_rad_s'],dict(car1=None,car2=None));self.assertEqual(y['state_dimension_per_keyframe'],6)

    def test_independent_F3_objective_and_solution(self):
        c,t,l,o,p,e,x,pr=fixture();obj=Objective(t,l,o,p,e,c,pr,False);r,J=obj.evaluate(x.ravel());H=J.T@J;g=J.T@r
        expectedH=np.zeros_like(H);expectedg=np.zeros_like(g);cost=0.;solutions=[]
        for i,car in enumerate(CARS):
            cols=(8*np.arange(len(t))[:,None]+np.arange(4*i,4*i+4)).ravel();cfg=car_config(c,car)
            part=single.Objective(t,l[:,i],[row[car] for row in o],[a[car] for a in e],c['models'][car],single.initial_prior(c['models'][car],cfg),cfg)
            rr,jj=part.evaluate(x[:,4*i:4*i+4].ravel());expectedH[np.ix_(cols,cols)]=jj.T@jj;expectedg[cols]=jj.T@rr;cost+=rr@rr
            solutions.append(least_squares(part.fun,x[:,4*i:4*i+4].ravel(),jac=part.jac,ftol=1e-7,xtol=1e-7,gtol=1e-7,tr_solver='exact').x.reshape(-1,4))
        np.testing.assert_allclose(H,expectedH,atol=1e-7,rtol=1e-9);np.testing.assert_allclose(g,expectedg,atol=1e-7,rtol=1e-9);self.assertAlmostEqual(r@r,cost,places=8)
        solution=least_squares(obj.fun,x.ravel(),jac=obj.jac,ftol=1e-7,xtol=1e-7,gtol=1e-7,tr_solver='exact').x.reshape(-1,8)
        for i in range(2):
            np.testing.assert_allclose(solution[:,4*i:4*i+3],solutions[i][:,:3],atol=1e-4,rtol=0)
            np.testing.assert_allclose(solution[:,4*i+3],solutions[i][:,3],atol=1e-5,rtol=0)

    def test_moving_independent_F3_through_marginalization(self):
        c,t,l,o,p,e,x,pr=fixture(26);g=WindowGraph(c,False);others=[single.WindowGraph(car_config(c,car)) for car in CARS]
        for k in range(len(t)):
            g.next_intervals=None if k==0 else e[k-1];r=g.update(t[k],l[k],o[k],p[k])
            for i,car in enumerate(CARS):
                rr=others[i].update(t[k],l[k,i],o[k][car],None if k==0 else e[k-1][car])
                np.testing.assert_allclose(np.array(r['pose'])[4*i:4*i+3],rr['pose'],atol=1e-4,rtol=0)
                self.assertLess(abs(r['pose'][4*i+3]-rr['bias_rad_s']),1e-5)
        self.assertEqual(g.marginalizations,5)

    def test_Jacobian_and_full_linear_system_Schur_no_double_consumption(self):
        c,t,l,o,p,e,x,pr=fixture();pr.matrix[0,7]=.8;pr.offset[2]=.3
        for enabled in (False,True):
            obj=Objective(t,l,o,p,e,c,pr,enabled);flat=x.ravel();step=1e-6
            num=np.column_stack([(obj.fun(flat+np.eye(len(flat))[i]*step)-obj.fun(flat-np.eye(len(flat))[i]*step))/(2*step) for i in range(len(flat))])
            np.testing.assert_allclose(obj.jac(flat),num,atol=3e-6,rtol=3e-6)
            carried,constant,detail=eliminate(x,t,l,o,p,e,c,pr,enabled);ind.marginal(detail,c,8,enabled)
            rr,JJ=obj.evaluate(flat);remaining=Objective(t[1:],l[1:],o[1:],p[1:],e[1:],c,carried,enabled);r2,J2=remaining.evaluate(x[1:].ravel())
            a,b=JJ[:,:8],JJ[:,8:];jp=b-a@np.linalg.lstsq(a,b,rcond=None)[0];rp=rr-a@np.linalg.lstsq(a,rr,rcond=None)[0]
            np.testing.assert_allclose(J2.T@J2,jp.T@jp,atol=1e-5,rtol=1e-8);np.testing.assert_allclose(J2.T@r2,jp.T@rp,atol=1e-6,rtol=1e-8)
            for delta in np.random.default_rng(7).normal(0,.002,(4,len(flat)-8)):
                d0=np.linalg.lstsq(a,-rr-b@delta,rcond=None)[0]
                self.assertLess(abs(np.linalg.norm(rr+a@d0+b@delta)**2-(np.linalg.norm(r2+J2@delta)**2+constant)),1e-6)

    def test_peer_really_adds_one_objective_row_and_bias_cross_prior(self):
        c,t,l,o,p,e,x,pr=fixture();r=Objective(t,l,o,p,e,c,pr,True).fun(x.ravel());r0=Objective(t,l,o,p,e,c,pr,False).fun(x.ravel())
        self.assertEqual(len(r)-len(r0),len(t));self.assertGreater(r@r-r0@r0,0)
        after,_,_=eliminate(x,t,l,o,p,e,c,pr,True);H=after.matrix.T@after.matrix
        self.assertGreater(np.linalg.norm(H[:4,4:]),.01);self.assertGreater(np.linalg.norm(H[[3,7]][:,[0,1,2,4,5,6]]),.01)

    def test_independent_stop_keeps_objective_prior_once(self):
        from core import solve_independent
        c,t,l,o,p,e,x,pr=fixture();obj=Objective(t,l,o,p,e,c,pr,False)
        result=solve_independent(obj,x,c)
        snap=dict(times_s=t.tolist(),local=l.tolist(),observations=o,peers_m=[None]*len(t),intervals=e,prior=pr.record(),peer_enabled=False)
        r=ind.residual(snap,result.x,c,8)
        self.assertLess(abs(r@r/2-result.cost),1e-7)
        self.assertEqual([len(p.prior.offset) for p in obj.parts],[0,0])

    def test_constant_bias_sign_and_wrap(self):
        c,t,l,o,p,e,x,pr=fixture(2)
        x[:,3]=.025;x[:,7]=-.015
        for i,car in enumerate(CARS):
            x[0,4*i+2]=math.pi-.01;x[1,4*i+2]=-math.pi+.01;e[0][car]=interval(0,.02+x[0,4*i+3])
        obj=Objective(t,l,[{car:{} for car in CARS} for _ in t],[None,None],e,c,pr,False)
        self.assertLess(np.linalg.norm(obj.fun(x.ravel())[-2:]),1e-10)
        g=WindowGraph(c,False);g.update(0,l[0],o[0],None);g.next_intervals=e[0]
        pred=g.update(1,l[1],o[1],None)['prediction_pose'];self.assertAlmostEqual(pred[2],pr.point[2]+e[0]['car1']['raw_angle_rad'])

    def test_missing_gyro_holds_startup_and_failed_prediction(self):
        c,t,l,o,p,e,x,pr=fixture(3);c['optimizer']['max_nfev']=1;g=WindowGraph(c,True)
        a=g.update(0,l[0],o[0],p[0]);l[1:,0,2]=[2.,-2.]
        for k in (1,2):
            e[k-1]['car1']=interval(k-1,valid=False);g.next_intervals=e[k-1];b=g.update(k,l[k],o[k],p[k])
            self.assertEqual(b['prediction_pose'][2],a['pose'][2]);self.assertFalse(b['estimate_valid']['car1']);self.assertFalse(b['odom_yaw_fallback']);a=b
        self.assertIn('solver_failed',b['status'])

    def test_prefix_after_marginalization_and_no_future(self):
        c,e,_,_=make_case(8,'nominal');cutoff=f0_sim.EPOCH_NS+27*10**9
        prefix=[x for x in e if x['receive_epoch_ns']<=cutoff];long=[x for x in e if x['receive_epoch_ns']<=cutoff+2*10**9]
        for method in ('M0','M1','M2','M3'):
            a=[];execute(prefix,c,method,a.append);b=[];execute(long,c,method,b.append)
            self.assertEqual(strip_times(a),strip_times([r for r in b if r['availability_cutoff_epoch_ns']<=prefix[-1]['receive_epoch_ns']]))
            self.assertGreater(a[-1]['marginalizations'],0)

    def test_gyro_axis_unit_frame_negative_and_duplicates(self):
        c,e,_,_=make_case(9,'nominal');e=[x for x in e if x['receive_epoch_ns']<=f0_sim.EPOCH_NS+4*10**9]
        a=[];execute(e,c,'M3',a.append);changed=copy.deepcopy(e)
        for row in changed:
            if row['kind']=='imu':row['value']['angular_velocity_rad_s'][2]*=-1
        for car in CARS:c['angular'][car]['body_z_in_imu_frame']['value']=[0,0,-1]
        b=[];execute(changed,c,'M3',b.append)
        self.assertEqual([r['pose'] for r in a],[r['pose'] for r in b])
        for row in changed:
            if row['kind']=='imu':row['value']['units']='deg/s'
        b=[];rep=execute(changed,c,'M3',b.append);self.assertFalse(b[-1]['angular_valid']['car1'])
        self.assertGreater(rep.angular_decisions['car1']['unsupported_gyro_units'],0)
        buf=integration.AngularBuffer();ident=dict(mapped_header_epoch_ns=10,receive_epoch_ns=11)
        self.assertEqual(buf.add(ident,.2),'angular_control_accepted');self.assertEqual(buf.add(ident,.2),'duplicate_or_out_of_order_angular_source')
        ident['mapped_header_epoch_ns']=12;self.assertEqual(buf.add(ident,.2),'angular_source_after_receipt')

    def test_input_matching_and_bounded_eight_dimensional_cache(self):
        c,e,_,_=make_case(10,'car1_gyro_gap');e=[x for x in e if x['receive_epoch_ns']<=f0_sim.EPOCH_NS+28*10**9]
        results=[]
        for method in ('M0','M1','M2','M3'):
            rows=[];r=execute(e,c,method,rows.append);results.append(rows)
            self.assertLessEqual(r.graph.peak_solve_states,21);self.assertLessEqual(r.graph.peak_transient_states,22)
            self.assertTrue(all(b.peak<=512 for b in r.angular.values()))
        for rows in results[1:]:self.assertEqual([r['bins'] for r in results[0]],[r['bins'] for r in rows])
        self.assertEqual(results[-1][-1]['scalar_variables'],168);self.assertFalse(results[-1][-1]['angular_valid']['car1']);self.assertTrue(results[-1][-1]['angular_valid']['car2'])

    def test_missing_and_valid_zero_bias_semantics(self):
        from replay import csv_rows
        c,e,_,_=make_case(11,'nominal');e=[x for x in e if x['receive_epoch_ns']<=f0_sim.EPOCH_NS+3*10**9]
        a=[];execute(e,c,'M0',a.append);self.assertTrue(all(x['bias_rad_s'] is None for r in a for x in csv_rows(r,c)))
        b=[];execute(e,c,'M2',b.append);self.assertEqual(b[0]['bias_rad_s']['car1'],0.);self.assertEqual(list(csv_rows(b[0],c))[0]['bias_rad_s'],0.)

    def test_independent_reader_rejects_semantic_corruption(self):
        c,t,l,o,p,e,x,pr=fixture()
        _,_,m=eliminate(x,t,l,o,p,e,c,pr,True)
        for kind in ('cross','affine','constant','retained_wall'):
            bad=copy.deepcopy(m)
            if kind=='cross':
                a=np.asarray(bad['after']['matrix']);a[:4,4:]=0.;bad['after']['matrix']=a.tolist()
            elif kind=='affine':bad['after']['offset']=[0.]*8
            elif kind=='constant':bad['constant']+=.1
            else:bad['old_observations']['car1']['node_2']+=.3
            with self.assertRaises(ValueError):ind.marginal(bad,c,8,True)

    def test_serialized_contract_and_independent_complete_readback(self):
        import tempfile
        from pathlib import Path
        from simulate import save
        from replay import run
        from io_utils import write_lines,lines
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);save(root/'input',7,'nominal')
            events=list(lines(root/'input/events.jsonl.gz'))
            write_lines(root/'short.jsonl.gz',[e for e in events if e['receive_epoch_ns']<=f0_sim.EPOCH_NS+24*10**9])
            for method in ('M0','M1','M2','M3'):
                run(root/'short.jsonl.gz',root/'input/config.json',method,root/method)
                result=ind.audit_run(root/method,root/'short.jsonl.gz')
                self.assertEqual(result['status'],'PASS');self.assertGreater(result['counts']['marginalizations'],0)

    def test_missing_edge_rank_deficient_prior_basis_matches_two_F3(self):
        c,t,l,o,p,e,x,pr=fixture(30);e[3]['car1']=interval(3,valid=False)
        g=WindowGraph(c,False);others=[single.WindowGraph(car_config(c,car)) for car in CARS];canonicalized=0
        for k in range(len(t)):
            g.next_intervals=None if k==0 else e[k-1];r=g.update(t[k],l[k],o[k],p[k])
            self.assertNotIn('solver_error',r['status'])
            for item in r['marginalization_details']:
                ind.marginal(item,c,8,False);canonicalized+=int(item.get('independent_basis_canonicalized',False))
            for i,car in enumerate(CARS):
                rr=others[i].update(t[k],l[k,i],o[k][car],None if k==0 else e[k-1][car])
                np.testing.assert_allclose(np.array(r['pose'])[4*i:4*i+3],rr['pose'],atol=1e-4,rtol=0)
                self.assertLess(abs(r['pose'][4*i+3]-rr['bias_rad_s']),1e-5)
        self.assertGreater(canonicalized,0)

    def test_rank_deficient_elimination_does_not_invent_information(self):
        from core import Prior
        c,t,l,o,p,e,x,pr=fixture(2);pr=Prior(np.zeros(8),np.zeros((0,8)),np.zeros(0));x=np.zeros((2,8))
        for car in CARS:e[0][car]=interval(0,valid=False)
        after,constant,detail=eliminate(x,t,np.zeros((2,2,3)),[{c:{} for c in CARS}]*2,[None,None],e,c,pr,False)
        self.assertLess(detail['rank_old'],8);self.assertLess(np.linalg.norm(after.matrix),1e-9);ind.marginal(detail,c,8,False)


if __name__=='__main__':unittest.main(verbosity=2)
