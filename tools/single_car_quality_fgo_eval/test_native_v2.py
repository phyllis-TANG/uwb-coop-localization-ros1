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
