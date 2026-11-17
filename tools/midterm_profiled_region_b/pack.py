"""Portable byte-preserving archives; added after freeze, no execution changes."""
import argparse,tarfile,time,collections
from common import *
def pack(src,out):
 out.mkdir(parents=True,exist_ok=False);start=time.perf_counter();groups=collections.defaultdict(list);files={}
 for stage in ['deterministic','random']:
  cases=read(DOC/'INPUTS.json.gz')[stage];lookup={c['id']:c for c in cases}
  for f in sorted((src/stage).iterdir()):
   if not f.is_file() or f.name=='LOCK':continue
   key='deterministic' if stage=='deterministic' else 'random_metadata'
   case=f.name.split('_')[0]
   if stage=='random' and case in lookup:key='random_'+lookup[case]['condition'].replace('.','p')
   groups[key].append((f,Path(stage)/f.name));files[str(Path(stage)/f.name)]=sha(f)
 archives={}
 for key,items in sorted(groups.items()):
  name=key+'.tar.gz';dest=out/name
  with tarfile.open(dest,'w:gz',compresslevel=6) as t:
   for f,path in items:t.add(f,arcname=str(path),recursive=False)
  archives[name]=dict(sha256=sha(dest),bytes=dest.stat().st_size,files=len(items))
 write(out/'MANIFEST.json',dict(archives=archives,files=files,pack_seconds=time.perf_counter()-start,random_phase_elapsed_until_archive=time.time()-read(src/'random'/'RUN.json')['start_epoch']))
 return dict(archives=len(archives),bytes=sum(a['bytes'] for a in archives.values()),pack_seconds=time.perf_counter()-start)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(pack(a.results,a.out)))
