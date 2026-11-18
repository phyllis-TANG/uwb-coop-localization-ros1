"""Read-only interrupted stage inventory. Never retries an attempt."""
import argparse
from common import *
from runtime import plans,identity,inspect_unit

def inventory(out,stage,inputs,freeze,lock):
 rows=[]
 for job in plans(inputs,stage):
  try:
   row=inspect_unit(out,job,identity(job,freeze,lock));status=row['status'] if row else 'UNEXECUTED'
  except Exception as e:status=str(e)
  rows.append(dict(id=job['id'],status=status))
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--stage',required=True);p.add_argument('--freeze',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();write(a.out,inventory(a.results,a.stage,read(DOC/'INPUTS.json.gz'),a.freeze,read(DOC/'SOURCE_LOCK.json')))
