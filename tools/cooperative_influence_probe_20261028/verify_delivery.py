#!/usr/bin/env python3
"""Check relocated results and unchanged execution source; no replay."""
import argparse,gzip,json
from pathlib import Path
import numpy as np
from common import ROOT,sha,dump,read

def check(art,out):
 root=art/'evidence-v1';index=json.loads((root/'RUN_INDEX.json').read_text())
 for p,s in index['source_sha256'].items():assert sha(ROOT/p)==s==sha(root/'source'/p)
 exact={}
 for n in ['metrics.csv','contrasts.csv','costs.csv','solver_controls.csv','receipt.json','audits.json']:
  a,b=art/'evaluation-v1'/n,art/'relocated-evaluation-v1'/n;assert a.read_bytes()==b.read_bytes();exact[n]=sha(a)
 with gzip.open(art/'evaluation-v1/timeline.csv.gz','rb') as a,gzip.open(art/'relocated-evaluation-v1/timeline.csv.gz','rb') as b:assert a.read()==b.read()
 controls=[]
 for s in ['nominal','car1_common_wall_bias']:
  case=s+'_seed101';j=read(root/f'reused/{case}__J/updates.jsonl.gz');u=read(root/f'runs/{case}__U/updates.jsonl.gz');d=np.array([b['pose'] for b in u[2:]])-np.array([a['pose'] for a in j[2:]])
  d[:,[2,5]]=np.arctan2(np.sin(d[:,[2,5]]),np.cos(d[:,[2,5]]));maxima=np.max(abs(d),axis=0);assert max(maxima)<1e-4
  controls.append(dict(case=case,max_abs_xy_yaw_component_difference=maxima.tolist(),same_solver_off_vs_original_within_1e_4=True))
 if out.exists():raise FileExistsError(out)
 dump(out,dict(status='PASS',source_files_unchanged=len(index['source_sha256']),relocated_identical_files=exact,timeline_decompressed_equal=True,numerical_controls=controls,estimator_runs=0,script_sha256=sha(Path(__file__))))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.artifacts,a.output)
