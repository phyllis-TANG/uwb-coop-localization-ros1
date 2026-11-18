"""Post-freeze portable packaging and A-compatible full-denominator certificates."""
import argparse,shutil
from common import *
from runtime import plans,identity
from a_bridge import make_certificate,MODE
from archive import pack

def package(results,out,evidence,freeze,stage):
 assert not out.exists();out.mkdir(parents=True);evidence.mkdir(parents=True,exist_ok=False)
 inputs=read(DOC/'INPUTS.json.gz');lock=read(DOC/'SOURCE_LOCK.json');jobs={j['id']:j for j in plans(inputs,stage)};rows=[]
 for c in inputs[stage]:
  for method in ('J5','P4','N4'):
   unit=c['id']+'_'+method;x=c['a_input'];row=dict(case_id=c['id'],mode=MODE[method],input_hash=x['input_hash'])
   if unit not in jobs:row.update(execution_status='NOT_RUN',reason='OUTSIDE_USER_AUTHORIZED_PLAN');rows.append(row);continue
   rp=results/stage/(unit+'.receipt.json')
   if not rp.exists():row.update(execution_status='NOT_RUN',reason='STAGE_STOPPED_OR_GATE_NOT_PASSED');rows.append(row);continue
   receipt=read(rp)
   if receipt['status']!='COMPLETED':row.update(execution_status='INTERRUPTED' if receipt['status']=='HARD_INTERRUPTION' else 'FAILED',reason=receipt['status']+': '+str(receipt.get('error')));rows.append(row)
   else:
    record=read(results/stage/(unit+'.result.json.gz'));cost=dict(processed_nodes=record['result']['processed'],search_seconds=str(receipt['costs']['search']),certificate_write_seconds=str(sum(receipt['costs'][k] for k in ('certificate_b','certificate_a','compressed_io'))),peak_rss_bytes=str(receipt['peak_rss_kib']*1024),distance_evaluations=record['result']['distance_evaluations'])
    cert=make_certificate(c,method,record['settings'],record['result'],record['projections'],cost=cost);name='certificates/'+unit+'.json';write(out/name,cert);row.update(execution_status='CERTIFICATE_AVAILABLE',certificate_file=name);rows.append(row)
   for suffix in ('.result.json.gz','.receipt.json','.attempt.json','.worker.json','.log'):
    p=results/stage/(unit+suffix)
    if p.exists():(out/'raw').mkdir(exist_ok=True);shutil.copyfile(p,out/'raw'/p.name)
 for name in ('RUN.json','STATUS.json','PROGRESS.json','WALL_COSTS.jsonl'):
  p=results/stage/name
  if p.exists():(out/'raw').mkdir(exist_ok=True);shutil.copyfile(p,out/'raw'/name)
 files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
 groups={}
 for name in files:
  if name.startswith('certificates/'):
   method=name.rsplit('_',1)[-1].split('.')[0];group='certificates_'+method
  elif name.endswith('.result.json.gz'):
   method=name.removesuffix('.result.json.gz').rsplit('_',1)[-1];group='raw_'+method
  else:group='metadata'
  groups.setdefault(group,[]).append(out/name)
 archives={}
 for group,paths in groups.items():
  # Keep individual Git archive blobs below 40 MiB using uncompressed source sizes.
  chunk=[];size=0;idx=0
  for path in paths:
   if chunk and size+path.stat().st_size>35*1024**2:
    name=f'{stage}_{group}_{idx:02d}.tar.gz';archives[name]=pack(chunk,out,evidence/name);chunk=[];size=0;idx+=1
   chunk.append(path);size+=path.stat().st_size
  if chunk:
   name=f'{stage}_{group}_{idx:02d}.tar.gz';archives[name]=pack(chunk,out,evidence/name)
 manifest=dict(schema_version='DUAL-A-V1',stage='deterministic' if stage=='deterministic' else 'conditional_random',source_commit=freeze,a_frozen_sha=lock['a_sha'],run_frozen_sha=freeze,files=files,archive_hash=digest(files),records=rows,archives=archives,authorized_plan=len(jobs),compatibility_records=len(rows),completed_authorized=sum(r['execution_status']=='CERTIFICATE_AVAILABLE' for r in rows),status='RESULTS_PACKAGED_PENDING_SOURCE_COMMIT')
 write(out/'RESULTS_READY.json',manifest);write(evidence/'MANIFEST.json',manifest)
 print(json.dumps(dict(files=len(files),archives=len(archives),bytes=sum(a['bytes'] for a in archives.values()),certified=manifest['completed_authorized'],compatibility_records=len(rows))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--freeze',required=True);p.add_argument('--stage',required=True);a=p.parse_args();package(a.results,a.out,a.evidence,a.freeze,a.stage)
