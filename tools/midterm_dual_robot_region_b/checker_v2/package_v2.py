"""Portable v2 results archive; original PR133 evidence stays in its old location."""
import argparse,hashlib,json,tarfile,sys,tempfile,shutil
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import read,write,sha,DOC,ROOT

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);args=ap.parse_args();dest=DOC/'checker_v2/evidence';dest.mkdir(exist_ok=True);members={};archives={}
 # Per-stage raw output includes attempts, jobs, receipts, certificates and wall ledgers.
 for stage in ['deterministic','deterministic_readback','random','random_readback']:
  folder=args.root/stage
  if not folder.exists():continue
  paths=[p for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='LOCK'];name=stage+'.tar.gz';mapping={}
  with tarfile.open(dest/name,'w:gz') as tar:
   for p in paths:
    rel=str(p.relative_to(args.root));mapping[rel]=sha(p);members[rel]=mapping[rel];tar.add(p,arcname=rel,recursive=False)
  archives[name]=dict(sha256=sha(dest/name),bytes=(dest/name).stat().st_size,files=mapping)
 # Include the fixed A source runtime and ready receipt; B source is carried by Git freeze.
 lock=read(DOC/'checker_v2/A_SOURCE_LOCK.json');root=Path(lock['source_root']);name='a_locked_source.tar.gz';mapping={}
 with tarfile.open(dest/name,'w:gz') as tar:
  for path,h in lock['files'].items():
   p=root/path;assert sha(p)==h;rel='a_source/'+path;mapping[rel]=h;members[rel]=h;tar.add(p,arcname=rel,recursive=False)
 archives[name]=dict(sha256=sha(dest/name),bytes=(dest/name).stat().st_size,files=mapping)
 name='delivery_metadata.tar.gz';mapping={}
 with tarfile.open(dest/name,'w:gz') as tar:
  inp=DOC/'INPUTS.json.gz';rel='metadata/INPUTS.json.gz';mapping[rel]=sha(inp);members[rel]=mapping[rel];tar.add(inp,arcname=rel,recursive=False)
  for p in sorted((DOC/'checker_v2').rglob('*')):
   if not p.is_file() or 'evidence' in p.relative_to(DOC/'checker_v2').parts or p.name in ['SHA256SUMS','PORTABLE_READBACK.json','PORTABLE_SEMANTIC_READBACK.json']:continue
   rel='metadata/'+str(p.relative_to(DOC/'checker_v2'));mapping[rel]=sha(p);members[rel]=mapping[rel];tar.add(p,arcname=rel,recursive=False)
 archives[name]=dict(sha256=sha(dest/name),bytes=(dest/name).stat().st_size,files=mapping)
 manifest=dict(archives=archives,files=members,freeze_sha=read(DOC/'checker_v2/FREEZE.json')['freeze_sha'],a_sha=lock['a_sha']);write(dest/'MANIFEST.json',manifest)
 # Actually unpack every member and re-hash it, not merely trust tar indexes.
 with tempfile.TemporaryDirectory(dir=args.root) as td:
  out=Path(td);seen={}
  for name,meta in archives.items():
   assert sha(dest/name)==meta['sha256']
   with tarfile.open(dest/name) as tar:
    for member in tar:
     p=Path(member.name);assert member.isfile() and not p.is_absolute() and '..' not in p.parts and member.name not in seen;target=out/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(tar.extractfile(member).read());seen[member.name]=sha(target);assert seen[member.name]==meta['files'][member.name]
  assert seen==members
 write(DOC/'checker_v2/PORTABLE_READBACK.json',dict(status='PASS',archives=len(archives),files=len(members),actual_unpack=True,search_calls=0));print('Portable unpack/hash check',len(archives),'archives',len(members),'files')
if __name__=='__main__':main()
