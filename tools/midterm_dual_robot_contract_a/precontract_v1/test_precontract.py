import copy
import json
from pathlib import Path
import sys
import unittest
from examples import C,K,P,small_input,tree_fixture,composite_fixture

REJECTIONS=[]

def rebuild(p):
    box=[[None,None] for _ in range(4)]
    for rec in p['directions']:
        i=(0 if rec['car']=='p' else 2)+rec['axis'];box[i][0 if rec['sign']<0 else 1]=rec['adopted_endpoint']
    p['contracted_domain']=box

def inside(point,box):return all(a<=C.F(v)<=b for v,(a,b) in zip(point,map(C.interval,box)))

class PrecontractTests(unittest.TestCase):
    def setUp(self):
        self.x=small_input();self.p=P.propose(self.x,clock=lambda:0.0)
    def reject(self,func,code):
        try:func()
        except (ValueError,KeyError,TypeError,IndexError) as e:
            self.assertIn(code,str(e));REJECTIONS.append({'test':self._testMethodName,'accepted':False,'reason':str(e)});return
        self.fail('damaged certificate accepted')
    def test_01_hand_normal_shrink(self):
        z=C.verify_preprocessing(self.x,self.p)
        self.assertEqual(z['contracted_domain'],[['1/8','31/8']]*4)
        self.assertTrue(inside(['2']*4,z['contracted_domain']))
    def test_02_joint_composite(self):
        c=composite_fixture(self.x,self.p);r=C.check_composite(self.x,c)
        self.assertTrue(r['accepted']);self.assertFalse(r['original_domain_contact']);self.assertTrue(r['contracted_domain_contact'])
    def test_03_collinear_both_mirrors(self):
        x=small_input('collinear');p=P.propose(x,clock=lambda:0.0);C.verify_preprocessing(x,p)
        for point in (['0','1','0','-1'],['0','-1','0','1']):
            self.assertTrue(inside(point,p['contracted_domain']))
            self.assertLessEqual(K.bounds(x,[[s,s] for s in point],'4d')[1],26)
        self.assertEqual(p['contracted_domain'][1],['-5','5'])
    def test_04_closed_boundary_exact_event(self):
        x=small_input('boundary');p=P.propose(x,clock=lambda:0.0);r=C.check_composite(x,composite_fixture(x,p))
        point=['1','0','0','0'];self.assertEqual(K.bounds(x,[[s,s] for s in point],'4d'),(26,26))
        self.assertTrue(inside(point,p['contracted_domain']));self.assertEqual(p['contracted_domain'][0][1],'1');self.assertTrue(r['original_domain_contact'])
    def test_05_zero_distance_not_squared_negative(self):
        x=small_input('zero');p=P.propose(x,clock=lambda:0.0);C.verify_preprocessing(x,p)
        self.assertEqual(p['range_enclosures']['p'][0]['lower'],'0');self.assertEqual(p['contracted_domain'],[['-1','1']]*4)
        self.assertEqual(K.bounds(x,[['0','0']]*4,'4d'),(0,0))
    def test_06_partial_fallback(self):
        p=P.propose(self.x,skip={'p_y_min':'FALLBACK_UNCERTIFIED','s_x_max':'FALLBACK_TIMEOUT'},clock=lambda:0.0)
        r=C.verify_preprocessing(self.x,p);self.assertEqual(r['contracted_domain'][1][0],'-6');self.assertEqual(r['contracted_domain'][2][1],'6')
        self.assertEqual(sum(v['status']=='CERTIFIED' for v in r['directions']),6)
    def test_07_all_fallback_original_domain(self):
        p=P.propose(self.x,skip={C.direction_id(*d):'FALLBACK_ERROR' for d in C.DIRECTIONS},clock=lambda:0.0)
        self.assertEqual(C.verify_preprocessing(self.x,p)['contracted_domain'],self.x['domains'][:4])
    def test_08_inward_extra_endpoint(self):
        self.p['directions'][1]['candidate_endpoint']='15/4';self.p['directions'][1]['adopted_endpoint']='15/4';rebuild(self.p)
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'CANDIDATE_ENDPOINT_INWARD')
    def test_09_sign_flip(self):
        self.p['directions'][1]['sign']=-1
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'DIRECTION_ID_OR_SIGN_MISMATCH')
    def test_10_other_vehicle_row(self):
        self.p['directions'][1]['proof']['linear'][0]['row_id']=self.p['directions'][1]['proof']['linear'][0]['row_id'].replace('p:','s:')
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'ROW_ID_OR_VEHICLE_MISMATCH')
    def test_11_forged_domain(self):
        self.p['contracted_domain'][0]=['1','2']
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'CONTRACTED_DOMAIN_MISMATCH')
    def test_12_forged_range(self):
        self.p['range_enclosures']['p'][0]['upper']='1'
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'RANGE_ENCLOSURE_OR_VEHICLE_MISMATCH')
    def test_13_negative_multiplier(self):
        self.p['directions'][1]['proof']['linear'][0]['weight']='-1'
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'NEGATIVE_MULTIPLIER')
    def test_14_inexact_dual_residual_repaired(self):
        rec=self.p['directions'][1]
        rec['proof']={'kind':'rational_support_v1','linear':[{'row_id':'p:pair:a0:a1','weight':'1/16'}],
                      'balls':[],'residual':['1/2','0'],'support_upper':'79/16'}
        rec['candidate_endpoint']=rec['adopted_endpoint']='79/16';rebuild(self.p)
        self.assertTrue(C.verify_preprocessing(self.x,self.p)['accepted'])
    def test_15_residual_ignored_is_rejected(self):
        rec=self.p['directions'][1]
        rec['proof']={'kind':'rational_support_v1','linear':[{'row_id':'p:pair:a0:a1','weight':'1/16'}],
                      'balls':[],'residual':['0','0'],'support_upper':'31/16'}
        rec['candidate_endpoint']=rec['adopted_endpoint']='31/16';rebuild(self.p)
        self.assertGreater(C.F(2),C.F('31/16')) # explicit feasible point would be lost
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'RESIDUAL_MISMATCH')
    def test_16_valid_soc_dual(self):
        rec=self.p['directions'][1];rec['proof']={'kind':'rational_support_v1','linear':[],
          'balls':[{'anchor_id':'a0','vector':['1','0'],'t':'1'}],'residual':['0','0'],'support_upper':'4'}
        rec['candidate_endpoint']=rec['adopted_endpoint']='4';rebuild(self.p)
        self.assertTrue(C.verify_preprocessing(self.x,self.p)['accepted'])
    def test_17_invalid_soc_dual(self):
        rec=self.p['directions'][1];rec['proof']={'kind':'rational_support_v1','linear':[],
          'balls':[{'anchor_id':'a0','vector':['1','0'],'t':'1/2'}],'residual':['0','0'],'support_upper':'2'}
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'SOC_DUAL_NOT_CERTIFIED')
    def test_18_unknown_peer_not_anchor(self):
        rec=self.p['directions'][1];rec['proof']['balls']=[{'anchor_id':'s','vector':['1','0'],'t':'1'}]
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'INVALID_BALL_ANCHOR')
    def test_19_fallback_cannot_shrink(self):
        rec=self.p['directions'][1];rec.update(status='FALLBACK_TIMEOUT',proof=None)
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'ADOPTED_ENDPOINT_MISMATCH')
    def test_20_timeout_cannot_certify(self):
        self.p['directions'][1]['elapsed_seconds']='0.50001'
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'DIRECTION_BUDGET_EXCEEDED_WITHOUT_FALLBACK')
    def test_21_empty_by_crossed_endpoints(self):
        x=small_input('empty');p=P.propose(x,clock=lambda:0.0)
        self.assertEqual(p['status'],'EMPTY_PROVED');self.assertIsNone(C.restricted_input(x,p))
        self.assertEqual(C.check_composite(x,composite_fixture(x,p))['status'],'EMPTY_IN_ORIGINAL_DOMAIN')
    def test_22_false_empty(self):
        self.p.update(status='EMPTY_PROVED',contracted_domain=None)
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'CONTRACTED_DOMAIN_MISMATCH')
    def test_23_missing_direction(self):
        self.p['directions'].pop();self.reject(lambda:C.verify_preprocessing(self.x,self.p),'EIGHT_DIRECTIONS_REQUIRED')
    def test_24_original_observation_identity(self):
        x=copy.deepcopy(self.x);x['observation_intervals'][0]=['1','2'];K.seal(x)
        self.reject(lambda:C.verify_preprocessing(x,self.p),'ORIGINAL_INPUT_HASH_MISMATCH')
    def test_25_composite_root_cropped(self):
        c=composite_fixture(self.x,self.p);c['search_certificate']['nodes'][0]['box'][0][0]='1'
        self.reject(lambda:C.check_composite(self.x,c),'ROOT_DOMAIN_MISMATCH')
    def test_26_composite_missing_queue(self):
        c=composite_fixture(self.x,self.p,True);c['search_certificate']['queue']=[]
        self.reject(lambda:C.check_composite(self.x,c),'LOST_OR_REORDERED_QUEUE')
    def test_27_composite_split_coverage(self):
        c=composite_fixture(self.x,self.p,True);c['search_certificate']['nodes'][1]['box'][0][1]='1'
        self.reject(lambda:C.check_composite(self.x,c),'CHILDREN_DO_NOT_COVER_PARENT')
    def test_28_composite_threshold_changed(self):
        c=composite_fixture(self.x,self.p);c['search_certificate']['threshold_certificate']['tau']='24'
        self.reject(lambda:C.check_composite(self.x,c),'THRESHOLD_IDENTITY_MISMATCH')
    def test_29_composite_domain_hash(self):
        c=composite_fixture(self.x,self.p);c['restricted_input_hash']=self.x['input_hash']
        self.reject(lambda:C.check_composite(self.x,c),'RESTRICTED_INPUT_HASH_MISMATCH')
    def test_30_solver_success_not_evidence(self):
        self.p['directions'][1]['proof']={'success':True,'kkt_residual':'0.000000001'}
        self.reject(lambda:C.verify_preprocessing(self.x,self.p),'INVALID_SUPPORT_FORMAT')
    def test_31_outward_endpoint_rounding_allowed(self):
        rec=self.p['directions'][1];rec['candidate_endpoint']=rec['adopted_endpoint']='3.9';rebuild(self.p)
        self.assertEqual(C.verify_preprocessing(self.x,self.p)['contracted_domain'][0][1],'39/10')
    def test_32_same_domain_bias_observations_budget(self):
        y=C.restricted_input(self.x,self.p)
        for key in self.x:
            if key not in ('domains','input_hash'):self.assertEqual(y[key],self.x[key])
        self.assertEqual(y['domains'][4],self.x['domains'][4]);self.assertNotEqual(y['input_hash'],self.x['input_hash'])
    def test_33_car_inputs_are_separate(self):
        x=copy.deepcopy(self.x);x['observation_intervals'][4:8]=[['3','4']]*4;K.seal(x)
        p=P.propose(x,clock=lambda:0.0);C.verify_preprocessing(x,p)
        self.assertNotEqual(p['contracted_domain'][0],p['contracted_domain'][2])
        p['range_enclosures']['s']=copy.deepcopy(p['range_enclosures']['p'])
        self.reject(lambda:C.verify_preprocessing(x,p),'RANGE_ENCLOSURE_OR_VEHICLE_MISMATCH')
    def test_34_clock_deadline_falls_back(self):
        ticks=iter(i*0.6 for i in range(20000));p=P.propose(self.x,clock=lambda:next(ticks))
        z=C.verify_preprocessing(self.x,p);self.assertEqual(z['contracted_domain'],self.x['domains'][:4]);self.assertFalse(z['cost_within_declared_total'])
    def test_35_preprocess_hash_tamper(self):
        c=composite_fixture(self.x,self.p);c['preprocessing']['directions'][0]['reason']='changed'
        self.reject(lambda:C.check_composite(self.x,c),'PREPROCESS_HASH_MISMATCH')
    def test_36_old_checker_rejects_small_root_against_original(self):
        y=C.restricted_input(self.x,self.p);c=tree_fixture(y);c['input_hash']=self.x['input_hash']
        self.reject(lambda:C.V2.check(self.x,c),'ROOT_DOMAIN_MISMATCH')

    def test_37_unknown_car_as_anchor_counterexample(self):
        x=small_input('zero');x['noise_model']['variance']=['1/625']*9
        x['observation_intervals']=[['2','2']]*4+[['3','3']]*4+[['1','1']];K.seal(x)
        self.assertEqual(K.bounds(x,[[v,v] for v in ['2','0','3','0']],'4d'),(0,0))
        # Incorrectly fix s=(0,0): true p=(2,0), peer y=1, B=[-.6,.6].
        false_peer_min=(C.F(2)-C.F(1)-C.F(3,5))**2/C.F(1,625)
        self.assertEqual(false_peer_min,100);self.assertGreater(false_peer_min,26)
    def test_38_composite_recovery_tamper(self):
        c=composite_fixture(self.x,self.p)
        c['search_certificate']['bias_recovery']=[{'point':['2']*4,'result':{'inner':None,'outer':None,'status':'EMPTY_PROVED'}}]
        self.reject(lambda:C.check_composite(self.x,c),'BIAS_RECOVERY_MISMATCH')
    def test_39_composite_radius_tamper(self):
        c=composite_fixture(self.x,self.p);c['search_certificate']['projections']['p']['radius']='0'
        self.reject(lambda:C.check_composite(self.x,c),'PROJECTION_OR_RADIUS_MISMATCH')

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(PrecontractTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if len(sys.argv)>1:
        Path(sys.argv[1]).write_text(json.dumps({'planned':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors),
        'failures':len(result.failures),'errors':len(result.errors),'expected_corruption_rejections':REJECTIONS},ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
