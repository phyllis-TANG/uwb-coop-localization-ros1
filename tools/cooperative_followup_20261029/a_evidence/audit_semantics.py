#!/usr/bin/env python3
"""Read original solver-control yaw and stored virtual-publication semantics."""
import argparse,json
from pathlib import Path
import numpy as np
from io_evidence import read,csvwrite,dump,sha,SCENARIOS,METHODS
from signals import wrap

def run(evidence,out):
 out.mkdir(exist_ok=False);root=Path(json.loads((evidence/'ARCHIVE_CHECK.json').read_text())['matrix_root']);index=json.loads((root/'RUN_INDEX.json').read_text());runs={}
 manifest=[]
 for cell in index['cells']:
  path=root/cell['path'];runmeta=json.loads((path/'run.json').read_text());runs[cell['case'].removesuffix('_seed101'),cell['method']]=read(path/'updates.jsonl.gz')
  manifest.append(dict(case=cell['case'],method=cell['method'],publication_sink='updates.jsonl.gz:pose (offline virtual publication)',separate_published_csv=(path/'published.csv').exists(),updates_sha256=sha(path/'updates.jsonl.gz'),run_sha256=sha(path/'run.json')))
 results=[]
 for s in SCENARIOS:
  for car,i in [('car1',2),('car2',5)]:
   for a,b in [('U','J'),('K004','C004')]:
    aa,bb=runs[s,a][2:],runs[s,b][2:];assert len(aa)==len(bb)==61
    differences=[wrap(x['pose'][i]-y['pose'][i]) for x,y in zip(aa,bb)]
    results.append(dict(scenario=s,car=car,comparison=a+'_'+b,n=61,max_abs_yaw_difference_rad=max(map(abs,differences)),rms_yaw_difference_rad=float(np.sqrt(np.mean(np.square(differences))))))
 csvwrite(out/'yaw_solver_controls.csv',results)
 dump(out/'PUBLICATION_SEMANTICS.json',dict(source_sha256=sha(Path(__file__)),estimator_runs=0,runs=manifest,
  scope='No independent physical publication or controller receipt is available. Publication means the immutable virtual update pose written by the original replay sink.',
  shared_original_exporter_sha256=index['source_sha256']['tools/cooperative_influence_probe_20261028/run_development.py']))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run(a.evidence,a.output)
