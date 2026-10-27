"""Isolate consumable prior inputs/configs from all endpoint diagnostics."""
import argparse
import gzip
import json
from pathlib import Path
import shutil
from evidence import begin,finish,require,sha,write

FORBIDDEN={'evaluation_window_s','end_antenna_xyz_m','manual_endpoint_xy_m','ground_truth','fault_label','truth','true_pose','true_bias'}


def no_reference_keys(value):
    if isinstance(value,dict):
        require(not FORBIDDEN.intersection(value),'evaluation reference/fault label in estimator input')
        for item in value.values():no_reference_keys(item)
    elif isinstance(value,list):
        for item in value:no_reference_keys(item)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reused',type=Path,required=True);p.add_argument('--facts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_A_consumable_input_bundle_without_manual_references')
    try:
        facts=json.loads((a.facts/'index.json').read_text());reuse=json.loads((a.reused/'reuse_manifest.json').read_text());require(reuse['status']=='PASS','verified reuse required');rows=[]
        for case in ('004023','005135'):
            dest=a.output/case;dest.mkdir();catalog=next(r for r in facts['cases'] if r['case_id']==case);copies={}
            for source,name in [(a.reused/'A_inputs'/case/'events.jsonl.gz','events.jsonl.gz'),(a.reused/'inputs'/case/'events.jsonl.gz','rich_events.jsonl.gz'),(a.facts/catalog['catalog_file'],'scalar_catalog.json.gz')]+[(a.reused/'A_inputs'/case/(arm+'.json'),arm+'_baseline_config.json') for arm in ('F0','F3')]:
                target=dest/name;shutil.copyfile(source,target);copies[name]=dict(sha256=sha(target),bytes=target.stat().st_size);require(sha(target)==sha(source),'input copy changed')
            with gzip.open(dest/'events.jsonl.gz','rt') as f:
                count=0
                for line in f:no_reference_keys(json.loads(line));count+=1
            for arm in ('F0','F3'):no_reference_keys(json.loads((dest/(arm+'_baseline_config.json')).read_text()))
            require(copies['events.jsonl.gz']['sha256']==next(r for r in reuse['reused_run_bindings'] if r['case_id']==case)['input_sha256'],'exact PR59 event binding')
            rows.append(dict(case_id=case,records=count,files=copies,quality_config=None,quality_config_pending_reason='requires actual A quality freeze; no fixture parameters transferred',
              strict_physical_calibration_status='still pending axes/clock/odom-origin; inherited conditional historical model only'))
        write(a.output/'manifest.json',dict(status='READY_INPUTS_ONLY',cases=rows,old_A_commit='e3a20fe04a6d53973696ec055dbc71eb135e0f77',Q0='F0 baseline available',Q1='F3 baseline available',Q2_Q3='NOT_EXECUTED; A quality native freeze pending',
          reference_evaluation_included=False,policy_configuration_included=False,A_quality_commit=None,quality_parameters=None,old_P1_transferred_to_other_sessions=False,
          inherited_clock_mapping='original recorded epochs uncorrected; not measured physical clock calibration',new_estimator_runs=0))
        v['inputs']=[dict(path=str(a.reused/'reuse_manifest.json'),sha256=sha(a.reused/'reuse_manifest.json'))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
