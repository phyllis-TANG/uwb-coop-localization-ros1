import copy
import unittest
from constraint_checks import ROOTS,closure,decision,factor_cost,invariant_prefix,shadow_intervention
from fixtures import example,objective_example
from input_facts import project

class ConstraintTests(unittest.TestCase):
    def check(self,fixture):
        previous=dict(health='unknown',bad_count=0,good_count=0)
        for row in fixture['decisions']:previous,_=decision(row,previous,fixture['policy'],fixture['nodes'],fixture['catalog'])
        return previous
    def test_literal_FSM_known_sequence(self):self.assertEqual(self.check(example())['health'],'healthy')
    def test_unknown_zero_score_rejected(self):
        f=example();f['decisions'][5]['score']=0.
        with self.assertRaisesRegex(ValueError,'null filled zero'):self.check(f)
    def test_unknown_not_healthy(self):
        f=example();f['decisions'][5]['health']='healthy'
        with self.assertRaisesRegex(ValueError,'health transition'):self.check(f)
    def test_missing_variance_not_zero_filled(self):
        f=example();f['decisions'][0]['prediction_variance_m2']=None
        with self.assertRaisesRegex(ValueError,'missing score input'):self.check(f)
    def test_future_support_rejected(self):
        f=example();f['catalog']['target_0_0']['receive_epoch_ns']=f['decisions'][0]['cutoff_epoch_ns']+1
        with self.assertRaisesRegex(ValueError,'future/cross-case'):self.check(f)
    def test_float_epoch_rejected(self):
        f=example();f['decisions'][0]['cutoff_epoch_ns']=float(f['decisions'][0]['cutoff_epoch_ns'])
        with self.assertRaisesRegex(ValueError,'exact integer'):self.check(f)
    def test_main_postfit_innovation_not_shadow(self):
        f=example();f['decisions'][1]['innovation_m']=0.
        with self.assertRaisesRegex(ValueError,'post-fit main residual'):self.check(f)
    def test_bad_score_not_hidden(self):
        f=example();f['decisions'][1]['score']=0.
        with self.assertRaisesRegex(ValueError,'score mismatch'):self.check(f)
    def test_recovery_hysteresis_not_skipped(self):
        f=example();f['decisions'][3].update(health='healthy',good_count=2,new_information_multiplier=1.)
        with self.assertRaisesRegex(ValueError,'health transition'):self.check(f)
    def test_each_shadow_influence_category_excludes_target(self):
        for category in ROOTS:
            with self.subTest(category=category):
                f=example();f['nodes'][category+'_2']['parents'].append('main_0')
                with self.assertRaisesRegex(ValueError,'excluded link leaked'):self.check(f)
    def test_target_in_marginalized_prior_rejected_even_low_current_score(self):
        f=example();f['nodes']['marginal_prior_4']['parents'].append('target_0_1')
        with self.assertRaisesRegex(ValueError,'excluded link leaked'):self.check(f)
    def test_shadow_incomplete_initialization_ledger_rejected(self):
        f=example();del f['decisions'][0]['shadow_roots']['external_initialization']
        with self.assertRaisesRegex(ValueError,'incomplete shadow'):self.check(f)
    def test_undeclared_state_origin_rejected(self):
        f=example();f['nodes']['cache_0']['parents']=[]
        with self.assertRaisesRegex(ValueError,'undeclared origin'):self.check(f)
    def test_provenance_cycle_rejected(self):
        f=example();f['nodes']['cache_0']['parents'].append('cache_0')
        with self.assertRaisesRegex(ValueError,'cyclic shadow'):self.check(f)
    def test_cross_case_leak_rejected(self):
        f=example();f['catalog']['target_0_0']['case_id']='005135'
        with self.assertRaisesRegex(ValueError,'cross-case'):self.check(f)
    def test_raw_median_and_original_bin_not_reselected(self):
        f=example();f['decisions'][0]['raw_range_m']+=.1
        with self.assertRaisesRegex(ValueError,'original raw median'):self.check(f)
    def test_duplicate_scalar_support_not_extra_samples(self):
        f=example();f['decisions'][0]['support_record_ids']=['target_0_0']*5
        with self.assertRaisesRegex(ValueError,'unique scalar supports'):self.check(f)
    def test_weighted_objective_uses_actual_effective_weight(self):
        f=example();row=f['decisions'][1];factor,cost=objective_example(row)
        factor_cost([factor],{row['constraint_id']:row},0.,cost,[row['constraint_id']])
        factor['weighted_residual']*=2
        with self.assertRaisesRegex(ValueError,'ignored or double-applied'):factor_cost([factor],{row['constraint_id']:row},0.,cost,[row['constraint_id']])
    def test_disabled_constraint_does_not_keep_full_factor(self):
        f=example();row=f['decisions'][2];factor,cost=objective_example(row);factor['information_multiplier']=1
        with self.assertRaisesRegex(ValueError,'not really applied'):factor_cost([factor],{row['constraint_id']:row},0.,cost,[row['constraint_id']])
    def test_objective_omitted_constraint_rejected(self):
        f=example();row=f['decisions'][0]
        with self.assertRaisesRegex(ValueError,'omission'):factor_cost([],{row['constraint_id']:row},0.,0.,[row['constraint_id']])
    def test_prefix_includes_quality_decisions_not_only_pose(self):
        full=example()['decisions'];prefix=copy.deepcopy(full[:4]);self.assertEqual(invariant_prefix(full,prefix),4);prefix[0]['new_information_multiplier']=.5
        with self.assertRaisesRegex(ValueError,'closed decision'):invariant_prefix(full,prefix)
    def test_intervention_checks_prior_and_optimizer_initial_guess(self):
        a=dict(target_link='node_10',other_input_sha256='a',target_input_sha256='b',marginalizations=2,shadow_artifact_sha256={k:'sha' for k in ROOTS});b=copy.deepcopy(a);b['target_input_sha256']='c';shadow_intervention(a,b,'node_10')
        for k in ('marginal_prior','optimizer_initial_guess','cache'):
            bad=copy.deepcopy(b);bad['shadow_artifact_sha256'][k]='changed'
            with self.assertRaisesRegex(ValueError,'reentered shadow'):shadow_intervention(a,bad,'node_10')
    def test_multi_anchor_message_projects_distinct_scalar_identities(self):
        r=dict(case_id='004023',source_file_sha256='a',record_index=1,topic='uwb',header_epoch_ns=1,receive_epoch_ns=2,raw_message_sha256='b',kind='uwb',message={'ranges':[{'anchor_id':'node_2','range':3.},{'anchor_id':'node_10','range':4.}]})
        p=project(r);self.assertNotEqual(p[0][0],p[1][0]);self.assertEqual(p[0][1]['record_index'],p[1][1]['record_index']);self.assertEqual([x[1]['link_id'] for x in p],['node_2','node_10'])
