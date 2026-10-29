#!/usr/bin/env python3
"""Final artifact-only input/output binding and relocation checks."""
import argparse,gzip,json
from pathlib import Path
from common import sha,dump

def check(root,original,relocated,output):
    index=json.loads((root/'RUN_INDEX.json').read_text());n=0
    for c in index['cells']:
        m=json.loads((root/c['run_path']/'run.json').read_text())
        assert m['config_sha256']==c['config_sha256']==sha(root/c['run_path']/'config.json')
        assert m['input_sha256' if c['method']=='D3' else 'events_sha256']==c['events_sha256']
        if c['method']!='D3':
            for k in ['labels_sha256','truth_sha256']:assert m[k]==c[k]
            assert m['method']==c['original_method'] and m['seed']==c['seed'] and m['scenario']==c['scenario']
        else:
            assert m['method']=='D3' and m['dcs_config_sha256']==index['dcs_config_sha256']==sha(root/c['run_path']/'dcs_config.json')
        n+=1
    names=['metrics.csv','paired_contrasts.csv','weights.csv','costs.csv','audits.json','receipt.json']
    for name in names:assert (original/name).read_bytes()==(relocated/name).read_bytes()
    with gzip.open(original/'timeline.csv.gz','rb') as a,gzip.open(relocated/'timeline.csv.gz','rb') as b:assert a.read()==b.read()
    result=dict(status='PASS',input_run_bindings=n,relocated_byte_identical_files={n:sha(original/n) for n in names},timeline_decompressed_equal=True,estimator_runs=0,script_sha256=sha(Path(__file__)))
    if output.exists():raise FileExistsError(output)
    dump(output,result);print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',type=Path,required=True);p.add_argument('--original-evaluation',type=Path,required=True);p.add_argument('--relocated-evaluation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();check(a.matrix,a.original_evaluation,a.relocated_evaluation,a.output)
