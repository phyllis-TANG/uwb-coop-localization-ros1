"""Execute B-proposed semantic contract fixtures. Real A native adapter pending.

This deliberately refuses field input until the actual A freeze has a reviewed
adapter. Fixture success cannot be reported as A strategy/model acceptance.
"""
import argparse
import hashlib
import json
from pathlib import Path
from evidence import begin,finish,require,sha,write
from constraint_checks import decision,factor_cost
from fixtures import example,objective_example


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def seal(value):return dict(content_sha256=digest(value),content=value)


def check(envelope):
    bundle=envelope['content'];require(envelope['content_sha256']==digest(bundle),'bundle checksum mismatch')
    require(bundle['scope']=='synthetic_fixture_not_A_or_field','real A native freeze/adapter not accepted; field semantic acceptance PENDING')
    require(bundle['field_quality_parameters_approved'] is False,'fixture parameters may not be promoted to field')
    previous={};seen=set();counts=dict(decisions=0,unknown=0,disabled=0,recovering=0,weighted_objectives=0);closures=[]
    for row in bundle['decisions']:
        key=(row['case_id'],row['quality_arm'],row['link_id']);cid=row['constraint_id'];require(cid not in seen,'duplicate constraint decision');seen.add(cid)
        old=previous.get(key,dict(health='unknown',bad_count=0,good_count=0));expected,provenance=decision(row,old,bundle['policy'],bundle['nodes'],bundle['catalog']);previous[key]=expected;closures.append(provenance)
        counts['decisions']+=1
        for field in ('unknown','disabled','recovering'):counts[field]+=int(expected['health']==field)
    by={r['constraint_id']:r for r in bundle['decisions']}
    for objective in bundle['objective_examples']:
        factor_cost(objective['factors'],by,objective['independent_fixture_non_UWB_cost'],objective['reported_cost'],objective['expected_decision_ids']);counts['weighted_objectives']+=1
    return dict(status='PASS_SYNTHETIC_CONTRACT_ONLY',counts=counts,real_A_quality_runs=0,real_A_semantic_acceptance='PENDING_NATIVE_FREEZE_AND_ADAPTER',
        all_declared_shadow_closures_checked=True,A_detector_or_optimizer_imported=False,shared_code='B fixtures/IO and B independent formulas only; no A production parser or quality function',
        caveats=['complete declared DAG traversal does not prove the producer logged every real influence','actual source review plus executed target-only interventions after marginalization and real receive-prefix runs remain mandatory','fixture score/FSM parameters are examples, not field thresholds','representative fixture other-cost is known synthetic arithmetic; actual full non-UWB cost must be independently reconstructed by native adapter'])


def fixture_bundle():
    b=example();b['objective_examples']=[]
    for row in b['decisions']:
        if row['score'] is None:continue
        factor,cost=objective_example(row);b['objective_examples'].append(dict(factors=[factor],independent_fixture_non_UWB_cost=0.,reported_cost=cost,expected_decision_ids=[row['constraint_id']]))
    return b


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_semantic_fixture_contract_no_field_quality_run')
    try:
        if a.bundle:
            envelope=json.loads(a.bundle.read_text());v['inputs']=[dict(path=str(a.bundle),sha256=sha(a.bundle))]
        else:envelope=seal(fixture_bundle());write(a.output/'synthetic_fixture.json',envelope)
        result=check(envelope);write(a.output/'verification.json',result);finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
