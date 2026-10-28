#!/usr/bin/env python3
"""Immutable evidence archive; no estimator calls, no remote upload."""
import argparse,json,shutil,tarfile
from pathlib import Path
from common import ROOT,HERE,sha,dump,state
DOC=Path('docs/field_tests/20261024_25/cooperative_dcs_probe_20261028')
def pack(art,out):
    if state()['dirty']:raise ValueError('commit delivery source before packing')
    out.mkdir(exist_ok=False);delivery=art/'delivery-source-v1';delivery.mkdir(exist_ok=False)
    shutil.copytree(art/'evidence-v1/source',delivery,dirs_exist_ok=True)
    # Preserve execution snapshot separately; overlay only in delivery reader tree.
    shutil.copytree(HERE,delivery/'tools'/HERE.name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT/DOC,delivery/DOC)
    dump(delivery/'DELIVERY_SOURCE.json',state())
    selected=['evidence-v1','evaluation-v1','evaluation-v1.log','presentation-v1','tests-v1','tests-v2','tests-v3','solver-source','literature','delivery-source-v1']
    files=[]
    for name in selected:
        p=art/name;files.extend([p] if p.is_file() else sorted(x for x in p.rglob('*') if x.is_file()))
    assert len(files)==len(set(files))
    manifest={'files':{str(p.relative_to(art)):{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in files},'execution_commit':'19f1bbaa42d6631cc3c2d8660953d13a17ae76de','delivery_source_commit':state()['code_commit']}
    dump(out/'MANIFEST.json',manifest)
    archive=out/'cooperative_dcs_probe_20261028_ca8fbac4_v1.tar.gz';prefix='cooperative_dcs_probe_20261028'
    with tarfile.open(archive,'x:gz') as t:
        for p in files:t.add(p,arcname=prefix+'/'+str(p.relative_to(art)),recursive=False)
        t.add(out/'MANIFEST.json',arcname=prefix+'/MANIFEST.json',recursive=False)
    dump(out/'ARCHIVE.json',dict(archive=str(archive),sha256=sha(archive),size_bytes=archive.stat().st_size,manifest_sha256=sha(out/'MANIFEST.json'),files=len(files),extraction_prefix=prefix,**state()))
    print(json.dumps(json.loads((out/'ARCHIVE.json').read_text()),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();pack(a.artifacts,a.output)
