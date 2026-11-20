"""Read every archived lunar certificate. No evaluation or trajectory data needed."""
import csv
import gzip
import hashlib
import io
import json
import subprocess
from decision import verifier, ROOT, pairs

SHA='af844589dc41d38f50b329b6baee3efb25eca208'
DIR='docs/research/lunar_end_to_end/slant/'


def blob(path):
    return subprocess.check_output(['git','show',SHA+':'+DIR+path],cwd=ROOT)


def main():
    rows=list(csv.DictReader(io.StringIO(blob('LEDGER.csv').decode())))
    cases=json.loads(blob('INPUT_MANIFEST.json'))['records']
    plan={(v['case'],m) for v in cases for m in ('P4','N4')}
    assert len(plan)==24 and len(rows)==24 and plan=={(r['case'],r['method']) for r in rows}
    output=[]
    for r in rows:
        case,method=r['case'],r['method']
        folder=f'results/{case}_{method}/'
        raw=blob(folder+'certificate.json.gz')
        receipt=json.loads(blob(folder+'receipt.json'))
        assert hashlib.sha256(raw).hexdigest()==receipt['certificate_sha256']
        x=json.loads(blob(folder+'input.json'),object_pairs_hook=pairs)
        c=json.loads(gzip.decompress(raw),object_pairs_hook=pairs)
        assert case==x['case_id'] and c['mode']=={'N4':'no_peer','P4':'4d'}[method]
        v=verifier('height').check(x,c)
        assert v['status']==r['status']
        for car in ('p','s'):
            output.append(dict(case=case,seed=next(i['seed'] for i in cases if i['case']==case),
                car=car,method=method,state_time=x['source_times'][car],input_hash=x['input_hash'],
                certificate_sha256=receipt['certificate_sha256'],certificate_status=v['status'],
                projection_rectangles=len(c['projections'][car]['rectangles']),estimate_xy=None,
                decision_ready_time=None,PL=None,AL=None,alarm=None,available=None,reason='PUBLICATION_AND_POLICY_NOT_ARCHIVED'))
    print(json.dumps(dict(evidence_sha=SHA,certificates=len(rows),rows=output),indent=2))


if __name__=='__main__':
    main()
