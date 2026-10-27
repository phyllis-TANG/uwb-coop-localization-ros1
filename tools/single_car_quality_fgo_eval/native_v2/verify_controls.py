"""Verify completed real controls independently; no new estimator executions."""
import argparse
import copy
import json
from pathlib import Path
from .common import begin,finish,lines,require,sha,write
from .controls import compare


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--controls',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_independent_reinspection_of_executed_real_controls')
    try:
        checks=[];matrix=json.loads((a.performance/'matrix.json').read_text())
        for case in ('004023','005135'):
            ready=a.prepared/'stage1/ready_for_A_001'/case;full=lines(ready/'events.jsonl.gz');origin=full[0]['receive_epoch_ns'];prefix=lines(a.controls/(case+'_prefix.jsonl.gz'));altered=lines(a.controls/(case+'_node10_intervention.jsonl.gz'));require(prefix==[r for r in full if r['receive_epoch_ns']<=origin+41_000_000_000],'prefix not exact original receive horizon');require(len(prefix)==len(altered),'control message coverage')
            changed=0
            for original,actual in zip(prefix,altered):
                wanted=copy.deepcopy(original)
                if wanted['kind']=='uwb' and 'node_10' in wanted['value']:wanted['value']['node_10']+=1.7;changed+=1
                require(wanted==actual,'altered non-target message field')
            require(changed>0,'no altered target')
            for group in ('Q2','Q3'):
                perf=a.performance/(case+'_'+group);meta=json.loads((perf/'run.json').read_text());config=json.loads((perf/'config.json').read_text());control_config=json.loads((a.controls/(case+'_'+group+'_control_config.json')).read_text());require({k:v for k,v in config.items() if k!='timing'}=={k:v for k,v in control_config.items() if k!='timing'},'control changed non-timing configuration')
                before=a.controls/(case+'_'+group+'_prefix');after=a.controls/(case+'_'+group+'_intervention')
                for folder,events in [(before,a.controls/(case+'_prefix.jsonl.gz')),(after,a.controls/(case+'_node10_intervention.jsonl.gz'))]:
                    run=json.loads((folder/'run.json').read_text());summary=json.loads((folder/'summary.json').read_text());require(run['status']=='DONE' and not run['dirty'] and run['code_commit']==matrix['execution_commit'],'control exact clean combination');require(summary['source_sha256']==meta['source_sha256'],'control A source differs');require(summary['input_sha256']==sha(events),'actual altered/prefix file SHA')
                    for output in run['outputs']:require(sha(folder/output['relative_path'])==output['sha256'],'control output SHA changed')
                result=compare(before,after,lines(perf/'graphs.jsonl.gz'),lines(perf/'quality_ledger.jsonl.gz'));result.update(case_id=case,group=group,changed_target_components=changed);checks.append(result)
        write(a.output/'verification.json',dict(status='PASS',checks=checks,estimator_runs_added=0,actual_control_runs_reused=8,execution_commit=matrix['execution_commit'],actual_cached_receive_deadlines_checked=True,A_policy_graph_Jacobian_or_qaudit_imported=False));finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
