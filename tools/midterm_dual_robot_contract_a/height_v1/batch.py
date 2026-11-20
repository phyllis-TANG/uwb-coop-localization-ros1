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
                folder=str(Path(ledger_path).parent/'results'/(entry['case']+'_'+entry['method']))
                receipt,_=load(evidence_sha,folder+'/receipt.json')
                archived_input,_=load(evidence_sha,folder+'/input.json')
                row.update(status='DELIVERED',input_hash=archived_input['input_hash'],
                           certificate=folder+'/certificate.json.gz',sha256=receipt['certificate_sha256'],
                           csv=entry,root=receipt['event_root'],archived_input=archived_input)
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
        shared=x
        for mode in ('4d','no_peer'):
            x=shared
            if mode=='no_peer' and ledger_path.endswith('.csv'):
                x=C.K.seal(dict(shared,**{k:shared[k][:8] for k in ('measurement_ids','observations','variance')}))
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
                if 'csv' in row:
                    C.need(row['archived_input']==x and row['root']==C.event_root(x),'FROZEN_ORIGINAL_OR_ROOT')
                verdict=C.check(x,c)
                item.update(verdict=verdict,queue=c.get('queue',[]),
                            projection_hash=C.K.digest(c.get('projections',{})),
                            outcome=verdict['status'])
                tolerance=C.q(x['budget']['position_resolution'])
                item['target_resolution']=not item['queue'] and all(C.q(b)-C.q(a)<=tolerance
                    for n in c.get('nodes',[]) if n['kind']=='UNDECIDED' for a,b in n['box'])
                if 'csv' in row:
                    entry=row['csv']
                    C.need(entry['status']==verdict['status'] and entry['certificate']=='PASS'
                           and int(entry['nodes'])==len(c.get('nodes',[]))
                           and entry['budget_stop']==str(bool(item['queue']))
                           and entry['resolution_met']==str(item['target_resolution']), 'LEDGER_RESULT')
                    eval_path=str(Path(ledger_path).parent/'evaluation'/(case+'.json'))
                    # Evaluation is read only after accepting the certificate.
                    truth,_=load('3b68bcf0df9de496cf7353f3cd506a06e5a6f40c',eval_path)
                    position=[C.q(v) for xyz in truth['xyz'] for v in xyz[:2]]
                    hit=[False]*3
                    for node in c.get('nodes',[]):
                        if node['kind'] in ('INSIDE','UNDECIDED','PENDING'):
                            axes=[C.q(a)<=v<=C.q(b) for v,(a,b) in zip(position,node['box'])]
                            for i,ok in enumerate((all(axes),all(axes[:2]),all(axes[2:]))):
                                hit[i]|=ok
                    noise=sum(C.q(e)**2/C.q(v) for e,v in zip(truth['generated_noise'],x['variance']))
                    event=noise<=C.q(c['threshold_certificate']['tau'])
                    C.need(all(entry[k]==str(v) for k,v in zip(('joint_hit','p_hit','s_hit','original_event'),[*hit,event])), 'EVALUATION_MISMATCH')
                    item.update(joint_hit=hit[0],p_hit=hit[1],s_hit=hit[2],original_event=event,
                                nodes=len(c.get('nodes',[])),reported_wall_seconds=entry['wall_seconds'])
                    for car,pr in c.get('projections',{}).items():
                        for field,col in [('radius','radius'),('area_upper','area_upper')]:
                            value=pr[field]
                            cell=entry[car+'_'+col]
                            C.need((not cell and value is None) or (value is not None and float(C.q(value))==float(cell)), 'LEDGER_REGION')
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
