"""Post-run exact trajectory attribution; does not run or tune an estimator."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

root=Path(sys.argv[1]);output=Path(sys.argv[2])
if output.exists():raise FileExistsError(output)
run=json.loads((root/'run.json').read_text())
reports={}
for name in run['profiles']:
    families={'feedback':['huber','gate_only','cap_only','gate_cap'], 'nonfeedback':['gate_cap_shadow']}
    differences={key:0 for key in families};states=0;final=None
    with gzip.open(root/name/'states.jsonl.gz','rt') as f:
        for line in f:
            methods=json.loads(line)['methods'];final=methods;states+=1
            for family,names in families.items():
                base=methods['joint' if family=='feedback' else 'shadow_only']
                for method in names:
                    item=methods[method]
                    differences[family]+=int(any(item[key]!=base[key] for key in ('vehicles','feedback_state','feedback_covariance','output_delta')))
    reports[name]=dict(publications=states,differing_method_publications=differences,
        final_policy_counts={m:s['policy_counts'] for m,s in final.items()})
result=dict(scope='exact output/feedback equivalence, not measured accuracy',
    input_run_sha256=hashlib.sha256((root/'run.json').read_bytes()).hexdigest(),
    postprocessor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),profiles=reports)
output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({name:r['differing_method_publications'] for name,r in reports.items()}))
