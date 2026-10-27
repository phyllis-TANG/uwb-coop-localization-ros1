"""Resealed semantic negative fixtures. No real quality estimator runs."""
import argparse
import copy
from pathlib import Path
from evidence import begin,finish,require,write
from check_contract import check,fixture_bundle,seal


def mutations(bundle):
    def edit(name,fn):
        b=copy.deepcopy(bundle);fn(b);return name,b
    def leak(b,category):b['nodes'][category+'_4']['parents'].append('target_0_0')
    out=[edit('future_arrival',lambda b:b['catalog']['target_0_0'].__setitem__('receive_epoch_ns',b['decisions'][0]['cutoff_epoch_ns']+1)),
        edit('header_float_epoch',lambda b:b['catalog']['target_0_0'].__setitem__('header_epoch_ns',float(b['catalog']['target_0_0']['header_epoch_ns']))),
        edit('unknown_filled_zero',lambda b:b['decisions'][5].__setitem__('score',0.)),
        edit('unknown_promoted_healthy',lambda b:b['decisions'][5].__setitem__('health','healthy')),
        edit('main_postfit_residual',lambda b:b['decisions'][1].__setitem__('innovation_m',0.)),
        edit('skipped_recovery',lambda b:b['decisions'][3].__setitem__('health','healthy')),
        edit('weight_logged_not_applied',lambda b:b['objective_examples'][1]['factors'][0].__setitem__('information_multiplier',1.)),
        edit('weighted_residual_not_applied',lambda b:b['objective_examples'][1]['factors'][0].__setitem__('weighted_residual',999.)),
        edit('omitted_objective_constraint',lambda b:b['objective_examples'][1].__setitem__('factors',[]))]
    for category in ('external_initialization','prediction','optimizer_initial_guess','history','cache','marginal_prior','score_pose'):out.append(edit('target_leak_'+category,lambda b,c=category:leak(b,c)))
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_resealed_semantic_fixture_negative_checks')
    try:
        original=fixture_bundle();check(seal(original));before=seal(original)['content_sha256'];checks=[]
        for name,b in mutations(original):
            envelope=seal(b);write(a.output/(name+'.json'),envelope)
            try:check(envelope)
            except ValueError as e:
                reason=str(e);require('checksum' not in reason,'negative rejected only by SHA gate');checks.append(dict(mutation=name,status='REJECTED',reason=reason,hashes_resealed=True))
            else:raise ValueError('semantic mutation accepted: '+name)
        require(seal(original)['content_sha256']==before,'original fixture changed');write(a.output/'verification.json',dict(status='PASS_SYNTHETIC_NEGATIVES_ONLY',checks=checks,original_unchanged=True,field_A_quality_runs=0,field_semantic_acceptance='PENDING'))
        finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
