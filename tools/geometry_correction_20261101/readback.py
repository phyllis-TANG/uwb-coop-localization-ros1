"""Original PR91 scalar/FD saved graph audit; no optimizer invocation."""
import argparse
import json
from pathlib import Path
from local_support import dump,load

old_support=load('_gc_rb_support','tools/two_car_mechanism_20261101/support.py')

old=load('_gc_readback','tools/two_car_mechanism_20261101/readback.py',{'support':old_support})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True,type=Path);p.add_argument('--events',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('No overwrite')
    r=old.audit(a.run,a.events);dump(a.output,r);print(json.dumps(r))
