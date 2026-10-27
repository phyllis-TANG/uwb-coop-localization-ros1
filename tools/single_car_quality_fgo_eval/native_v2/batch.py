"""At most eight main paced replays, four processes per historical input."""
import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from .common import ROOT,begin,finish,require,sha,write


def baseline_check(actual,prior):
    a=list(csv.DictReader(Path(actual).open()));b=list(csv.DictReader(Path(prior).open()));require(len(a)==len(b),'baseline coverage mismatch');maximum=0.
    for x,y in zip(a,b):
        for k in ('state_time_s','availability_cutoff_s','status','accepted_graph','graph_states','marginalizations','range_medians_json','sample_counts_json'):require(x[k]==y[k],'baseline discrete/aggregation mismatch '+k)
        for k in ('base_x_m','base_y_m','yaw_rad','antenna_x_m','antenna_y_m'):maximum=max(maximum,abs(float(x[k])-float(y[k])))
    require(maximum<=1e-9,'baseline numeric mismatch');return dict(publications=len(a),maximum_pose_component_difference=maximum)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--execution-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_eight_paced_historical_performance_runs');jobs=[]
    try:
        binding=json.loads((a.prepared/'binding.json').read_text());commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.execution_checkout,text=True).strip();require(not subprocess.check_output(['git','status','--porcelain'],cwd=a.execution_checkout,text=True).strip(),'clean execution checkout')
        for name,h in binding['source_sha256'].items():require(sha(a.execution_checkout/'tools/single_car_quality_fgo'/name)==h,'frozen A source '+name)
        environment=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1');records=[];regression=[]
        for case in ('004023','005135'):
            anchor=time.monotonic_ns()+5_000_000_000;hostanchor=time.time_ns()+5_000_000_000;jobs=[]
            for entry in [r for r in binding['matrix'] if r['case_id']==case]:
                require(sha(a.prepared/entry['events_relative_path'])==entry['input_sha256'] and sha(a.prepared/entry['config_relative_path'])==entry['config_sha256'],'frozen input/config')
                key=case+'_'+entry['group'];dest=a.output/key;args=[sys.executable,str(a.execution_checkout/'tools/single_car_quality_fgo/qrun.py'),'--events-jsonl',str(a.prepared/entry['events_relative_path']),'--config',str(a.prepared/entry['config_relative_path']),'--output',str(dest),'--anchor-monotonic-ns',str(anchor),'--anchor-host-epoch-ns',str(hostanchor),'--max-seconds',str(entry['max_seconds'])]
                log=(a.output/(key+'.log')).open('x');process=subprocess.Popen(args,cwd=a.execution_checkout,env=environment,stdout=log,stderr=subprocess.STDOUT);v['estimator_runs']+=1;jobs.append((process,log,entry,args,time.monotonic()))
            for process,log,entry,args,started in jobs:
                try:rc=process.wait(timeout=entry['max_seconds']+20)
                except subprocess.TimeoutExpired:process.terminate();rc=process.wait(timeout=15)
                log.close();key=case+'_'+entry['group'];record=dict(case_id=case,group=entry['group'],exit_code=rc,command_argv=args,wall_s=time.monotonic()-started,host_anchor_monotonic_ns=anchor,host_anchor_epoch_ns=hostanchor)
                path=a.output/key/'run.json'
                if path.exists():record['run_sha256']=sha(path);record['status']=json.loads(path.read_text())['status']
                else:record['status']='FAILED_NO_RUN_MANIFEST'
                if rc==0 and entry['group'] in ('Q0','Q1'):
                    try:regression.append(dict(case_id=case,group=entry['group'],status='PASS',**baseline_check(a.output/key/'published.csv',a.prepared/'prior/F0_F3'/(case+'_'+entry['base_arm'])/'published.csv')))
                    except ValueError as e:regression.append(dict(case_id=case,group=entry['group'],status='FAIL',reason=str(e)))
                records.append(record);write(a.output/('checkpoint_'+str(len(records))+'.json'),dict(status='IN_PROGRESS',execution_commit=commit,completed=records,baseline_regression=regression));print(key,record['status'],flush=True)
        success=all(r['exit_code']==0 and r['status']=='DONE' for r in records);write(a.output/'matrix.json',dict(status='DONE' if success else 'FAILED',execution_commit=commit,A_execution_commit=binding['A_execution_commit'],binding_sha256=sha(a.prepared/'binding.json'),expected_runs=8,actual_runs=len(records),runs=records,baseline_regression=regression,
          timing='each case four concurrent independent processes, shared host anchor, recorded receive paced; includes same host load across all groups',baseline_remeasurement_reason=binding['baseline_remeasurement_reason'],automatic_retry=False))
        finish(a.output,v,None if success else 'one or more preserved failed runs');return 0 if success else 1
    except Exception as e:
        for process,log,*_ in jobs:
            if process.poll() is None:process.terminate();process.wait(timeout=15)
            log.close()
        finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
