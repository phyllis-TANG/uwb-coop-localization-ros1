"""Exactly48 private optimizer cells. No push, retries or parameter adaptation."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from local_support import DOC,HERE,METHODS,dump,gitstate,new,protocol,sha,sources

def matrix(output):
    p=protocol();state=gitstate()
    if state['worktree_dirty']:raise ValueError('Commit complete runnable configuration and source before results')
    root=new(output);(root/'logs').mkdir();frozen=sources();start=time.perf_counter()
    index=dict(status='IN_PROGRESS',**state,protocol_sha256=sha(DOC/'PROTOCOL.json'),source_sha256=frozen,
        cells=[],commands=[],public_upload_authorized=False)
    dump(root/'RUN_INDEX.json',index)
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    def command(name,script,*args):
        if sources()!=frozen:raise ValueError('Source changed')
        if time.perf_counter()-start>p['resource_limits']['total_wall_s']:raise TimeoutError('Frozen total budget')
        argv=[sys.executable,str(HERE/script),*map(str,args)];index['commands'].append(argv);dump(root/'RUN_INDEX.json',index)
        def limits():resource.setrlimit(resource.RLIMIT_AS,(2147483648,2147483648))
        with (root/'logs'/name).open('x') as f:subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=180,preexec_fn=limits)
    try:
        for seed in p['seeds']:
            command(f'{seed}-inputs.log','inputs.py','--seed',seed,'--output',root/'inputs'/str(seed))
            command(f'{seed}-pairing.log','pairing.py','--input',root/'inputs'/str(seed),'--output',root/(str(seed)+'-PAIRING.json'))
            for geometry in ('G1','G2'):
                for processing in ('raw','historical'):
                    inp=root/'inputs'/str(seed)/(geometry+'-'+processing)
                    for method in METHODS:
                        tag=f'{seed}-{geometry}-{processing}-{method}';run=root/'runs'/tag
                        command(tag+'-run.log','execute.py','--events',inp/'events.jsonl.gz','--config',inp/'config.json','--method',method,'--output',run)
                        command(tag+'-readback.log','readback.py','--run',run,'--events',inp/'events.jsonl.gz','--output',root/(tag+'-READBACK.json'))
                        info=json.loads((run/'run.json').read_text());index['cells'].append(dict(seed=seed,geometry=geometry,processing=processing,method=method,run=str(run.relative_to(root)),input=str(inp.relative_to(root)),run_json_sha256=sha(run/'run.json'),readback_sha256=sha(root/(tag+'-READBACK.json')),status=info['status']))
                        dump(root/'RUN_INDEX.json',index)
                        if sum(q.stat().st_size for q in root.rglob('*') if q.is_file())>p['resource_limits']['artifact_bytes']:raise ValueError('Artifact cap')
        if len(index['cells'])!=48:raise ValueError('Unexpected cell count')
        index.update(status='DONE',elapsed_s=time.perf_counter()-start)
    except BaseException as e:
        index.update(status='FAILED',error=type(e).__name__+': '+str(e));raise
    finally:
        index['files']={str(q.relative_to(root)):sha(q) for q in root.rglob('*') if q.is_file() and q.name!='RUN_INDEX.json'};dump(root/'RUN_INDEX.json',index)
    return index

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args();r=matrix(a.output);print(json.dumps(dict(status=r['status'],cells=len(r['cells']),elapsed_s=r['elapsed_s'])))
