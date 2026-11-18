"""Post-hoc lunar readback, using independently pinned input and evidence commits."""
import argparse
import csv
import io
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess

import checker as C


def unique(pairs):
    result=dict(pairs)
    C.need(len(result)==len(pairs),'DUPLICATE_KEY')
    return result


def load(sha,path):
    raw=subprocess.check_output(['git','show',f'{sha}:{path}'])
    payload=gzip.decompress(raw) if path.endswith('.gz') else raw
    return json.loads(payload,object_pairs_hook=unique),hashlib.sha256(raw).hexdigest()


def run(plan_sha,plan_path,evidence_sha,ledger_path):
    for sha in (plan_sha,evidence_sha):
        C.need(re.fullmatch('[0-9a-f]{40}',sha),'FULL_SHA_REQUIRED')
    plan,plan_hash=load(plan_sha,plan_path)
    if ledger_path.endswith('.csv'):
        raw=subprocess.check_output(['git','show',f'{evidence_sha}:{ledger_path}'])
        ledger_hash=hashlib.sha256(raw).hexdigest()
        ledger=[]
        for entry in csv.DictReader(io.StringIO(raw.decode())):
            mode={'P4':'4d','N4':'no_peer'}[entry['method']]
            status=entry['status']
            row=dict(case_id=entry['case'],mode=mode,reason=status,
                     status='NOT_RUN' if status.startswith('NOT_RUN') else status)
            if row['status']!='NOT_RUN':
                row.update(input_hash=entry['input_hash'],certificate=entry['certificate'],sha256=entry['sha256'])
            ledger.append(row)
    else:
        ledger,ledger_hash=load(evidence_sha,ledger_path)
    expected={(segment,epoch,condition) for segment in ('1','2')
              for epoch in ('start','middle','end') for condition in ('normal','ramp')}
    cases={}
    slots=set()
    for item in plan:
        slot=(item['segment'],item['epoch'],item['condition'])
        C.need(slot in expected and slot not in slots,'PLAN_SLOT')
        slots.add(slot)
        x,_=load(plan_sha,item['input'])
        C.validate(x)
        C.need(x['input_hash']==item['input_hash'] and x['case_id'] not in cases and
               len(x['measurement_ids'])==9,'FROZEN_PAIRED_INPUT')
        cases[x['case_id']]=x
    C.need(slots==expected,'PLAN_DENOMINATOR')
    archived={}
    for row in ledger:
        key=row['case_id'],row['mode']
        C.need(key[0] in cases and key[1] in ('4d','no_peer') and key not in archived,'UNPLANNED_OR_DUPLICATE_RESULT')
        archived[key]=row
    results=[]
    for case,x in cases.items():
        for mode in ('4d','no_peer'):
            key=case,mode
            item=dict(case_id=case,mode=mode,input_hash=x['input_hash'])
            results.append(item)
            if key not in archived:
                item['outcome']='MISSING'
                continue
            row=archived[key]
            try:
                if row['status']!='NOT_RUN' or 'input_hash' in row:
                    C.need(row['input_hash']==x['input_hash'],'LEDGER_INPUT_IDENTITY')
                if row['status'] in ('NOT_RUN','FAILED'):
                    C.need(not row.get('certificate'),'UNACCOUNTED_CERTIFICATE')
                    item.update(outcome=row['status'],reason=row['reason'])
                    continue
                C.need(row['status']=='DELIVERED','LEDGER_STATUS')
                c,checksum=load(evidence_sha,row['certificate'])
                item.update(certificate=row['certificate'],certificate_sha256=checksum)
                C.need(c['mode']==mode and checksum==row['sha256'],'ARCHIVE_IDENTITY')
                verdict=C.check(x,c)
                item.update(verdict=verdict,queue=c.get('queue',[]),
                            projection_hash=C.K.digest(c.get('projections',{})),
                            outcome=verdict['status'])
                tolerance=C.q(x['budget']['position_resolution'])
                item['target_resolution']=not item['queue'] and all(C.q(b)-C.q(a)<=tolerance
                    for n in c.get('nodes',[]) if n['kind']=='UNDECIDED' for a,b in n['box'])
            except (ValueError,KeyError,TypeError,IndexError,OSError,subprocess.CalledProcessError) as exc:
                item.update(outcome='REJECT',reason=str(exc))
    return dict(plan_sha=plan_sha,evidence_sha=evidence_sha,plan_hash=plan_hash,
                ledger_hash=ledger_hash,planned=24,ledger_rows=len(ledger),
                outcomes=dict(Counter(r['outcome'] for r in results)),rows=results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('plan_sha','plan_path','evidence_sha','ledger_path'):
        p.add_argument(arg)
    args=p.parse_args()
    report=run(**vars(args))
    print(json.dumps(report,indent=2))
    raise SystemExit(int(bool(report['outcomes'].get('REJECT'))))
