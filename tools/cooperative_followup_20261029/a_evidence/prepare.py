#!/usr/bin/env python3
"""Verify fixed public revision and copy/read existing NAS archive once."""
import argparse,json,shutil,tarfile,hashlib
from pathlib import Path
from io_evidence import *
NAS=Path('/home/ubuntu22/nas/data/uwb_coop_artifacts/cooperative_influence_probe_20261028_v1/cooperative_influence_probe_20261028_v1.tar.gz')
ARCHIVE_SHA='50c671e3687c3342b8abe99986ecd6a6488de23e24fe112b16b44d9f8fb3f320'
def prepare(out,archive_source=NAS):
 out.mkdir(exist_ok=False);public=out/'public_snapshot';public.mkdir();pubsha={}
 names=['REPORT.md','METHODS.md','FROZEN_CONFIG.json','HANDOFF.md','ARTIFACTS.json','RUN_INDEX.json','RUN_PLAN.json','INPUT_BINDINGS.json','results/metrics.csv','results/contrasts.csv','results/costs.csv','results/solver_controls.csv','results/receipt.json','results/audits.json','review/DELIVERY_FILES_SHA256.json']
 for n in names:
  b=show(DOC+'/'+n);p=public/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);pubsha[n]=sha(p)
 index=json.loads((public/'RUN_INDEX.json').read_text());expected={s+'_seed101__'+m for s in SCENARIOS for m in ['I','J','W025','U','C004','C100','K004','K100']}
 assert index['status']=='DONE' and index['commit']==EXEC and len(index['cells'])==16 and {r['id'] for r in index['cells']}==expected
 for c in index['cells']:assert c['status']==('REUSED_VERIFIED' if c['kind']=='reuse' else 'DONE')
 inv=json.loads((public/'review/DELIVERY_FILES_SHA256.json').read_text())['files']
 for n in names:
  if n=='review/DELIVERY_FILES_SHA256.json':continue
  assert pubsha[n]==inv[DOC+'/'+n]['sha256']
 costs=table(public/'results/costs.csv');assert len(costs)==16 and sum(int(r['denominator']) for r in costs)==1008
 public_receipt=dict(status='PASS',fixed_HEAD=HEAD,execution_commit=EXEC,source_file_sha256=pubsha,logical_cells=16,random_seeds=1,paired_conditions=2,
  rows={n:len(table(public/'results'/n)) for n in ['metrics.csv','contrasts.csv','costs.csv','solver_controls.csv']},denominator_totals={k:sum(int(r[k]) for r in costs) for k in ['denominator','finite','reference_accepted','joint_success','post_clip','fallback','unknown','failure','timeout']},estimator_runs=0)
 dump(out/'PUBLIC_CHECK.json',public_receipt)
 # A missing mount ends at the public check, with an accurate blocker.
 if not archive_source.is_file():dump(out/'ARCHIVE_CHECK.json',dict(status='BLOCKED',reason='Archive source path unavailable',path=str(archive_source)));return
 archive=out/archive_source.name;shutil.copyfile(archive_source,archive);assert archive.stat().st_size==54249275 and sha(archive)==ARCHIVE_SHA
 a=json.loads((public/'ARTIFACTS.json').read_text())['archive'];prefix=a['prefix'];destination=out/'unpacked';destination.mkdir()
 with tarfile.open(archive,'r:gz') as tf:
  manifest_bytes=tf.extractfile(prefix+'/MANIFEST.json').read();assert hashlib.sha256(manifest_bytes).hexdigest()==a['manifest_sha256'];manifest=json.loads(manifest_bytes)
  members=tf.getmembers();assert len(members)==len(manifest['files'])+1
  for m in members:
   assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
   rel=str(Path(m.name).relative_to(prefix));data=tf.extractfile(m).read()
   if rel!='MANIFEST.json':assert hashlib.sha256(data).hexdigest()==manifest['files'][rel]['sha256'] and len(data)==manifest['files'][rel]['size_bytes']
   p=destination/m.name;p.parent.mkdir(parents=True,exist_ok=True)
   with p.open('xb') as f:f.write(data)
 root=destination/prefix;matrix=root/'evidence-v1';assert sha(matrix/'RUN_INDEX.json')==pubsha['RUN_INDEX.json']
 for n in ['metrics.csv','contrasts.csv','costs.csv','solver_controls.csv','receipt.json','audits.json']:assert sha(root/'evaluation-v1'/n)==pubsha['results/'+n]
 for p,h in index['source_sha256'].items():assert sha(matrix/'source'/p)==h
 for c in index['cells']:
  run=matrix/c['path'];assert sha(run/'run.json')==c['run_sha256'];meta=json.loads((run/'run.json').read_text());outputs=meta['outputs'];outputs=[dict(path=k,**v) for k,v in outputs.items()] if isinstance(outputs,dict) else outputs
  for p in outputs:assert sha(run/p['path'])==p['sha256']
  for p,h in c['input_sha256'].items():assert sha(matrix/'inputs'/c['case']/p)==h
 dump(out/'ARCHIVE_CHECK.json',dict(status='PASS',NAS_path=str(archive_source),archive_path=str(archive),sha256=sha(archive),size_bytes=archive.stat().st_size,verified_members=len(manifest['files']),matrix_root=str(matrix),public_all_results_byte_equal=True,execution_source_sha256=index['source_sha256'],inputs={c['case']:c['input_sha256'] for c in index['cells']},estimator_runs=0))
 print('PASS public 16 cells, archive 239 members, source/input/run/result identities; no estimator execution')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ART/'evidence-v1');p.add_argument('--archive',type=Path,default=NAS);a=p.parse_args();prepare(a.output,a.archive)
