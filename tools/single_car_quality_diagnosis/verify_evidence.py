#!/usr/bin/env python3
"""Read-only verification of immutable archive and reused original evidence."""
import argparse,hashlib,json,subprocess,tarfile
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--original',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 archive=a.original/'archives/single_car_quality_fgo_v1_evidence_20261027.tar.gz'
 expected='7a5ff137f2f7fb250ebda466e163f94d137d59f660b48eb4f9150847bbdc3ab8'
 assert sha(archive)==expected
 manifest=a.original/'archive-input-manifest.json';assert sha(manifest)=='1d24a1fcb887b00aec65b9c920da367b684a17ea7ed2b87583b829449105dbd5'
 rows=json.loads(manifest.read_text())['files'];index={r['path']:r for r in rows};checked=0;reuse=[]
 with tarfile.open(archive,'r:gz') as t:
  for m in t:
   if not m.isfile():continue
   name=m.name.removeprefix('single_car_quality_fgo_v1/')
   if name=='archive-input-manifest.json':continue
   r=index[name];h=hashlib.sha256();f=t.extractfile(m)
   for b in iter(lambda:f.read(2**20),b''):h.update(b)
   assert h.hexdigest()==r['sha256'] and m.size==r['size_bytes'],name;checked+=1
 assert checked==len(rows)==2138
 for r in rows:
  if r['path'].startswith('validation-v1/'):
   p=a.original/r['path'];assert p.stat().st_size==r['size_bytes'] and sha(p)==r['sha256'],str(p);reuse.append(r)
 root=a.original/'validation-v1';cp=json.loads((root/'checkpoint.json').read_text());assert len(cp['cells'])==96 and all(c['status']=='DONE' for c in cp['cells'])
 configs=[]
 for c in cp['cells']:
  run=root/c['output'];j=json.loads((run/'run.json').read_text());assert j['code_commit']=='12a1d94379b58c5a759b1698425fb90d48587609'
  for p,s in j['source_sha256'].items():
   assert sha(root/'source'/p)==s,p
   blob=subprocess.check_output(['git','show',j['code_commit']+':'+p]);assert hashlib.sha256(blob).hexdigest()==s,p
  assert sha(run/'config.json')==j['config_sha256']
  configs.append(dict(cell_id=c['cell_id'],input_sha256=j['input_sha256'],config_sha256=j['config_sha256'],source_sha256=j['source_sha256'],original_argv=j['command_argv']))
 result=dict(status='PASS',archive=str(archive),archive_sha256=expected,manifest_sha256=sha(manifest),archive_files_verified=checked,reused_validation_files_verified=len(reuse),runs_verified=96,protocol_sha256=sha(root/'protocol.json'),estimator_reruns=0,reused_files=reuse,runs=configs)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('reused_files','runs')}))
if __name__=='__main__':main()
