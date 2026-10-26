"""Create and independently read back a bounded T10 input/evidence archive."""
import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import tarfile

from common import ROOT, sha, write


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--prefix',default='T10_inputs')
    args=p.parse_args()
    if args.prefix not in ('T10_inputs','T10_full_local_results','T10_closure_review'):raise ValueError('explicit archive scope required')
    files=sorted(x for x in args.source.rglob('*') if x.is_file())
    if any(x.is_symlink() for x in args.source.rglob('*')):raise ValueError('symlinks forbidden')
    if sum(x.stat().st_size for x in files)>100*1024**2:raise ValueError('archive budget exceeded')
    if any(x.suffix.lower() in ('.bag','.mov','.zip') for x in files):raise ValueError('raw media/bags forbidden')
    if args.archive.exists() or args.archive.with_suffix(args.archive.suffix+'.json').exists():raise FileExistsError('archive destination exists')
    args.archive.parent.mkdir(parents=True,exist_ok=True)
    expected={args.prefix+'/'+str(x.relative_to(args.source)):sha(x) for x in files}
    with args.archive.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as compressed,tarfile.open(fileobj=compressed,mode='w|') as t:
        for path in files:
            info=t.gettarinfo(str(path),arcname=args.prefix+'/'+str(path.relative_to(args.source)))
            info.uid=info.gid=info.mtime=0;info.uname=info.gname='';info.mode=0o644
            with path.open('rb') as f:t.addfile(info,f)
    verified={}
    with tarfile.open(args.archive,'r:gz') as t:
        for member in t:
            if not member.isfile() or member.name not in expected or member.name in verified:raise ValueError('unexpected archive member')
            h=hashlib.sha256()
            with t.extractfile(member) as f:
                for b in iter(lambda:f.read(1024**2),b''):h.update(b)
            if h.hexdigest()!=expected[member.name]:raise ValueError('archive member changed')
            verified[member.name]=h.hexdigest()
    if verified!=expected:raise ValueError('archive member missing')
    write(args.archive.with_suffix(args.archive.suffix+'.json'),{'schema_version':1,'status':'DONE',
        'archive_name':args.archive.name,'sha256':sha(args.archive),'size_bytes':args.archive.stat().st_size,
        'source_code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'command_argv':__import__('sys').argv,'verified_members':verified,'raw_media_included':False})
    return 0


if __name__=='__main__':raise SystemExit(main())
