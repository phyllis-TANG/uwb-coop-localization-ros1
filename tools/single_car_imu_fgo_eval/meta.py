"""Run IO and identity only; no optimization or propagation functions."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
LEGACY=ROOT/'docs/field_tests/single_car_fixed_lag_20261022/protocol.json'


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')


def start(output,role):
    output=Path(output).resolve()
    if any((p/'.git').exists() for p in [output,*output.parents]):raise ValueError('new results outside Git only')
    output.mkdir(parents=True,exist_ok=False)
    files=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))
    files += [ROOT/'tools'/n for n in ['single_car_fixed_lag.py','single_car_sequential_replay.py','run_single_car_fixed_lag.py','run_single_car_sequential_baseline.py']]
    run={'schema_version':1,'role':role,'status':'IN_PROGRESS','code_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'worktree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
        'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'command_argv':[sys.executable]+sys.argv,
        'source_sha256':{str(p.relative_to(ROOT)):sha(p) for p in files},'legacy_protocol_sha256':sha(LEGACY),
        'inputs':[],'new_IMU_FGO_runs':0,'clock_calibration':False,'started_monotonic':time.monotonic()}
    (output/'python_packages.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
    save(output/'checkpoint.json',run);return run


def finish(output,run,status,error=None):
    run['status']=status;run['elapsed_s']=time.monotonic()-run.pop('started_monotonic')
    if error is not None:run['error']=str(error)
    run['outputs']=[{'relative_path':str(p.relative_to(output)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(Path(output).rglob('*')) if p.is_file() and p!=Path(output)/'run.json']
    save(Path(output)/'run.json',run)
