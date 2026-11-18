"""Fresh-process, sequential zero-search benchmarking of the locked 44 proofs."""
from time import perf_counter
START=perf_counter()
import argparse
import importlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys


def worker(args):
    module=importlib.import_module('core' if args.kernel=='v1' else 'checker_v2')
    from check import read_json
    from core import digest
    imported=perf_counter()
    lock=read_json(Path(args.evidence)/'EVIDENCE_LOCK.json')
    record=lock['formal_records'][args.index]
    inputs=read_json(Path(args.evidence)/'inputs.json'); x=next(x for x in inputs if x['case_id']==record['case_id'])
    c=read_json(Path(args.evidence)/record['certificate_file'])
    loaded=perf_counter()
    result=module.check(x,c)
    checked=perf_counter()
    metrics={'kernel':args.kernel,'index':args.index,'case_id':record['case_id'],'mode':c['mode'],
             'result':result,'projection_hash':digest(c['projections']),'queue_hash':digest(c['queue']),
             'recovery_hash':digest(c['bias_recovery']),'region_status':c['status'],'nodes':len(c['nodes']),
             'import_seconds':imported-START,'load_seconds':loaded-imported,'check_seconds':checked-loaded,
             'child_elapsed_seconds':checked-START,'child_cpu_seconds':resource.getrusage(resource.RUSAGE_SELF).ru_utime+resource.getrusage(resource.RUSAGE_SELF).ru_stime,
             'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024}
    print(json.dumps(metrics))


def batch(args):
    from check import read_json
    root=Path(args.out); root.mkdir(parents=True,exist_ok=True)
    lock=read_json(Path(args.evidence)/'EVIDENCE_LOCK.json')
    cpu=min(os.sched_getaffinity(0))
    env={'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),'cpu_affinity':[cpu],
         'cpu_model':next((x.strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('model name')),'unknown'),
         'policy':'one fresh interpreter per certificate, sequential, fixed CPU, empty application cache; OS page cache not flushed',
         'kernel':args.kernel,'evidence_archive_hash':lock['archive_hash']}
    (root/(args.kernel+'_environment.json')).write_text(json.dumps(env,indent=2)+'\n')
    for i,record in enumerate(lock['formal_records']):
        target=root/f'{args.kernel}_{i:02d}.json'
        if target.exists(): raise RuntimeError('Refusing overwrite of benchmark sample: '+str(target))
        t=perf_counter()
        proc=subprocess.run([sys.executable,__file__,'worker','--kernel',args.kernel,'--evidence',args.evidence,'--index',str(i)],
                            capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},
                            preexec_fn=lambda:os.sched_setaffinity(0,{cpu}))
        elapsed=perf_counter()-t
        if proc.returncode:
            (root/f'{args.kernel}_{i:02d}.failure.txt').write_text(proc.stdout+'\n'+proc.stderr)
            raise RuntimeError(f'worker {i} failed: {proc.stderr}')
        row=json.loads(proc.stdout);row['cold_process_wall_seconds']=elapsed
        target.write_text(json.dumps(row,indent=2)+'\n')
        print(json.dumps({'kernel':args.kernel,'completed':i+1,'planned':44,'case_id':record['case_id'],
                          'mode':record['mode'],'check_seconds':row['check_seconds'],'peak_mib':row['peak_rss_bytes']/2**20}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['worker','batch']);p.add_argument('--kernel',choices=['v1','v2'],required=True)
    p.add_argument('--evidence',required=True);p.add_argument('--index',type=int);p.add_argument('--out');a=p.parse_args()
    worker(a) if a.action=='worker' else batch(a)
