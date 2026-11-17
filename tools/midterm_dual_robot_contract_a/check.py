"""Read-only certificate/archive verification. Does not import any searcher."""
import argparse
import hashlib
import json
from pathlib import Path
from core import *

def read_json(path):
    def unique(pairs):
        d={}
        for k,v in pairs:
            need(k not in d,'DUPLICATE_JSON_KEY'); d[k]=v
        return d
    return json.loads(Path(path).read_text(),object_pairs_hook=unique)

def archive_check(input_dir, archive_dir, expected_sha):
    root=Path(archive_dir).resolve(); ready=read_json(root/'RESULTS_READY.json')
    need(ready['schema_version']==VERSION and ready['source_commit']==expected_sha,'B_SOURCE_MISMATCH')
    files=ready['files']; need(isinstance(files,dict) and files,'NO_ARCHIVE_HASHES')
    for name,h in files.items():
        p=(root/name).resolve()
        need(p.is_relative_to(root) and p.is_file() and name!='RESULTS_READY.json','INVALID_ARCHIVE_PATH')
        need(hashlib.sha256(p.read_bytes()).hexdigest()==h,'ARCHIVE_HASH_MISMATCH')
    need(ready['archive_hash']==digest(files),'ARCHIVE_MANIFEST_HASH_MISMATCH')
    records=ready['records']; stage=ready['stage']; need(stage in ('deterministic','conditional_random'),'STAGE_UNSUPPORTED')
    inputs=read_json(Path(input_dir)/('deterministic.json' if stage=='deterministic' else 'random_conditional.json'))
    expected={(x['case_id'],mode) for x in inputs for mode in ('5d','4d','no_peer')}; by={x['case_id']:x for x in inputs}
    seen=set(); results=[]; attempts=[]
    for r in records:
        key=(r['case_id'],r['mode']); need(key in expected and key not in seen,'DENOMINATOR_DUPLICATE_OR_EXTRA'); seen.add(key)
        need(r['input_hash']==by[key[0]]['input_hash'],'RECORD_INPUT_HASH')
        if r['execution_status']!='CERTIFICATE_AVAILABLE':
            need(r['execution_status'] in ('NOT_RUN','FAILED','INTERRUPTED'),'EXECUTION_STATUS')
            need(isinstance(r['reason'],str) and r['reason'],'MISSING_FAILURE_REASON')
            attempts.append(r); continue
        name=r['certificate_file']; need(name in files,'UNHASHED_CERTIFICATE')
        cert=read_json(root/name); need(cert['mode']==key[1],'RECORD_MODE_MISMATCH')
        result=check(by[key[0]],cert); result['case_id']=key[0]; results.append(result)
    need(seen==expected,'DENOMINATOR_MISSING')
    return {'cross_readback':'PASS' if not attempts else 'INCOMPLETE', 'locked_b_sha':expected_sha,
            'archive_hash':ready['archive_hash'],'stage':stage,'planned':len(expected),'certified':len(results),
            'not_certified':len(attempts),'attempts':attempts,'results':results,
            'conditional_random_gate':'must separately satisfy HANDOFF deterministic gate; archive validation does not authorize a random stage'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('certificate'); p.add_argument('inputs'); p.add_argument('case_id'); p.add_argument('certificate')
    p=sub.add_parser('archive'); p.add_argument('input_dir'); p.add_argument('archive_dir'); p.add_argument('expected_sha')
    a=parser.parse_args()
    try:
        if a.action=='archive': out=archive_check(a.input_dir,a.archive_dir,a.expected_sha)
        else:
            xs=read_json(a.inputs); x=next(x for x in xs if x['case_id']==a.case_id); out=check(x,read_json(a.certificate))
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (Invalid,KeyError,TypeError,ValueError,StopIteration) as e:
        print(json.dumps({'certificate_valid':False,'error':str(e)},ensure_ascii=False)); raise SystemExit(1)
