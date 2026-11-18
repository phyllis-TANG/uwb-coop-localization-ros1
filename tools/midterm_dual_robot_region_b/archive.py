"""Portable byte-preserving archive with exact membership and hashes."""
import tarfile
from pathlib import Path,PurePosixPath
from common import sha,read,write

def pack(files,base,out):
 base=Path(base);out=Path(out);assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True)
 members={str(Path(f).relative_to(base)):sha(f) for f in files}
 with tarfile.open(out,'x:gz') as tar:
  for name in sorted(members):tar.add(base/name,arcname=name,recursive=False)
 return dict(archive=out.name,sha256=sha(out),bytes=out.stat().st_size,files=members)
def unpack(archive,manifest,out):
 archive=Path(archive);out=Path(out);assert sha(archive)==manifest['sha256'];assert not out.exists();out.mkdir(parents=True);seen=set()
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar:
   p=PurePosixPath(member.name);assert member.isfile() and not p.is_absolute() and '..' not in p.parts
   assert member.name in manifest['files'] and member.name not in seen;seen.add(member.name)
   target=out/member.name;target.parent.mkdir(parents=True,exist_ok=True)
   with target.open('xb') as f:f.write(tar.extractfile(member).read())
   assert sha(target)==manifest['files'][member.name]
 assert seen==set(manifest['files']);return dict(status='PASS',files=len(seen))
