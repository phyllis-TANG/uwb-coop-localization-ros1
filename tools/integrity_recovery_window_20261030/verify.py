"""Extend independent PR81 reader's time-index domain, not numerical tolerances."""
import sys,json,gzip
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'docs/research/integrity_recovery_window_20261030'
sys.path.insert(0,str(ROOT/'tools/cooperative_integrity_baselines_20261029'))
import independent as reader
old_keys=reader.noise_keys()
new_keys=[]
for car in ('car1','car2'):
 new_keys += [f'odom|{car}|{t}|{t+1}|{i}' for t in range(63,89) for i in range(3)]
 new_keys += [f'wall|{car}|{t}|{key}' for t in range(64,90) for key in ('node_10','node_2','node_3','node_8')]
new_keys += [f'peer|{t}' for t in range(64,90)]
keys=old_keys+new_keys;assert len(keys)==len(set(keys))
reader.noise_keys=lambda:keys
for condition in ('nominal','wall_long'):
 folder=OUT/condition
 rows=[json.loads(l) for l in gzip.open(folder/'monitor.jsonl.gz','rt')]
 # Earlier saved evidence uses original columns. Append mathematically zero
 # future-source columns for this read-only full-horizon verification.
 for row in rows:
  for e in (row.get('linear_evidence') or {}).values():
   for field in ('prior_b','k'):
    e[field]=np.pad(np.asarray(e[field]),((0,0),(0,len(keys)-len(e[field][0])))).tolist()
 result=reader.verify(rows,json.loads((folder/'config.json').read_text()))
 result['extension']='only primitive naming domain and zero-padding earlier saved evidence; same original Schur/FD/score tolerances'
 with (folder/'INDEPENDENT.json').open('x') as f:json.dump(result,f,indent=2)
 print(condition,result,flush=True)
