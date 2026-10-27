"""Extend completed N10 controls to every excluded wall; reuse existing prefixes."""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from .common import begin,finish,lines,write_lines,require,sha,write
from .controls import compare


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--controls',type=Path,required=True);p.add_argument('--prior-readback',type=Path,required=True);p.add_argument('--execution-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_all_wall_target_exclusion_extension_no_performance_rerun')
    try:
        previous=json.loads((a.prior_readback/'verification.json').read_text());require(previous['status']=='PASS','original real controls must pass');checks=[dict(r,target='node_10',reused_original_N10=True) for r in previous['checks']];env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
        for case in ('004023','005135'):
            original=a.controls/(case+'_prefix.jsonl.gz');prefix=lines(original)
            for target in ('node_2','node_3','node_8'):
                altered=copy.deepcopy(prefix);changes=0
                for row in altered:
                    if row['kind']=='uwb' and target in row['value']:row['value'][target]+=1.7;changes+=1
                require(changes>0,'target intervention absent');path=a.output/(case+'_'+target+'_intervention.jsonl.gz');write_lines(path,altered)
            for group in ('Q2','Q3'):
                jobs=[];config=a.controls/(case+'_'+group+'_control_config.json')
                for target in ('node_2','node_3','node_8'):
                    path=a.output/(case+'_'+target+'_intervention.jsonl.gz');dest=a.output/(case+'_'+group+'_'+target);args=[sys.executable,'-m','tools.single_car_quality_fgo_eval.native_v2.probe_runner','--events',str(path),'--config',str(config),'--output',str(dest)];log=(a.output/(dest.name+'.log')).open('x');proc=subprocess.Popen(args,cwd=a.execution_checkout,env=env,stdout=log,stderr=subprocess.STDOUT);jobs.append((proc,log,dest,target,args));v['estimator_runs']+=1
                full=a.performance/(case+'_'+group);graphs=lines(full/'graphs.jsonl.gz');ledger=lines(full/'quality_ledger.jsonl.gz');baseline=a.controls/(case+'_'+group+'_prefix')
                for proc,log,dest,target,args in jobs:
                    rc=proc.wait(timeout=180);log.close();require(rc==0,'all-wall control failed: '+str(dest));result=compare(baseline,dest,graphs,ledger,target);result.update(case_id=case,group=group,target=target,reused_original_N10=False,command_argv=args,original_prefix_sha256=sha(original),altered_input_sha256=sha(a.output/(case+'_'+target+'_intervention.jsonl.gz')));checks.append(result);print(case,group,target,'PASS',flush=True)
        require(len(checks)==16 and len({(r['case_id'],r['group'],r['target']) for r in checks})==16,'complete 2case x2group x4excluded wall controls')
        write(a.output/'verification.json',dict(status='PASS',checks=checks,reused_original_control_runs=8,added_intervention_runs=12,total_control_estimator_runs=20,main_performance_runs_added=0,all_four_excluded_walls_checked=True,actual_marginalization_crossed=True,original_data_unchanged=True));finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
