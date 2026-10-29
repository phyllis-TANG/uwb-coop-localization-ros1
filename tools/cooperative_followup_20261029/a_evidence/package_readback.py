#!/usr/bin/env python3
"""Package derived evidence only; original 54 MB archive is never rewritten."""
import argparse,gzip,hashlib,io,json,subprocess,tarfile
from pathlib import Path
from io_evidence import ART,ROOT,HERE,sha,dump

def package(out):
 out.mkdir(exist_ok=False);members={}
 # Keep failed/earlier derived versions, successful outputs and original receipts.
 for folder in ['analysis-v1','analysis-v2','summary-v1','summary-v2','semantics-v1','tests-v1','tests-v2']:
  for p in sorted((ART/folder).rglob('*')):
   if p.is_file():members['derived/'+str(p.relative_to(ART))]=p.read_bytes()
 for p in sorted(ART.glob('*.log')):members['logs/'+p.name]=p.read_bytes()
 for p in (ART/'evidence-v1').glob('*CHECK.json'):members['original_receipts/'+p.name]=p.read_bytes()
 for p in sorted(HERE.glob('*.py')):members['source/'+p.name]=p.read_bytes()
 members['failed_source/extract-v1.py']=subprocess.check_output(['git','show','17eec40:tools/cooperative_followup_20261029/a_evidence/extract.py'],cwd=ROOT)
 manifest=dict(original_archive_sha256='50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320',original_archive_included=False,
               contents='Derived readback, failed versions, checks and readers. Final report/PR metadata live in Git.',files={n:dict(sha256=hashlib.sha256(b).hexdigest(),size_bytes=len(b)) for n,b in members.items()})
 members['MANIFEST.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
 path=out/'cooperative_followup_20261029_a_evidence_v1.tar.gz'
 with path.open('xb') as raw:
  with gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as compressed:
   with tarfile.open(fileobj=compressed,mode='w') as tf:
    for n,b in sorted(members.items()):
     info=tarfile.TarInfo('cooperative_followup_20261029_a_evidence_v1/'+n);info.size=len(b);info.mode=0o644;info.mtime=0;tf.addfile(info,io.BytesIO(b))
 with tarfile.open(path,'r:gz') as tf:
  for m in tf.getmembers():
   name=m.name.split('/',1)[1];data=tf.extractfile(m).read();assert data==members[name]
 dump(out/'PACKAGE_CHECK.json',dict(status='PASS',archive_path=str(path),sha256=sha(path),size_bytes=path.stat().st_size,
                                  members=len(members),manifest_sha256=hashlib.sha256(members['MANIFEST.json']).hexdigest(),source_sha256=sha(Path(__file__))))
 print(path,sha(path),path.stat().st_size)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();package(a.output)
