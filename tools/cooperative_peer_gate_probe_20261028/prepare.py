#!/usr/bin/env python3
"""Read-only old-evidence verification and the sole new input adapter."""
import argparse,copy,gzip,hashlib,json,shutil,tarfile
from pathlib import Path
from pinned import MANIFEST,ROOT,simulate
from records import sha,dump,read,write_gzip
SEEDS=(101,211,307)
SCENARIOS=('nominal','peer_bias','wall_bias','peer_gap','car1_common_wall_bias')

def verify_old(old):
 meta=json.loads((old/'ARCHIVE.json').read_text());archive=old/meta['archive_filename'];assert sha(archive)==meta['archive_sha256'];pkg=json.loads((old/'PACKAGE_MANIFEST.json').read_text());assert sha(old/'PACKAGE_MANIFEST.json')==meta['package_manifest_sha256'];expected={r['relative_path']:r for r in pkg['files']};verified=0
 with tarfile.open(archive,'r:gz') as tar:
  for m in tar:
   if not m.isfile() or m.name not in expected:continue
   h=hashlib.sha256();stream=tar.extractfile(m)
   for b in iter(lambda:stream.read(2**20),b''):h.update(b)
   assert h.hexdigest()==expected[m.name]['sha256'] and m.size==expected[m.name]['size_bytes'];verified+=1
 assert verified==len(expected)
 matrix=json.loads((old/'formal-v1/matrix.json').read_text());assert matrix['status']=='DONE' and len(matrix['cells'])==24
 assert matrix['source_sha256']==MANIFEST['files']
 for p,s in MANIFEST['files'].items():assert sha(ROOT/p)==s
 cells=[]
 for c in matrix['cells']:
  root=old/'formal-v1';run=root/c['run_relative_path'];inp=root/c['input_relative_path'];assert c['status']=='DONE';assert sha(run/'run.json')==c['run_manifest_sha256'];r=json.loads((run/'run.json').read_text());assert r['status']=='DONE' and r['source_sha256']==MANIFEST['files'];assert sha(inp/'events.jsonl.gz')==c['events_sha256'];assert sha(inp/'config.json')==c['config_sha256']==r['config_sha256'];assert r['inputs'][0]['sha256']==c['events_sha256']
  for o in r['outputs']:assert sha(run/o['relative_path'])==o['sha256'] and (run/o['relative_path']).stat().st_size==o['size_bytes']
  im=json.loads((inp/'input_manifest.json').read_text())
  for name,s in im['files'].items():assert sha(inp/name)==s
  cells.append(dict(c,method='G0' if c['arm']=='D0' else 'G1',original_run=str(run),original_input=str(inp),original_source_sha256=r['source_sha256']))
 return dict(status='PASS',archive_sha256=meta['archive_sha256'],archive_files_verified=verified,source_SHA_matches=19,reusable_cells=24,cells=cells)

def prepare(old,output):
 output.mkdir(exist_ok=False);proof=verify_old(old);dump(output.parent/'reuse_evidence.json',proof);index=[]
 for seed in SEEDS:
  for sc in SCENARIOS:
   path=output/f'{sc}_seed{seed}';path.mkdir(exist_ok=False);base=old/'formal-v1/inputs'/f'{sc if sc!=SCENARIOS[-1] else "nominal"}_seed{seed}'
   for name in ('config.json','events.jsonl.gz','truth.jsonl','labels.json','input_manifest.json'):shutil.copyfile(base/name,path/name)
   note=dict(kind='unmodified_original_generator_input',original_manifest_SHA=sha(base/'input_manifest.json'))
   if sc==SCENARIOS[-1]:
    rows=list(read(base/'events.jsonl.gz'));original=copy.deepcopy(rows);modified=0
    for row in rows:
     if row['kind']=='uwb' and row['vehicle_id']=='car1' and 24_000_000_000<=row['header_epoch_ns']-simulate.EPOCH_NS<38_000_000_000:
      for key in ('node_10','node_2','node_3','node_8'):row['value'][key]+=.30;modified+=1
    # Write deterministic actual bytes to a new file, never touch the old evidence.
    with (path/'events.jsonl.gz').open('wb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z:z.write(('\n'.join(simulate.canonical(r) for r in rows)+'\n').encode())
    for x,y in zip(original,rows):
     for k,v in x.items():
      if k!='value':assert y[k]==v
     for k,v in (x['value'].items()):
      target=x['kind']=='uwb' and x.get('vehicle_id')=='car1' and k in ('node_10','node_2','node_3','node_8') and 24_000_000_000<=x.get('header_epoch_ns',0)-simulate.EPOCH_NS<38_000_000_000
      if target:assert abs(y['value'][k]-v-.30)<1e-15
      else:assert y['value'][k]==v
    assert modified==1120
    labels=json.loads((base/'labels.json').read_text());labels.update(scenario=sc,fault=dict(interval_s=[24.,38.],interval_convention='left_closed_right_open',kind=sc,affected_stream='car1/four_walls_only',additive_bias_m=.30),adapter=dict(source_nominal_events_sha256=sha(base/'events.jsonl.gz'),source_recipe_and_message_ids_retained=True,actual_adapted_file_sha256=sha(path/'events.jsonl.gz'),modified_wall_scalars=modified));dump(path/'labels.json',labels)
    note=dict(kind='sole_input_adapter',base_nominal_SHA=sha(base/'events.jsonl.gz'),adapter_source_SHA=sha(Path(__file__)),modified_wall_scalars=modified,all_other_scalars_and_metadata_exact_equal=True)
    dump(path/'input_manifest.json',dict(schema_version=1,scenario=sc,seed=seed,adapter=note,files={n:sha(path/n) for n in ('config.json','events.jsonl.gz','truth.jsonl','labels.json')},labels_are_estimator_inputs=False))
   index.append(dict(scenario=sc,seed=seed,path=str(path),files={n:sha(path/n) for n in ('config.json','events.jsonl.gz','truth.jsonl','labels.json','input_manifest.json')},adapter=note))
 dump(output.parent/'input_index.json',dict(status='FROZEN_INPUTS',cases=index,frozen_algorithm_commit=MANIFEST['commit']))
 print('PASS: 24 reusable cells, 15 input cases; sole adapter verified 1120 wall scalars/seed')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--old',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();prepare(a.old,a.output)
if __name__=='__main__':main()
