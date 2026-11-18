"""Replay only the selected preregistered stage, after checking the manifest."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from trajectory import ROOT,blob

DOC=ROOT/'docs/research/midterm_dual_robot_contract_a/round2'
SOURCE='85fbe8aca47f0b8d25b6b97107e91b8550737195'
DIR='docs/research/ground_b_round2/runtime'
p=argparse.ArgumentParser()
p.add_argument('stage',choices=['dev','holdout'])
p.add_argument('out',type=Path)
p.add_argument('--freeze')
a=p.parse_args()
if a.stage=='holdout':
    if not a.freeze or len(a.freeze)!=40:
        p.error('holdout requires the full A freeze SHA')
    for path in [Path(__file__),Path(__file__).with_name('trajectory.py'),DOC/'packages.json',DOC/'PROTOCOL.md',
                 ROOT/'tools/midterm_dual_robot_contract_a/ground_hcpl/example.py',
                 ROOT/'docs/research/midterm_sim_review/round1/ground/replay_tta.py']:
        if blob(a.freeze,path.resolve().relative_to(ROOT))!=path.read_bytes():
            raise ValueError(f'frozen dependency differs: {path}')
manifest=json.loads((DOC/'packages.json').read_text())
seeds=(101,) if a.stage=='dev' else (2026111901,2026111902)
for seed in seeds:
    for scene in ('nominal','wall','peer_ramp','peer_step'):
        name=f'{seed}_{scene}'
        folder=f'{DIR}/{name}'
        entry=manifest[name]
        if hashlib.sha256(blob(SOURCE,folder+'/SHA256SUMS')).hexdigest()!=entry:
            raise ValueError('manifest changed')
        subprocess.run([sys.executable,Path(__file__).with_name('trajectory.py'),SOURCE,
                        folder,str(seed),scene,a.out/name],check=True,
                       env=dict(os.environ,OPENBLAS_NUM_THREADS='1'))
