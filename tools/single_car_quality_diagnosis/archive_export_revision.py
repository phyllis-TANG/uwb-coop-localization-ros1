#!/usr/bin/env python3
"""Save a separate export-correction archive; preserve both original archives."""
import argparse,hashlib,json,shutil,tarfile
from pathlib import Path
from verify_evidence import sha

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--revision',type=Path,required=True);ap.add_argument('--nas',type=Path,required=True);a=ap.parse_args();root=a.revision
 source=root/'source';source.mkdir(exist_ok=False)
 for p in Path(__file__).parent.glob('*.py'):shutil.copyfile(p,source/p.name)
 files=[p for p in sorted(root.rglob('*')) if p.is_file() and p.name!='archive.log']
 out=root/'archives';out.mkdir(exist_ok=False)
 manifest=dict(files=[dict(path=str(p.relative_to(root)),size_bytes=p.stat().st_size,sha256=sha(p)) for p in files])
 mp=out/'manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');archive=out/'quality_fgo_bias_null_export_20261027.tar.gz';prefix='quality_fgo_bias_null_export/'
 with tarfile.open(archive,'w:gz') as tar:
  for r in manifest['files']:tar.add(root/r['path'],arcname=prefix+r['path'],recursive=False)
  tar.add(mp,arcname=prefix+'manifest.json',recursive=False)
 expected={prefix+r['path']:r for r in manifest['files']};count=0
 with tarfile.open(archive,'r:gz') as tar:
  for member in tar:
   if member.name==prefix+'manifest.json':continue
   stream=tar.extractfile(member);h=hashlib.sha256()
   for b in iter(lambda:stream.read(2**20),b''):h.update(b)
   assert h.hexdigest()==expected[member.name]['sha256'] and member.size==expected[member.name]['size_bytes'];count+=1
 assert count==len(expected)
 a.nas.mkdir(exist_ok=False);dest=a.nas/archive.name;shutil.copyfile(archive,dest);assert sha(dest)==sha(archive);shutil.copyfile(mp,a.nas/mp.name)
 receipt=dict(status='PASS',archive=str(archive),NAS_archive=str(dest),sha256=sha(archive),size_bytes=archive.stat().st_size,manifest_sha256=sha(mp),verified_files=count,NAS_readback_SHA_matches=True,formal_matrix_restarts=0,main_reconstructions_this_revision=0,snapshot_solves_this_revision=0,scope='Corrected exports and source only; old evidence archives retained separately')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copyfile(out/'receipt.json',a.nas/'receipt.json');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
