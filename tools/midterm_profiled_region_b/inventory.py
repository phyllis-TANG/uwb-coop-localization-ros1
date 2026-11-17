"""Read-only plan/completion inventory, including interrupted runs without STATUS."""
import argparse
from common import *
def inventory(out,stage):
 plan=read(DOC/'INPUTS.json.gz')[stage];rows=[]
 for c in plan:
  for method in ['OLD','PROFILED']:
   unit=c['id']+'_'+method;file=out/(unit+'.json.gz');attempt=out/(unit+'.attempt.json');receipt=out/(unit+'.receipt.json')
   status='UNEXECUTED'
   if file.exists():
    try:read(file);status='COMPLETED' if receipt.exists() else 'RESULT_SAVED_TIMING_UNAVAILABLE'
    except Exception:status='INCOMPLETE_RESULT_UNCERTAIN_NO_RETRY'
   elif attempt.exists():status='ATTEMPT_UNCERTAIN_NO_RETRY'
   rows.append(dict(id=unit,status=status))
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--stage',choices=['deterministic','random'],required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();write(a.out,inventory(a.results,a.stage))
