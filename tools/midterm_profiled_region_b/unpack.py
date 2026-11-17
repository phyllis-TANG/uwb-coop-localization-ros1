"""Byte-verified portable extraction, refusing overwrite and non-file members."""
import argparse,tarfile
from pathlib import PurePosixPath
from common import *
def unpack(src,out):
 assert not out.exists(),'Refuse existing destination';out.mkdir(parents=True);m=read(src/'MANIFEST.json')
 for name,z in m['archives'].items():
  assert sha(src/name)==z['sha256']
  with tarfile.open(src/name,'r:gz') as t:
   for member in t:
    p=PurePosixPath(member.name);assert member.isfile() and not p.is_absolute() and '..' not in p.parts
    dest=out/str(p);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('xb') as f:f.write(t.extractfile(member).read())
 for file,h in m['files'].items():assert sha(out/file)==h,file
 return dict(status='PASS',files=len(m['files']),archives=len(m['archives']),search_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(unpack(a.archive,a.out)))
