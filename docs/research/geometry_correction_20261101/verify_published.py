"""Verify/recover published evidence; stdlib only, no optimizer imports."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile

DOC=Path(__file__).resolve().parent
REPO=DOC.parents[2]
def load(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    index=load(DOC/'ARTIFACTS.json');seen=set()
    for archive in index['archives']:
        p=DOC/archive['path']
        if p.stat().st_size!=archive['bytes'] or sha(p)!=archive['sha256']:raise ValueError('Archive hash: '+str(p))
        with tarfile.open(p,'r:gz') as tf:
            members=tf.getmembers()
            if len(members)!=len(archive['members']) or {m.name for m in members}!=set(archive['members']):raise ValueError('Archive member list')
            for member in members:
                name=Path(member.name)
                if not member.isfile() or name.is_absolute() or '..' in name.parts or member.name in seen:raise ValueError('Unsafe or duplicate member')
                expected=archive['members'][member.name]
                if member.size!=expected['bytes'] or hashlib.sha256(tf.extractfile(member).read()).hexdigest()!=expected['sha256']:raise ValueError('Member hash')
                seen.add(member.name)
            tf.extractall(output,filter='data')
    if len(seen)!=732 or len(seen)!=index['member_count']:raise ValueError('Evidence member count')
    root=output/index['extraction_root'];manifest=load(root/'delivery/FULL_ARTIFACT_MANIFEST.json')
    receipt=load(DOC/'checks/DELIVERY_RECEIPT.json')
    if sha(root/'delivery/FULL_ARTIFACT_MANIFEST.json')!=receipt['full_manifest_sha256']:raise ValueError('Original manifest SHA')
    for name,v in manifest['files'].items():
        p=root/name
        if p.stat().st_size!=v['bytes'] or sha(p)!=v['sha256']:raise ValueError('Original private bytes: '+name)
    for dirname,indexname in [('matrix-v1','RUN_INDEX.json'),('analysis-v1','ANALYSIS_INDEX.json')]:
        data=load(root/dirname/indexname)
        if data['status']!='DONE':raise ValueError('Incomplete experiment')
        for name,h in data['files'].items():
            if sha(root/dirname/name)!=h:raise ValueError('Input/output index binding: '+name)
    for p in (DOC/'results').iterdir():
        source=root/('matrix-v1' if p.name=='RUN_INDEX.json' else 'analysis-v1')/p.name
        if sha(source)!=sha(p):raise ValueError('Published summary differs from original: '+p.name)
    protocol=REPO/'docs/research/geometry_correction_20261101_private/PROTOCOL.json'
    locked=load(root/'delivery/SOURCE_LOCK.json')
    for name,h in locked.items():
        if sha(REPO/name)!=h:raise ValueError('Frozen source changed: '+name)
    matrix=load(root/'matrix-v1/RUN_INDEX.json')
    if sha(protocol)!=matrix['protocol_sha256'] or matrix['code_commit']!='63701fee9067d3517c4db9dde93a15891fc8335e' or matrix['worktree_dirty'] or len(matrix['cells'])!=48:raise ValueError('Freeze binding')
    result=dict(status='PASS',archives=len(index['archives']),archive_members=len(seen),original_private_files_byte_identical=len(manifest['files']),source_files_byte_identical=len(locked),optimizer_cells=48,new_optimizer_runs=0,protocol_sha256=sha(protocol),frozen_source_commit=matrix['code_commit'])
    (output/'ARCHIVE_READBACK.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);args=parser.parse_args();print(json.dumps(verify(args.output)))
