#!/usr/bin/env python3
"""Archive new diagnosis evidence, verify every member, optionally copy to NAS.
References the original immutable 293 MB archive rather than duplicating it.
"""
import argparse,hashlib,json,shutil,tarfile
from pathlib import Path
from verify_evidence import sha

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--artifacts',type=Path,required=True);ap.add_argument('--nas',type=Path);a=ap.parse_args();root=a.artifacts;out=root/'archives';out.mkdir(exist_ok=False);source=root/'executed-source';source.mkdir(exist_ok=False)
 for p in Path(__file__).parent.glob('*.py'):shutil.copyfile(p,source/p.name)
 paths=[]
 for name in ('log-analysis-v6','interventions-v1','mechanics-v1','executed-source'):
  paths.extend(p for p in (root/name).rglob('*') if p.is_file())
 paths.extend(p for p in root.iterdir() if p.is_file() and (p.suffix in ('.log','.json') or p.name=='COMMANDS.md'))
 manifest=dict(schema_version=1,original_archive_sha256='7a5ff137f2f7fb250ebda466e163f94d137d59f660b48eb4f9150847bbdc3ab8',files=[dict(path=str(p.relative_to(root)),size_bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(paths))]);mp=out/'archive-input-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');archive=out/'quality_fgo_diagnosis_20261027_evidence.tar.gz';prefix='quality_fgo_diagnosis_20261027/'
 with tarfile.open(archive,'w:gz') as t:
  for r in manifest['files']:t.add(root/r['path'],arcname=prefix+r['path'],recursive=False)
  t.add(mp,arcname=prefix+'archive-input-manifest.json',recursive=False)
 expected={prefix+r['path']:r for r in manifest['files']};count=0
 with tarfile.open(archive,'r:gz') as t:
  for m in t:
   if m.name==prefix+'archive-input-manifest.json':continue
   h=hashlib.sha256();f=t.extractfile(m)
   for b in iter(lambda:f.read(2**20),b''):h.update(b)
   assert h.hexdigest()==expected[m.name]['sha256'] and m.size==expected[m.name]['size_bytes'];count+=1
 assert count==len(expected)
 receipt=dict(status='PASS',archive=str(archive),sha256=sha(archive),size_bytes=archive.stat().st_size,evidence_files_verified=count,manifest_sha256=sha(mp),original_archive_sha256=manifest['original_archive_sha256'],original_formal_matrix_restarts=0,diagnostic_main_reconstructions=6,diagnostic_snapshot_solves=28)
 if a.nas:
  a.nas.mkdir(exist_ok=False);dest=a.nas/archive.name;shutil.copyfile(archive,dest);assert sha(dest)==receipt['sha256'];shutil.copyfile(mp,a.nas/mp.name);receipt.update(NAS_archive=str(dest),NAS_readback_sha256=sha(dest),access='Existing authorized SMB mount //10.22.5.135/data; LAN/VPN; not public HTTP')
 (out/'archive.json').write_text(json.dumps(receipt,indent=2)+'\n')
 if a.nas:shutil.copyfile(out/'archive.json',a.nas/'archive.json')
 print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
