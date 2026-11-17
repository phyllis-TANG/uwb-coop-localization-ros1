"""Portable archive extraction with exact member/hash verification; zero search."""
import argparse,tarfile
from pathlib import PurePosixPath
from common import *

def unpack(evidence,ready,out):
 assert not out.exists();out.mkdir(parents=True);seen=set()
 for name,m in ready['archives'].items():
  archive=evidence/name;assert sha(archive)==m['sha256'];local=set()
  with tarfile.open(archive,'r:gz') as tar:
   for member in tar:
    path=PurePosixPath(member.name);assert member.isfile() and not path.is_absolute() and '..' not in path.parts
    assert member.name in ready['files'] and member.name in m['files'] and member.name not in seen;seen.add(member.name);local.add(member.name)
    dest=out/member.name;dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(tar.extractfile(member).read())
    assert sha(dest)==ready['files'][member.name]==m['files'][member.name]
  assert local==set(m['files'])
 assert seen==set(ready['files']);assert digest(ready['files'])==ready['archive_hash'];write(out/'RESULTS_READY.json',ready)
 return dict(status='PASS',files=len(seen),archives=len(ready['archives']),search_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--ready',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(unpack(a.evidence,read(a.ready),a.out)))
