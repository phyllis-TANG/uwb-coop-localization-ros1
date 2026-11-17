"""Source byte hashes and complete identities before coverage; no optimization."""
import argparse,collections,hashlib,json,subprocess
from common import *
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 try:
  manifest=json.loads((ROOT/'docs/research/midterm_mismatch_b/SHA256SUMS.json').read_text())['files']
  previous=json.loads((ROOT/'docs/research/midterm_uncertainty_a/SHA256SUMS.json').read_text())
  for file,h in {**manifest,**previous}.items():assert sha(ROOT/file)==h,file
  report=dict(base=CFG['source_sha'],B_delivery_files_checked=len(manifest),A_delivery_files_checked=len(previous),noise_handoff_and_hashes='Parent HANDOFF.md and SHA256SUMS.json cover both batches; no separate noise files',batches={})
  for batch,spec in CFG['batches'].items():
   directory=ROOT/spec['directory'];frozen=json.loads((directory/'FREEZE_MANIFEST.json').read_text());changes=[]
   for file,h in frozen['files'].items():
    raw=subprocess.check_output(['git','show',spec['freeze']+':'+file],cwd=ROOT);assert hashlib.sha256(raw).hexdigest()==h,(batch,file)
    if sha(ROOT/file)!=h:changes.append(file)
   seen=set();inputs=set();cats=collections.Counter();sizes=collections.Counter();meta_hash=None;shards={}
   for p in sorted((directory/'results').glob('EVIDENCE-*.jsonl.gz')):
    meta,units,records=read_shard(p);h=digest(meta);assert meta_hash in [None,h];meta_hash=h
    assert meta['frozen_commit']==spec['freeze'] and digest(meta['config'])==meta['config_sha256']==frozen['config_sha256']
    assert digest(meta['config'])==digest(json.loads((directory/'CONFIG.json').read_text()))
    assert digest(meta['plan'])==meta['plan_sha256']
    for file,h in meta['sources'].items():assert sha(ROOT/file)==h,file
    for key,u in units.items():assert key not in inputs;inputs.add(key);assert digest(u['obs'])==u['input_sha256']
    for r in records:
     key=(r['unit'],r['method']);assert key not in seen;seen.add(key);assert digest(units[r['unit']])==r['input_sha256'];assert set(r['stages'])=={'P0','P1'} and all(s is not None for s in r['stages'].values())
     s=r['stages']['P1'];cats[s['category']]+=1;sizes[units[r['unit']]['condition']['id'],r['method']]+=1
    shards[p.name]=sha(p)
   expected={(p['id'],m) for p in meta['plan'] for m in METHODS};assert seen==expected
   assert inputs=={p['id'] for p in meta['plan']} and len(seen)==spec['methods'] and dict(cats)==spec['categories']
   assert len(sizes)==72*4 and set(sizes.values())=={spec['seeds']}
   report['batches'][batch]=dict(inputs=len(inputs),methods=len(seen),categories=dict(cats),freeze=spec['freeze'],config_sha256=meta['config_sha256'],plan_sha256=meta['plan_sha256'],sources=meta['sources'],shards=shards,freeze_files_checked=len(frozen['files']),post_freeze_document_changes=changes)
  report['passed']=True;write_json(a.out/'SOURCE_CHECKS.json',report);print(json.dumps({k:v for k,v in report.items() if k!='batches'},ensure_ascii=False))
 except Exception as ex:write_json(a.out/'SOURCE_FAILURE.json',dict(error=repr(ex)));raise
if __name__=='__main__':main()
