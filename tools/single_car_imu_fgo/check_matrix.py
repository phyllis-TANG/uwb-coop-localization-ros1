#!/usr/bin/env python3
"""Bounded independent audit of the immutable matrix cells."""
import argparse
import json
from pathlib import Path
import time
from audit import audit
from batch import fingerprint,verify_completed
from io_utils import dump,utc


def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds',type=float,default=1800);a=p.parse_args();start=time.monotonic();state=json.loads((a.experiment/'checkpoint.json').read_text())
    if state['fingerprint']!=fingerprint():raise ValueError('source/protocol lock differs')
    a.output.mkdir(parents=True,exist_ok=False);result=dict(status='IN_PROGRESS',started_at_utc=utc(),fingerprint=state['fingerprint'],cells=[]);dump(a.output/'readback.json',result)
    for cell in state['cells']:
        if time.monotonic()-start>a.max_seconds:result['status']='TIMEOUT';break
        verify_completed(a.experiment,cell)
        if cell['status']!='DONE':result['cells'].append(dict(cell_id=cell['cell_id'],status='NOT_AUDITED_FAILED_RUN'));continue
        run=a.experiment/cell['output'];metadata=json.loads((run/'run.json').read_text())
        if metadata['source_sha256']!=state['fingerprint']['source_sha256']:raise ValueError('cell source lock differs')
        inp=a.experiment/'inputs'/f"{cell['scenario']}_seed{cell['seed']}"/'events.jsonl.gz';report=audit(run,inp);dump(a.output/(cell['cell_id']+'.json'),report);result['cells'].append(dict(cell_id=cell['cell_id'],**report));result['elapsed_s']=time.monotonic()-start;dump(a.output/'readback.json',result);print(cell['cell_id'],report['status'],flush=True)
    else:result['status']='PASS' if all(r['status']=='PASS' for r in result['cells']) else 'FAIL'
    result.update(elapsed_s=time.monotonic()-start,finished_at_utc=utc());dump(a.output/'readback.json',result);return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
