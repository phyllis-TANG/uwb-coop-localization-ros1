"""Portable lossless JSON maps, retaining reference/measurement/estimate separation."""
import argparse,shutil
from bridge import *

def run(source,out):
 source=Path(source);out=Path(out);out.mkdir(parents=True,exist_ok=False);originals={}
 for p in source.glob('*.json'):shutil.copyfile(p,out/p.name)
 for group in ['measurements','reference','estimates','dispatch','failures']:
  if not (source/group).exists():continue
  files=sorted((source/group).rglob('*.json'));mapping={str(p.relative_to(source/group)):read(p) for p in files}
  for p in files:
   obj=mapping[str(p.relative_to(source/group))];b=(json.dumps(obj,indent=2,allow_nan=False)+'\n').encode();assert b==p.read_bytes()
   originals[str(p.relative_to(source))]=filehash(p)
  with (out/(group+'.json.gz')).open('xb') as raw:
   with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0) as f:f.write(json.dumps(mapping,separators=(',',':'),allow_nan=False).encode())
 write(out/'MANIFEST.json',dict(files={str(p.relative_to(out)):dict(sha256=filehash(p),bytes=p.stat().st_size) for p in sorted(out.rglob('*')) if p.is_file()},original_json_sha256=originals,all_original_json_bytes_reconstructed=True))
 print('Archived',len(originals),'JSON records')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out',required=True);a=p.parse_args();run(a.input,a.out)
