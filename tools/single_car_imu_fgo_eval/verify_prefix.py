"""Real receive-prefix causality controls using exact frozen A CLI, no tuning."""
import argparse
import gzip
import json
from pathlib import Path
import subprocess
import sys
from meta import HERE,finish,save,sha,start
from verify_fgo import loadlines,require

TIMING={'solve_wall_s','marginal_wall_s','update_wall_s','estimated_worker_start_s','estimated_worker_finish_s','estimated_worker_queue_s'}


def compare(full,prefix):
    require(bool(prefix),'empty prefix control')
    require(len(prefix)<len(full),'control must truncate real future input')
    for a,b in zip(full,prefix):
        require({k:v for k,v in a.items() if k not in TIMING}=={k:v for k,v in b.items() if k not in TIMING},'published prefix changed when future input removed')
    return len(prefix)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--adapted',type=Path,required=True);p.add_argument('--matrix',type=Path,required=True);p.add_argument('--execution-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=start(a.output,'B_real_receive_prefix_controls')
    try:
        protocol=json.loads((HERE/'verification_protocol.json').read_text());matrix=json.loads((a.matrix/'matrix.json').read_text())
        actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.execution_checkout,text=True).strip();require(actual==matrix['code_commit'],'exact nominal execution commit')
        require(not subprocess.check_output(['git','status','--porcelain'],cwd=a.execution_checkout,text=True).strip(),'clean execution tree')
        checks=[]
        for case in protocol['prefix_checks']['cases']:
            rows=loadlines(a.adapted/case/'events.jsonl.gz');cutoff=rows[0]['receive_epoch_ns']+protocol['prefix_checks']['receive_horizon_from_origin_ns'];selected=[r for r in rows if r['receive_epoch_ns']<=cutoff]
            path=a.output/(case+'_prefix_events.jsonl.gz')
            with path.open('xb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:
                for r in selected:z.write((json.dumps(r,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())
            for arm in protocol['prefix_checks']['arms']:
                dest=a.output/(case+'_'+arm);args=[sys.executable,str(a.execution_checkout/'tools/single_car_imu_fgo/replay.py'),'--events-jsonl',str(path),'--config',str(a.adapted/case/(arm+'.json')),'--output',str(dest),'--max-seconds','120']
                with (a.output/(case+'_'+arm+'.log')).open('x') as log:process=subprocess.run(args,cwd=a.execution_checkout,stdout=log,stderr=subprocess.STDOUT,timeout=150)
                require(process.returncode==0,'prefix CLI failed (partial directory preserved)')
                count=compare(loadlines(a.matrix/(case+'_'+arm)/'updates.jsonl.gz'),loadlines(dest/'updates.jsonl.gz'))
                checks.append(dict(case_id=case,arm=arm,input_records=len(selected),publications_identical=count,command_argv=args,exit_code=process.returncode,run_sha256=sha(dest/'run.json')))
        save(a.output/'verification.json',dict(status='PASS',controls=checks,execution_commit=actual,all_non_timing_publication_fields_identical=True,control_purpose='remove future records after 41s receipt horizon, real marginalizations included; not a new parameter experiment'))
        finish(a.output,run,'DONE');return 0
    except Exception as e:finish(a.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
