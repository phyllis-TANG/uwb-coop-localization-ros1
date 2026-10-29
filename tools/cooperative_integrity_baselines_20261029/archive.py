#!/usr/bin/env python3
"""Bounded immutable archive, no raw bags/videos/venv; stream full member readback."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile
from common import ROOT,HERE,canonical,sha,write_json,SPEC


def build(target,entries):
    if sum(len(b) for _,b in entries)>SPEC['max_new_artifacts_bytes']:raise ValueError('Archive uncompressed scope exceeds cap')
    manifest=[dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in entries]
    payload=sorted(entries+[('MANIFEST.json',(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode())])
    with target.open('xb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z,tarfile.open(fileobj=z,mode='w') as tar:
        for name,data in payload:
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644;info.mtime=0;info.uid=0;info.gid=0
            tar.addfile(info,io.BytesIO(data))
    expected={name:hashlib.sha256(data).hexdigest() for name,data in payload}
    with tarfile.open(target,'r:gz') as tar:
        members=tar.getmembers();assert len(members)==len(expected)
        for m in members:
            assert m.isfile() and m.name in expected and not m.name.startswith('/') and '..' not in Path(m.name).parts
            assert hashlib.sha256(tar.extractfile(m).read()).hexdigest()==expected[m.name]
    return dict(path=str(target.resolve()),sha256=sha(target),bytes=target.stat().st_size,members=len(payload),member_readback='PASS')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--task-root',type=Path,required=True);ap.add_argument('--full-output',type=Path,required=True);ap.add_argument('--review-output',type=Path,required=True);a=ap.parse_args()
    entries=[]
    for folder in ('reproduction-v2','readback-v3','readback-v4','report-v1','report-v2','logs'):
        for p in sorted((a.task_root/folder).rglob('*')):
            if p.is_file():entries.append(('task/'+str(p.relative_to(a.task_root)),p.read_bytes()))
    for p in sorted(a.task_root.glob('*.json')):entries.append(('task/'+p.name,p.read_bytes()))
    for p in sorted(HERE.iterdir()):
        if p.is_file():entries.append(('delivery-source/'+p.name,p.read_bytes()))
    frozen=json.loads((a.task_root/'reproduction-v2/FROZEN_INDEX.json').read_text())
    for p in frozen['source_sha256']:
        data=subprocess.check_output(['git','show',frozen['execution_commit']+':'+p],cwd=ROOT)
        assert hashlib.sha256(data).hexdigest()==frozen['source_sha256'][p]
        entries.append(('online-source/'+Path(p).name,data))
    for p,h in frozen['kernel']['files'].items():
        data=(ROOT/p).read_bytes();assert hashlib.sha256(data).hexdigest()==h;entries.append(('frozen-source/'+p,data))
    doc=ROOT/'docs/research/cooperative_integrity_baselines_20261029'
    for name in ('PLAN.md','FROZEN_SPEC.md','LITERATURE.md','REPORT.md','COMMANDS.md','HANDOFF.md','SOURCE_AUDIT.json','ENVIRONMENT.json'):
        entries.append(('review/'+name,(doc/name).read_bytes()))
    full=build(a.full_output,entries)
    compact=[('review/'+str(p.relative_to(doc)),p.read_bytes()) for p in sorted(doc.rglob('*')) if p.is_file() and p.suffix not in ('.gz',) and 'artifacts' not in p.parts]
    # Include compressed declaration CSV explicitly, not the complete monitor JSONL.
    p=doc/'results/declarations.csv.gz';compact.append(('review/results/declarations.csv.gz',p.read_bytes()))
    review=build(a.review_output,compact)
    write_json(a.full_output.with_suffix(a.full_output.suffix+'.json'),dict(full=full,review=review,scope='No bag/video/raw event cache/venv. Exact original online-source and final delivery-source both retained.'))
    print(json.dumps(dict(full=full,review=review),indent=2))
if __name__=='__main__':main()
