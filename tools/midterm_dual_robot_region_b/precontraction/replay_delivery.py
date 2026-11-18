"""Read frozen pilot inputs and recompute all 14 verdicts without running search."""
import subprocess
from formal import A, D, DOC, PLAN, READY, read, sha, digest
from review import inspect

freeze = 'a86d143b83617bb360402ff3bd0745231545a001'
assert sha(DOC/'INPUTS.json.gz') == PLAN['input_file_sha256']
assert all(sha(A/path)==h for path,h in READY['file_hashes'].items())
for name in ('formal.py','review.py'):
    path='tools/midterm_dual_robot_region_b/precontraction/'+name
    assert subprocess.check_output(['git','show',freeze+':'+path])==(DOC.parents[2]/path).read_bytes()
root=D/'runs/pilot'
stored={r['id']:r for r in read(root/'decision.json')['rows']}
assert len(stored)==14
for item in PLAN['jobs']:
    folder=root/(item['case']+'_'+item['arm'])
    job=read(folder/'job.json')
    assert digest(job['case'])==item['input_sha256'] and job['settings']==item['settings']
    assert job['freeze']==freeze and job['method']=='P4' and job['arm']==item['arm']
    assert inspect(folder)==stored[folder.name]
print('PASS: 14 original-input identities, trees or strict emptiness, projections, evaluations and timings.')
