#!/usr/bin/env python3
"""Immutable archive of evidence plus standalone independent reader tree."""
import argparse,json,shutil,tarfile
from pathlib import Path
from common import ROOT,HERE,ART,sha,dump,state
DOC=Path('docs/field_tests/20261024_25/cooperative_influence_probe_20261028')
def pack(out):
 if state()['dirty']:raise ValueError('Commit delivery source first')
 out.mkdir(exist_ok=False);delivery=ART/'delivery-source-v1';shutil.copytree(ART/'evidence-v1/source',delivery)
 shutil.copytree(HERE,delivery/'tools'/HERE.name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 shutil.copytree(ROOT/DOC,delivery/DOC);dump(delivery/'DELIVERY_SOURCE.json',state())
 names=['evidence-v1','evaluation-v1','evaluation-v1.log','presentation-v1','tests-v1','tests-v2','tests-v3','development-v1.log','during_run_editorial_status.json','environment.json','delivery-source-v1']
 files=[]
 for name in names:
  p=ART/name;files.extend([p] if p.is_file() else sorted(q for q in p.rglob('*') if q.is_file()))
 manifest=dict(files={str(p.relative_to(ART)):dict(sha256=sha(p),size_bytes=p.stat().st_size) for p in files},execution_commit='312180ef51c6ea4ba394bc85618674ec36ff786d',delivery_source_commit=state()['commit'])
 dump(out/'MANIFEST.json',manifest);archive=out/'cooperative_influence_probe_20261028_v1.tar.gz';prefix='cooperative_influence_probe_20261028'
 with tarfile.open(archive,'x:gz') as tf:
  for p in files:tf.add(p,arcname=prefix+'/'+str(p.relative_to(ART)),recursive=False)
  tf.add(out/'MANIFEST.json',arcname=prefix+'/MANIFEST.json',recursive=False)
 receipt=dict(archive=str(archive),sha256=sha(archive),size_bytes=archive.stat().st_size,manifest_sha256=sha(out/'MANIFEST.json'),files=len(files),prefix=prefix,**state())
 dump(out/'ARCHIVE.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ART/'archives-v1');pack(p.parse_args().output)
