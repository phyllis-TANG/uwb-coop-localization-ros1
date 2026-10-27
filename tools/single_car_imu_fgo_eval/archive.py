"""Bounded source/result archive with complete independent member readback."""
import argparse
import gzip
import hashlib
from pathlib import Path
import subprocess
import tarfile
from meta import ROOT,save,sha


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--archive',type=Path,required=True)
    args=p.parse_args();files=sorted(x for x in args.source.rglob('*') if x.is_file())
    if any(x.is_symlink() for x in args.source.rglob('*')):raise ValueError('symlinks forbidden')
    if any(x.suffix.lower() in ('.bag','.mov') for x in files):raise ValueError('raw media/bag excluded')
    if sum(x.stat().st_size for x in files)>512*1024**2:raise ValueError('archive size budget')
    receipt=args.archive.with_suffix(args.archive.suffix+'.json')
    if args.archive.exists() or receipt.exists():raise FileExistsError('new archive required')
    args.archive.parent.mkdir(parents=True,exist_ok=True)
    expected={'FGO_B_stage1/'+str(x.relative_to(args.source)):sha(x) for x in files}
    with args.archive.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as compressed,tarfile.open(fileobj=compressed,mode='w|') as out:
        for path in files:
            info=out.gettarinfo(str(path),arcname='FGO_B_stage1/'+str(path.relative_to(args.source)))
            info.uid=info.gid=info.mtime=0;info.uname=info.gname='';info.mode=0o644
            with path.open('rb') as f:out.addfile(info,f)
    seen={}
    with tarfile.open(args.archive,'r:gz') as archived:
        for m in archived:
            if not m.isfile() or m.name not in expected or m.name in seen:raise ValueError('unexpected archive member')
            actual=hashlib.sha256(archived.extractfile(m).read()).hexdigest()
            if actual!=expected[m.name]:raise ValueError('member checksum changed')
            seen[m.name]=actual
    if seen!=expected:raise ValueError('missing archive member')
    save(receipt,{'schema_version':1,'status':'DONE','archive_name':args.archive.name,'sha256':sha(args.archive),
        'bytes':args.archive.stat().st_size,'member_sha256':seen,'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'command_argv':__import__('sys').argv,'raw_bags_videos_or_venv_included':False})
    return 0


if __name__=='__main__':raise SystemExit(main())
