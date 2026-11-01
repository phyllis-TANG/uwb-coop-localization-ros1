"""Finite frozen run list. No automatic seeds, retries or parameter search."""
import argparse
from datetime import datetime,timezone
import json
import os
import resource
from pathlib import Path
import subprocess
import sys
import time
from support import HERE, METHODS, MOTIONS, dump, git_state, new_output, protocol, sha, sources


def execute(protocol_path, partition, output):
    p = protocol(protocol_path)
    part = p['partitions'][partition]
    if not part['seeds']:
        raise ValueError('Partition is not frozen/enabled')
    state = git_state()
    if state['worktree_dirty']:
        raise ValueError('Commit the protocol/source before any run')
    root = new_output(output)
    (root/'logs').mkdir()
    frozen = sources()
    started = time.perf_counter()
    env = dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    index = dict(status='IN_PROGRESS',partition=partition,protocol_sha256=sha(protocol_path),
        protocol_commit=subprocess.check_output(['git','log','-1','--format=%H','--',str(Path(protocol_path).resolve().relative_to(HERE.parents[1]))],cwd=HERE.parents[1],text=True).strip(),
        **state,source_sha256=frozen,started_utc=datetime.now(timezone.utc).isoformat(),commands=[],cells=[])
    dump(root/'RUN_INDEX.json',index)
    def command(name,script,*args):
        if sources() != frozen:
            raise ValueError('Frozen sources changed during matrix')
        if time.perf_counter()-started > p['resources']['partition_wall_cap_s']:
            raise TimeoutError('Frozen total partition budget')
        argv = [sys.executable,str(HERE/script),*map(str,args)]
        index['commands'].append(argv)
        dump(root/'RUN_INDEX.json',index)
        with (root/'logs'/name).open('x') as f:
            def limits():
                cap=p['resources'].get('subprocess_address_space_cap_bytes',2147483648)
                resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
            subprocess.run(argv,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,
                timeout=p['resources']['subprocess_wall_cap_s'],preexec_fn=limits)
    try:
        for seed in part['seeds']:
            for motion in MOTIONS:
                for condition in part['conditions']:
                    tag=f'{seed}-{motion}-{condition}'
                    inp=root/'inputs'/tag
                    command(tag+'-input.log','inputs.py','--protocol',protocol_path,'--partition',partition,
                        '--seed',seed,'--motion',motion,'--condition',condition,'--output',inp)
                    for method in METHODS:
                        cell=tag+'-'+method
                        run=root/'runs'/tag/method
                        command(cell+'-run.log','run.py','--events',inp/'events.jsonl.gz','--config',inp/'config.json',
                            '--method',method,'--output',run)
                        command(cell+'-readback.log','readback.py','--run',run,'--events',inp/'events.jsonl.gz',
                            '--output',root/(cell+'-READBACK.json'))
                        meta=json.loads((run/'run.json').read_text())
                        if meta['process_peak_rss_kib'] > p['resources']['per_process_observed_rss_cap_kib']:
                            raise ValueError('Observed process RSS exceeds frozen cap')
                        index['cells'].append(dict(seed=seed,motion=motion,condition=condition,method=method,
                            run=str(run.relative_to(root)),input=str(inp.relative_to(root)),
                            run_json_sha256=sha(run/'run.json'),input_manifest_sha256=sha(inp/'manifest.json'),
                            readback_sha256=sha(root/(cell+'-READBACK.json')),
                            **{k:meta[k] for k in ('status','elapsed_s','process_cpu_s','process_peak_rss_kib')}))
                        size=sum(q.stat().st_size for q in root.rglob('*') if q.is_file())
                        if size > p['resources']['partition_artifact_cap_bytes']:
                            raise ValueError('Frozen artifact budget exceeded')
                        dump(root/'RUN_INDEX.json',index)
        index.update(status='DONE',elapsed_s=time.perf_counter()-started)
    except BaseException as error:
        index.update(status='FAILED',error=type(error).__name__+': '+str(error))
        raise
    finally:
        index['files']={str(q.relative_to(root)):sha(q) for q in root.rglob('*') if q.is_file() and q.name!='RUN_INDEX.json'}
        dump(root/'RUN_INDEX.json',index)
    return index


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',required=True,type=Path)
    p.add_argument('--partition',required=True,choices=('development','calibration','test'))
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    result=execute(a.protocol,a.partition,a.output)
    print(json.dumps(dict(status=result['status'],partition=result['partition'],cells=len(result['cells']),elapsed_s=result['elapsed_s'])))
