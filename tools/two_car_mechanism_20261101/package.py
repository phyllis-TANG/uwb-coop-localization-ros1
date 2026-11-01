"""Hash-verified per-seed archives, no optimization and no raw field data."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
from support import dump, sha


def package(root, output):
    root,output=Path(root),Path(output);output.mkdir(parents=True,exist_ok=False)
    index=json.loads((root/'RUN_INDEX.json').read_text())
    if index['status']!='DONE':raise ValueError('Incomplete matrix')
    for name,digest in index['files'].items():
        if sha(root/name)!=digest:raise ValueError('Changed evidence '+name)
    receipts=[]
    for seed in sorted({c['seed'] for c in index['cells']}):
        members=[root/'RUN_INDEX.json']
        for p in root.rglob('*'):
            if not p.is_file() or p.name=='RUN_INDEX.json':continue
            relative=str(p.relative_to(root))
            if any(part.startswith(str(seed)+'-') for part in Path(relative).parts):members.append(p)
        archive=output/f'{index["partition"]}-seed{seed}.tar.gz'
        expected={root.name+'/'+str(p.relative_to(root)):sha(p) for p in members}
        with tarfile.open(archive,'w:gz') as tf:
            for p in sorted(members):tf.add(p,arcname=root.name+'/'+str(p.relative_to(root)),recursive=False)
        with tarfile.open(archive,'r:gz') as tf:
            if set(tf.getnames())!=set(expected):raise ValueError('Archive member set')
            for member in tf.getmembers():
                if not member.isfile() or '..' in Path(member.name).parts:raise ValueError('Unsafe member')
                if hashlib.sha256(tf.extractfile(member).read()).hexdigest()!=expected[member.name]:raise ValueError('Archive content')
        receipts.append(dict(seed=seed,archive=archive.name,sha256=sha(archive),bytes=archive.stat().st_size,
            members=len(expected),member_sha256=expected))
    dump(output/'ARCHIVE_INDEX.json',dict(status='PASS',partition=index['partition'],source_index_sha256=sha(root/'RUN_INDEX.json'),archives=receipts))
    return receipts


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--matrix',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();r=package(a.matrix,a.output);print(json.dumps(dict(status='PASS',archives=len(r),total_bytes=sum(x['bytes'] for x in r))))
