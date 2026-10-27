"""Extend record-prefix guards to quality decisions; synthetic records only."""
import argparse
import copy
from pathlib import Path
from evidence import begin,finish,require,write
from check_contract import check,fixture_bundle,seal
from constraint_checks import invariant_prefix


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_synthetic_quality_record_prefix_guard')
    try:
        full=fixture_bundle();prefix=copy.deepcopy(full);prefix['decisions']=prefix['decisions'][:4];last=prefix['decisions'][-1]['cutoff_epoch_ns'];prefix['catalog']={k:r for k,r in prefix['catalog'].items() if r['receive_epoch_ns']<=last};ids={r['constraint_id'] for r in prefix['decisions']};prefix['objective_examples']=[x for x in prefix['objective_examples'] if set(x['expected_decision_ids']).issubset(ids)]
        check(seal(full));check(seal(prefix));count=invariant_prefix(full['decisions'],prefix['decisions']);bad=copy.deepcopy(prefix['decisions']);bad[0]['new_information_multiplier']=.5
        try:invariant_prefix(full['decisions'],bad)
        except ValueError as e:reason=str(e)
        else:raise ValueError('closed quality decision mutation accepted')
        write(a.output/'full_fixture.json',seal(full));write(a.output/'prefix_fixture.json',seal(prefix));write(a.output/'verification.json',dict(status='PASS_SYNTHETIC_RECORD_GUARD_ONLY',recorded_receive_cutoff_epoch_ns=last,quality_decisions_identical=count,closed_weight_mutation_rejected=reason,
          actual_new_estimator_prefix_runs=0,actual_A_quality_prefix_status='PENDING_NATIVE_FREEZE',reused_prior_baseline_prefix_evidence='PR59: 8 real original FGO controls, 304 publications. Not rerun or counted as new quality controls.',
          limitation='This tests the extended record comparison and deadline guard, not an A quality estimator execution. The native A CLI must still run real recorded prefixes after freeze.'))
        finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
