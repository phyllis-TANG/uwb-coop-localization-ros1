#!/usr/bin/env python3
"""Immutable complete task archive plus verified old reuse archive, no overwrite."""
import argparse,hashlib,json,shutil,tarfile
from pathlib import Path
SKIP={'archives-v1','retrieved-v1','retrieved-readback-v1','mpl-cache','tmp'}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--artifacts',type=Path,required=True);ap.add_argument('--old',type=Path,required=True);ap.add_argument('--nas',type=Path,required=True);a=ap.parse_args();root=a.artifacts
 source=root/'delivery-source';source.mkdir(exist_ok=False)
 for p in Path(__file__).parent.iterdir():
  if p.suffix in ('.py','.json','.md'):shutil.copyfile(p,source/p.name)
 oldmeta=root/'reused-original-manifests';oldmeta.mkdir(exist_ok=False);reuse=json.loads((root/'reuse_evidence.json').read_text())
 for c in reuse['cells']:
  p=Path(c['original_run'])/'run.json';assert sha(p)==c['run_manifest_sha256'];shutil.copyfile(p,oldmeta/(Path(c['original_run']).name+'.json'))
 files=[p for p in sorted(root.rglob('*')) if p.is_file() and not set(p.relative_to(root).parts)&SKIP and p.name!='archive-v1.log']
 out=root/'archives-v1';out.mkdir(exist_ok=False);manifest=dict(files=[dict(path=str(p.relative_to(root)),size_bytes=p.stat().st_size,sha256=sha(p)) for p in files]);mp=out/'manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');archive=out/'cooperative_peer_gate_probe_20261028_74fa210e.tar.gz';prefix='cooperative_peer_gate_probe_20261028/'
 with tarfile.open(archive,'w:gz') as tar:
  for r in manifest['files']:tar.add(root/r['path'],arcname=prefix+r['path'],recursive=False)
  tar.add(mp,arcname=prefix+'manifest.json',recursive=False)
 expected={prefix+r['path']:r for r in manifest['files']};count=0
 with tarfile.open(archive,'r:gz') as tar:
  for m in tar:
   if m.name==prefix+'manifest.json':continue
   h=hashlib.sha256();f=tar.extractfile(m)
   for b in iter(lambda:f.read(2**20),b''):h.update(b)
   assert h.hexdigest()==expected[m.name]['sha256'] and m.size==expected[m.name]['size_bytes'];count+=1
 assert count==len(expected)
 original=a.old/'two-car-fixed-lag-fgo-v1-1595c98.tar.gz';original_sha='0e0156d75374cbe8e2180ef0eb36a7f282b5c59c842b6392d1ae4ae1956c8f8b';assert sha(original)==original_sha
 a.nas.mkdir(exist_ok=False);remote=a.nas/archive.name;shutil.copyfile(archive,remote);assert sha(remote)==sha(archive);shutil.copyfile(mp,a.nas/mp.name);oldremote=a.nas/original.name;shutil.copyfile(original,oldremote);assert sha(oldremote)==original_sha
 receipt=dict(status='PASS',archive=str(archive),NAS_archive=str(remote),size_bytes=archive.stat().st_size,sha256=sha(archive),manifest_sha256=sha(mp),verified_files=count,old_reuse_archive=dict(local=str(original),NAS_archive=str(oldremote),sha256=original_sha,size_bytes=original.stat().st_size),NAS_full_readback_SHA_matches=True,access='Existing authorized SMB //10.22.5.135/data; LAN/VPN; not a public HTTP URL',archive_scope='Frozen source, original/copied/adapted synthetic inputs, all 45 normalized outputs, all failures/tests, independent v1/v2 evaluations and compact figures; original reuse archive separately retained')
 (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');shutil.copyfile(out/'receipt.json',a.nas/'receipt.json');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
