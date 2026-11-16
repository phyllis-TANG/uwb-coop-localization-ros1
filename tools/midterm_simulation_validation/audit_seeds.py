"""Read-only Git exposure-record scan; registers seeds without generating observations."""
import argparse
import ast
import gzip
import hashlib
import json
import re
import subprocess
from pathlib import Path
from core import ROOT,DOC,load_config,digest
from pipeline import exclusive

def cmd(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def audit(pr_heads):
    c=load_config();seeds=c['seeds']['formal'];pattern=re.compile(rb'(?<![\d.])(?:'+b'|'.join(str(s).encode() for s in seeds)+rb')(?!\d)')
    prs=json.loads(pr_heads.read_text());refs=sorted(set(cmd('for-each-ref','--format=%(objectname)').decode().splitlines()+[p['headRefOid'] for p in prs]))
    blobs={};missing_commits=[];excluded=collections_counter={}
    for sha in refs:
        try:data=cmd('ls-tree','-rlz',sha)
        except subprocess.CalledProcessError:missing_commits.append(sha);continue
        for line in data.split(b'\0'):
            if not line:continue
            meta,path=line.split(b'\t',1);parts=meta.split();name=path.decode(errors='replace')
            if parts[1]!=b'blob':continue
            if name.startswith(('tools/midterm_simulation_validation/','docs/research/midterm_simulation_validation/')):continue
            # All textual repository records and compressed textual evidence, deduplicated.
            if not name.lower().endswith(('.md','.json','.jsonl','.csv','.txt','.log','.py','.sh','.yaml','.yml','.toml','.ini','.cfg','.json.gz','.jsonl.gz','.csv.gz')):continue
            oid=parts[2].decode();size=int(parts[3]);blobs.setdefault(oid,dict(path=name,size=size,commit=sha))
    matches=[];ranges=[];scanned=[];missing_blobs=[]
    for oid,info in sorted(blobs.items()):
        try:data=cmd('cat-file','blob',oid)
        except subprocess.CalledProcessError:missing_blobs.append(dict(oid=oid,**info));continue
        if data.startswith(b'\x1f\x8b'):
            try:data=gzip.decompress(data)
            except Exception as exc:missing_blobs.append(dict(oid=oid,error=repr(exc),**info));continue
        hit=pattern.findall(data)
        if hit:matches.append(dict(oid=oid,path=info['path'],matches=sorted(set(x.decode() for x in hit))))
        if info['path'].endswith('.py'):
            try:tree=ast.parse(data.decode())
            except (SyntaxError,UnicodeError):tree=None
            if tree:
                for node in ast.walk(tree):
                    if isinstance(node,ast.Call) and ((isinstance(node.func,ast.Name) and node.func.id=='range') or (isinstance(node.func,ast.Attribute) and node.func.attr=='arange')):
                        try:args=[ast.literal_eval(a) for a in node.args];r=range(*args)
                        except (ValueError,TypeError):continue
                        overlap=[s for s in seeds if s in r]
                        if overlap:ranges.append(dict(oid=oid,path=info['path'],line=node.lineno,overlap=overlap))
        scanned.append(dict(oid=oid,path=info['path'],commit=info['commit'],uncompressed_bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    result=dict(config_sha256=digest(c),formal_seeds=seeds,formal_observations_generated=0,formal_runs=0,status='REGISTERED_UNEXPOSED_IN_AUDITED_RECORDS',known_exposed_ranges=[[26011601,26011603],[621160101,621160112],[16101,16102],[17101,17150]],bootstrap_seed=c['statistics']['bootstrap_seed'],bootstrap_seed_is_not_observation_seed=True,scope='All text/code/config and compressed textual evidence in local refs and all 101 GitHub PR head commits returned by audit; exact integer tokens plus literal Python range/arange overlap; excludes this new delivery itself. Does not assert knowledge of unrecorded external executions.',pr_heads=prs,commits=refs,unique_blobs=len(scanned),uncompressed_bytes=sum(x['uncompressed_bytes'] for x in scanned),literal_matches=matches,literal_range_overlaps=ranges,missing_commits=missing_commits,missing_blobs=missing_blobs,scanned_records=scanned)
    if matches or ranges or missing_commits or missing_blobs:result['status']='AUDIT_INCOMPLETE_OR_COLLISION'
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pr-heads',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();r=audit(a.pr_heads);exclusive(a.out,r);print(json.dumps({k:v for k,v in r.items() if k not in ['scanned_records','commits','pr_heads']},indent=2));raise SystemExit(0 if r['status']=='REGISTERED_UNEXPOSED_IN_AUDITED_RECORDS' else 1)
