"""Ordinary CLI: measurement + solver config only, never reference labels."""
import argparse
from bridge import *
from engine import once,lock

def run(measurement,method,config,out):
 o=read(measurement);cfg=read(config);f,start,_=problem(o,method);out=Path(out);out.mkdir(parents=True,exist_ok=False)
 with lock(out/'METHOD_LOCK'):
  p0=once(o,method,start,cfg['P0'],out,'P0');p1=None
  if p0['estimate'] is not None and np.isfinite(p0['estimate']).all():p1=once(o,method,p0['estimate'],cfg['P1'],out,'P1')
  final=p1 if p1 is not None and p1['estimate'] is not None else p0
  accepted=bool(p1 is not None and p1['accepted'])
  write(out/'FINAL.json',dict(method=method,stage=final['stage'],status=final['status'] if p1 is not None and p1['estimate'] is not None else 'NO_FINITE_P1',accepted=accepted,estimate=final['estimate'],optimizer_calls=1+int(p1 is not None),finite=final['estimate'] is not None))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--measurement',required=True);p.add_argument('--method',choices=['M0','M1','M2'],required=True);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 def guard(event,args):
  if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)) and 'reference' in os.fsdecode(args[0]).split(os.sep):raise PermissionError('reference forbidden to solver')
 sys.addaudithook(guard);run(a.measurement,a.method,a.config,a.out)
