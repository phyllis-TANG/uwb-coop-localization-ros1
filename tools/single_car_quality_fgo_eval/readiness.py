"""Concrete Q0/Q1 reuse inventory and unresolved native A handoff bindings."""
import argparse
import json
from pathlib import Path
from evidence import ROOT,begin,finish,require,sha,write


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reused',type=Path,required=True);p.add_argument('--facts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_quality_input_readiness_no_new_estimator')
    try:
        reuse=json.loads((a.reused/'reuse_manifest.json').read_text());facts=json.loads((a.facts/'index.json').read_text());require(reuse['status']=='PASS' and facts['status']=='DONE','input preparation incomplete');rows=[]
        for case in ('004023','005135'):
            catalog=next(x for x in facts['cases'] if x['case_id']==case);require(sha(a.facts/catalog['catalog_file'])==catalog['catalog_sha256'],'scalar catalog changed')
            for old,new in [('F0','Q0'),('F3','Q1')]:
                binding=next(x for x in reuse['reused_run_bindings'] if x['case_id']==case and x['arm']==old);matches={name:((ROOT/name).is_file() and sha(ROOT/name)==digest) for name,digest in binding['source_sha256'].items()}
                rows.append(dict(case_id=case,arm=new,status='PR59_RESULT_AVAILABLE_NO_RERUN',baseline_model=old,prior_execution_commit=binding['execution_commit'],
                    publication_sha256=binding['publication_sha256'],input_sha256=binding['input_sha256'],config_sha256=binding['config_sha256'],
                    source_matches_common_checkout=matches,all_archived_source_files_match_common_checkout=all(matches.values()),
                    future_A_reuse_gate='Native quality-off route must call exactly this baseline with identical inputs/config/evaluation. Check frozen A source and actual route; rerun only an inconsistent baseline if necessary.',
                    catalog_sha256=catalog['catalog_sha256']))
            for arm in ('Q2','Q3'):
                rows.append(dict(case_id=case,arm=arm,status='NOT_EXECUTED_PENDING_NATIVE_A_FREEZE',input_available=True,input_sha256=next(x for x in reuse['reused_run_bindings'] if x['case_id']==case)['input_sha256'],catalog_sha256=catalog['catalog_sha256'],A_commit=None,quality_protocol_sha256=None,quality_native_schema_sha256=None,field_quality_parameters=None,trigger_metrics=None,coverage=None,improvement_assessment='尚不能判断'))
        write(a.output/'readiness.json',dict(status='STAGE1_READY_A_NATIVE_PENDING',rows=rows,
          no_new_estimator_runs=True,prior_matrix_rerun=False,
          required_A_handoff=['exact quality execution commit and frozen parameters/protocol SHA','native CLI/schema and complete per-constraint identity/score/state/weight/admission evidence','target-excluded shadow source and all init/prediction/cache/history/prior dependencies','quality-off baseline route identity and weighted objective snapshots','field-independent parameter provenance; no manual endpoint/window input','executed source-audit and target-only shadow interventions after marginalization plus real receive-prefix controls'],
          interpretation={'code_and_interface':'B neutral fixture checks tested; actual A native acceptance pending','quality_actions':'Q2/Q3 not executed, trigger counts remain null','evidence_of_improvement':'尚不能判断; historical manual endpoints uncertain, no complete fault timeline labels'},
          shared_parsing='PR59 packets reused; new scalar projection reads serialized fields only. No A quality decision, optimizer, Jacobian or detector imported.'))
        v['inputs']=[dict(path=str(a.reused/'reuse_manifest.json'),sha256=sha(a.reused/'reuse_manifest.json')),dict(path=str(a.facts/'index.json'),sha256=sha(a.facts/'index.json'))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
