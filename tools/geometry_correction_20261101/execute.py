"""Reuse the PR91 run function; only initial availability is adapted."""
import argparse
import json
from pathlib import Path
import types
from local_support import EPOCH,ROOT,clone,gitstate,load,sources
from reuse import adapter,old_support

old_run=load('_gc_pr91_run','tools/two_car_mechanism_20261101/run.py',{'support':old_support,'bindings':types.SimpleNamespace(adapter=adapter)})

def replay(config,method,sink,origin):
    if origin!=EPOCH+5*10**9:raise ValueError('Initialization origin mismatch')
    value=adapter.replay(config,method,sink,origin)
    value.available_ns=EPOCH+6_050_000_000
    return value

run=clone(old_run.run,adapter=types.SimpleNamespace(replay=replay),sources=sources,git_state=gitstate)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--events',required=True,type=Path);p.add_argument('--config',required=True,type=Path);p.add_argument('--method',required=True,choices=('M2','M3','M3W025'));p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    r=run(a.events,a.config,a.method,a.output)
    print(json.dumps({k:r[k] for k in ('status','method_id','elapsed_s','process_cpu_s','process_peak_rss_kib')}))
