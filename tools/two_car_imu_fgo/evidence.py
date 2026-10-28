#!/usr/bin/env python3
"""Immutable evidence packaging and SHA verification, standard library only."""
import argparse
import hashlib
import json
from pathlib import Path,PurePosixPath
import tarfile

SKIP={'tmp','mpl-cache','retrieved-inputs','delivery'}
ROOT_NAME='two_car_imu_fgo_evidence'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def pack(root,archive):
    root=Path(root);archive=Path(archive)
    if archive.exists() or (root/'EVIDENCE_MANIFEST.json').exists():raise FileExistsError('immutable bundle')
    files={}
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root)
        if rel.parts[0] in SKIP or any(x=='__pycache__' for x in rel.parts) or p.suffix=='.bag':continue
        if p.is_symlink():raise ValueError('unexpected symlink '+str(p))
        if p.is_file():files[str(rel)]=dict(sha256=sha(p),size_bytes=p.stat().st_size)
    manifest=dict(schema_version=1,files=files,excluded=['original .bag bytes: retrieve via registered SHA','retrieved archive includes other bags, not repackaged','tmp/cache/delivery'],
        content='all executed originals and four repairs, selected indices, raw field exports, tests, exact source snapshots; no solver execution during packaging')
    mp=root/'EVIDENCE_MANIFEST.json';mp.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    with archive.open('xb') as stream,tarfile.open(fileobj=stream,mode='w:gz') as tf:
        for name in [*files,'EVIDENCE_MANIFEST.json']:tf.add(root/name,arcname=ROOT_NAME+'/'+name,recursive=False)
    return dict(status='PACKED',archive_sha256=sha(archive),size_bytes=archive.stat().st_size,files=len(files),manifest_sha256=sha(mp))


def verify(archive,extract=None):
    archive=Path(archive)
    if extract is not None:
        extract=Path(extract);extract.mkdir(parents=True,exist_ok=False)
    with tarfile.open(archive,'r:gz') as tf:
        members=tf.getmembers();names=[m.name for m in members]
        if len(names)!=len(set(names)):raise ValueError('duplicate members')
        manifest=json.load(tf.extractfile(ROOT_NAME+'/EVIDENCE_MANIFEST.json'))
        expected={ROOT_NAME+'/'+k for k in manifest['files']}|{ROOT_NAME+'/EVIDENCE_MANIFEST.json'}
        if set(names)!=expected:raise ValueError('manifest membership')
        for m in members:
            p=PurePosixPath(m.name)
            if not m.isfile() or p.is_absolute() or '..' in p.parts or p.parts[0]!=ROOT_NAME:raise ValueError('unsafe member')
            body=tf.extractfile(m);h=hashlib.sha256();n=0
            dst=None if extract is None else extract.joinpath(*p.parts)
            if dst:dst.parent.mkdir(parents=True,exist_ok=True)
            out=None if dst is None else dst.open('xb')
            try:
                for block in iter(lambda:body.read(1024*1024),b''):
                    n+=len(block);h.update(block)
                    if out:out.write(block)
            finally:
                if out:out.close()
            name=str(p.relative_to(ROOT_NAME))
            if name in manifest['files']:
                want=manifest['files'][name]
                if n!=want['size_bytes'] or h.hexdigest()!=want['sha256']:raise ValueError('SHA '+name)
    return dict(status='PASS',archive_sha256=sha(archive),size_bytes=archive.stat().st_size,files=len(manifest['files']),extracted_to=None if extract is None else str(extract))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['pack','verify']);p.add_argument('--archive',type=Path,required=True);p.add_argument('--root',type=Path);p.add_argument('--extract',type=Path);v=p.parse_args()
    print(json.dumps(pack(v.root,v.archive) if v.phase=='pack' else verify(v.archive,v.extract),indent=2))
