#!/usr/bin/env python3
"""Independent bounded audit, including older development source identities."""
import argparse
import json
from pathlib import Path
import time
from qaudit import audit
from qio import dump,sha,utc,sources,HERE
def fingerprint():return dict(source_sha256=sources(),protocol_sha256=sha(HERE/'protocol.json'))

def verify(root,cell):
    for entry in cell.get('inputs',[])+cell.get('outputs',[]):
        path=root/entry['relative_path']
        if not path.is_file() or sha(path)!=entry['sha256']:raise ValueError('input/output storage SHA mismatch')


def main():
    p=argparse.ArgumentParser();p.add_argument('--experiment',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--allow-development-reader-update',action='store_true');a=p.parse_args();start=time.monotonic();state=json.loads((a.experiment/'checkpoint.json').read_text());current=fingerprint()
    if current!=state['fingerprint'] and not(a.allow_development_reader_update and state['stage']=='development'):raise ValueError('source/protocol fingerprint mismatch')
    a.output.mkdir(parents=True,exist_ok=False);result=dict(status='IN_PROGRESS',created_at_utc=utc(),execution_fingerprint=state['fingerprint'],reader_fingerprint=current,cells=[]);dump(a.output/'readback.json',result)
    for cell in state['cells']:
        verify(a.experiment,cell)
        if cell['status']!='DONE':result['cells'].append(dict(cell_id=cell['cell_id'],status='NOT_AUDITED_FAILED'));continue
        inp=a.experiment/'inputs'/f"{cell['scenario']}_seed{cell['seed']}"/'events.jsonl.gz'
        try:report=audit(a.experiment/cell['output'],events_path=inp)
        except Exception as error:report=dict(status='FAIL',errors=[type(error).__name__+': '+str(error)])
        dump(a.output/(cell['cell_id']+'.json'),report);result['cells'].append(dict(cell_id=cell['cell_id'],**report));result['elapsed_s']=time.monotonic()-start;dump(a.output/'readback.json',result);print(cell['cell_id'],report['status'],flush=True)
    result.update(status='PASS' if all(c['status']=='PASS' for c in result['cells']) else 'FAIL',elapsed_s=time.monotonic()-start,finished_at_utc=utc());dump(a.output/'readback.json',result);return 0 if result['status']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
