"""Shared IO/provenance only; no estimator, motion equation or calibration."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
SESSION=ROOT/'docs/field_tests/20261024_25'
CONTRACT=SESSION/'imu_parallel_20261027/CONTRACT.json'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def start(output,role):
    output=Path(output).resolve()
    if any((p/'.git').exists() for p in [output,*output.parents]):raise ValueError('new results must be outside Git')
    output.mkdir(parents=True,exist_ok=False)
    files=[]
    for directory in ('imu_field_prep','imu_verification'):
        files+=list((ROOT/'tools/field_20261024_25'/directory).glob('*.py'))
        files+=list((ROOT/'tools/field_20261024_25'/directory).glob('*.json'))
    run={'schema_version':1,'role':role,'status':'IN_PROGRESS',
        'base_commit':'d079c26ff1f279fbe5db131b43f809d77b561345',
        'code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
        'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'command_argv':[sys.executable]+sys.argv,'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},
        'config_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [CONTRACT,SESSION/'manifest.json',SESSION/'geometry.json']},
        'inputs':[],'blocked_reasons':[],'new_model_field_replays':0,'started_monotonic':time.monotonic()}
    (output/'python_packages.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    save(output/'checkpoint.json',run)
    return run


def finish(output,run,status,error=None):
    run['status']=status;run['elapsed_s']=time.monotonic()-run.pop('started_monotonic')
    if error is not None:run['error']=str(error)
    run['outputs']=[{'relative_path':str(p.relative_to(output)),'sha256':sha(p),'bytes':p.stat().st_size}
                    for p in sorted(Path(output).rglob('*')) if p.is_file() and p!=Path(output)/'run.json']
    save(Path(output)/'run.json',run)
