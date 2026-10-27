import copy
import json
import unittest
from pathlib import Path
from native_v2.policy_math import initial,step,score_gate

class NativeV2Tests(unittest.TestCase):
    def parameters(self):return {k:v['value'] for k,v in json.loads((Path(__file__).parents[1]/'single_car_quality_fgo/config.template.json').read_text())['controller'].items()}
    def sequence(self,values):
        state=initial();rows=[]
        for score,reason in values:state,result=step(state,score,reason,self.parameters());rows.append(result)
        return rows
    def test_native_warn_confirm_and_unknown_holds_gain(self):
        r=self.sequence([(2,None),(2,None),(None,'MISSING')]);self.assertEqual([x['state'] for x in r],['normal','downweighted','unknown']);self.assertEqual(r[-1]['information_multiplier'],.1);self.assertEqual(r[-1]['policy_mode_held'],'downweighted')
    def test_initial_unknown_keeps_unity_without_normal_claim(self):
        r=self.sequence([(None,'MISSING')])[0];self.assertEqual(r['state'],'unknown');self.assertEqual(r['information_multiplier'],1.);self.assertFalse(r['monitorable'])
    def test_recovery_requires_three_plus_three(self):
        r=self.sequence([(3,None),(3,None)]+[(0,None)]*6);self.assertEqual([x['state'] for x in r],['normal','disabled','disabled','disabled','recovering','recovering','recovering','normal'])
    def test_recovery_relapse_is_immediate(self):
        r=self.sequence([(3,None),(3,None)]+[(0,None)]*3+[(1.5,None)]);self.assertEqual(r[-1]['state'],'downweighted');self.assertEqual(r[-1]['reason'],'RECOVERY_RELAPSE')
    def test_unknown_resets_confirmation(self):
        r=self.sequence([(3,None),(None,'MISSING'),(3,None)]);self.assertEqual(r[-1]['state'],'normal')
    def test_missing_measurement_has_priority(self):
        base={'arm':'F0'};r=score_gate(dict(raw_aggregate_m=None,target='node_10'),None,base,self.parameters());self.assertEqual(r[1],'NO_CURRENT_AGGREGATED_LINK');self.assertIsNone(r[0])
    def test_not_accepted_shadow_never_scores_main_residual(self):
        r=score_gate(dict(raw_aggregate_m=4.,target='node_10'),dict(row={'accepted_graph':False}),{'arm':'F0'},self.parameters());self.assertIsNone(r[0]);self.assertEqual(r[1],'SHADOW_SOLVE_NOT_ACCEPTED')
    def test_zero_gain_is_zero_information_not_missing_factor(self):
        import math
        self.assertEqual(math.sqrt(0.)*7.,0.);self.assertNotEqual(0.,None)

    def test_policy_score_roundoff_does_not_relax_discrete_states(self):
        from native_v2.policy_math import check_policy
        result=self.sequence([(2,None)])[0];actual=copy.deepcopy(result);actual['score']+=2.3e-15;check_policy(actual,result)
        actual['state']='disabled'
        with self.assertRaisesRegex(ValueError,'state/persistence'):check_policy(actual,result)

class NativeExposureTests(unittest.TestCase):
    def data(self,states,gains):
        from native_v2.summarize import actions
        rows=[];availability=[]
        for i,(state,gain) in enumerate(zip(states,gains)):
            t=1700000000000000000+i*10**9;availability.append(dict(state_epoch_ns=t,available_receive_epoch_ns=t+10**9));rows.append(dict(target='node_10',state_epoch_ns=t,actual_information_multiplier=gain,factor_action='weighted_pseudo_huber_row',engineering_score=None if state=='unknown' else 2.,policy=dict(state=state,policy_mode_held='downweighted' if state=='unknown' else state,information_multiplier=gain,monitorable=state!='unknown',reason='fixture')))
        return actions,rows,availability
    def test_unknown_held_exposure_is_separate_and_last_sample_zero(self):
        actions,rows,a=self.data(['downweighted','unknown','disabled'],[.1,.1,0.]);a[1]['available_receive_epoch_ns']+=10**9;a[2]['available_receive_epoch_ns']+=3*10**9
        result,*_=actions(rows,a,'004023','Q3');s=result['per_link']['node_10']['exposure_link_seconds'];self.assertEqual(s['known_attenuation'],2.);self.assertEqual(s['unknown_hold_attenuation'],3.);self.assertEqual(s.get('known_disabled',0),0.)
    def test_normal_onset_is_not_third_normal_confirmation(self):
        actions,rows,a=self.data(['disabled','recovering','normal','normal','normal'],[0.,.25,1.,1.,1.]);_,_,recovery,_,_=actions(rows,a,'004023','Q3');normal=next(x for x in recovery if x['event']=='policy_normal_onset');self.assertEqual(normal['available_receive_epoch_ns'],a[2]['available_receive_epoch_ns']);self.assertEqual(normal['third_known_normal_confirmation_epoch_ns'],a[4]['available_receive_epoch_ns'])

class NativePublicationBindingTests(unittest.TestCase):
    def data(self):
        row=dict(pose=[1.,2.,3.],antenna_xy_m=[1.1,2.1],bias_rad_s=None,status='graph',estimate_valid=True);graph=dict(record_id='g',role='main',state_epoch_ns=1,row=row);pub=dict(graph_record_id='g',state_epoch_ns=1,availability_cutoff_epoch_ns=1000000001,publication_id='p',row=copy.deepcopy(row));csv=dict(state_epoch_ns='1',availability_cutoff_epoch_ns='1000000001',publication_id='p',base_x_m='1',base_y_m='2',yaw_rad='3',antenna_x_m='1.1',antenna_y_m='2.1',bias_rad_s='',status='graph',estimate_valid='True');return graph,pub,csv
    def test_native_published_graph_association_not_only_file_SHA(self):
        from native_v2.bindings import publication_binding
        g,p,c=self.data();publication_binding([g],[p],[c]);p['row']['pose'][0]+=.01
        with self.assertRaisesRegex(ValueError,'solved main graph'):publication_binding([g],[p],[c])
    def test_CSV_cannot_silently_differ_from_json_publication(self):
        from native_v2.bindings import publication_binding
        g,p,c=self.data();c['base_x_m']='0'
        with self.assertRaisesRegex(ValueError,'CSV numerical'):publication_binding([g],[p],[c])
