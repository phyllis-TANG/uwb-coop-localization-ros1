"""Read Git objects and verify/extract PR133 evidence without executing B code."""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
from core import canonical, digest, need, validate
from check import read_json

B_SHA='5e3579086776725f9330f64eca75b63a21cd661c'
B_PREFIX='docs/research/midterm_dual_robot_region_b/'
A_SHA='e45ca6d5940ff9f28233f03fb3502d5ed7004817'
A_PREFIX='docs/research/midterm_dual_robot_contract_a/'
SPECIAL={'empty_in_domain','domain_closed_contact','coincident_zero_distance','forced_budget'}

def blob(repo,sha,path):
    return subprocess.check_output(['git','show',sha+':'+path],cwd=repo)

def sha(data):return hashlib.sha256(data).hexdigest()

def lock(repo,out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    ready_bytes=blob(repo,B_SHA,B_PREFIX+'RESULTS_READY.json'); ready=json.loads(ready_bytes)
    need(ready['a_frozen_sha']==A_SHA,'A_SOURCE_MISMATCH')
    need(digest(ready['files'])==ready['archive_hash'],'ARCHIVE_HASH_MISMATCH')
    (out/'RESULTS_READY.json').write_bytes(ready_bytes)
    extracted={}; archives={}
    for name,meta in ready['archives'].items():
        data=blob(repo,B_SHA,B_PREFIX+'evidence/'+name)
        need(sha(data)==meta['sha256'] and len(data)==meta['bytes'],'ARCHIVE_BYTES_MISMATCH')
        archives[name]=meta['sha256']
        with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as tar:
            members=tar.getmembers()
            need(len(members)==len(meta['files']),'TAR_MEMBER_COUNT')
            for member in members:
                path=PurePosixPath(member.name)
                need(member.isfile() and not path.is_absolute() and '..' not in path.parts,'UNSAFE_TAR_MEMBER')
                need(member.name in meta['files'] and member.name not in extracted,'UNEXPECTED_OR_DUPLICATE_MEMBER')
                raw=tar.extractfile(member).read()
                need(sha(raw)==meta['files'][member.name] and ready['files'][member.name]==sha(raw),'PAYLOAD_HASH_MISMATCH')
                dest=out/member.name; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(raw)
                extracted[member.name]=sha(raw)
    need(extracted==ready['files'],'INCOMPLETE_ARCHIVE')
    source_lock=json.loads(blob(repo,B_SHA,B_PREFIX+'SOURCE_LOCK.json'))
    need(source_lock['a_sha']==A_SHA,'B_SOURCE_LOCK_A_SHA')
    for name,h in source_lock['files'].items():need(sha(blob(repo,A_SHA,name))==h,'FROZEN_SOURCE_HASH_MISMATCH')
    inp=blob(repo,A_SHA,A_PREFIX+'inputs/deterministic.json'); (out/'inputs.json').write_bytes(inp)
    xs=json.loads(inp); [validate(x) for x in xs]; inputs={x['case_id']:x for x in xs}
    planned={(x['case_id'],m) for x in xs for m in ('5d','4d','no_peer') if m!='no_peer' or x['case_id'] not in SPECIAL}
    seen=set(); formal=[]; outside=[]
    for r in ready['records']:
        key=(r['case_id'],r['mode']); need(key not in seen,'DUPLICATE_RECORD'); seen.add(key)
        need(r['input_hash']==inputs[key[0]]['input_hash'],'RECORD_INPUT_MISMATCH')
        if key not in planned:
            need(key[0] in SPECIAL and key[1]=='no_peer' and r['execution_status']=='NOT_RUN' and r['reason']=='OUTSIDE_USER_AUTHORIZED_PLAN','UNEXPECTED_UNPLANNED_RECORD')
            outside.append(r);continue
        need(r['execution_status']=='CERTIFICATE_AVAILABLE' and r['certificate_file'] in extracted,'MISSING_CERTIFICATE')
        formal.append(r)
    need({(r['case_id'],r['mode']) for r in formal}==planned and len(formal)==44 and len(outside)==4,'FORMAL_DENOMINATOR')
    result={'schema':'DUAL-A-CHECKER-V2-EVIDENCE-LOCK','delivery_sha':B_SHA,'evidence_source_commit':ready['source_commit'],
            'run_frozen_sha':ready['run_frozen_sha'],'a_frozen_sha':A_SHA,'ready_sha256':sha(ready_bytes),
            'archive_hash':ready['archive_hash'],'archives':archives,'verified_payload_files':len(extracted),
            'verified_frozen_source_files':len(source_lock['files']),'input_file_sha256':sha(inp),'formal_records':formal,
            'outside_plan_records':outside,'formal_denominator':{'J5':16,'P4':16,'N4':12,'total':44},
            'conditional_random':{'planned':240,'performed_by_A':0,'b_recorded_completed':ready['denominators']['random_completed'],
                                  'b_recorded_status':ready['random_stage']}}
    (out/'EVIDENCE_LOCK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--repo',default='.');p.add_argument('--out',required=True);a=p.parse_args()
    r=lock(a.repo,a.out);print(json.dumps({k:v for k,v in r.items() if k not in ('archives','formal_records','outside_plan_records')},indent=2))
