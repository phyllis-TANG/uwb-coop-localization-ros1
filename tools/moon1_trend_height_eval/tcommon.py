"""Frozen dependency bridge and durable serialization, no dataset reads on import."""
import sys,os,json,gzip,csv,hashlib,subprocess,fcntl,contextlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
BASE='0c3dbbb59a5c65087e073ad1c49eaed397f2958b'
DOC=ROOT/'docs/research/moon1_trend_height_eval'
sys.path.insert(0,str(ROOT/'tools/moon1_bias_dynamics_eval'))
from bridge import clean,digest,read,filehash,write,csvwrite,unpack,git
from model import problem as old_problem,validate as old_validate
from generate import make_input

def sources():
 paths=list((ROOT/'tools/moon1_trend_height_eval').glob('*.py'))
 paths += [ROOT/x for x in ['tools/moon1_bias_dynamics_eval/bridge.py','tools/moon1_localization_eval/common.py','tools/moon1_localization_eval/model.py','tools/moon1_localization_eval/generate.py','tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py','sim/isaac_lab/moon1/antenna_geometry.py']]
 paths += [DOC/x for x in ['CONFIG.json','SEEDS.json','SOLVER.json','PROTOCOL.md','MATH.md','UNCERTAINTY_CONTRACT.md','INPUT_PLAN.json','HISTORY_SHA256.json.gz','SEED_AUDIT.json'] if (DOC/x).exists()]
 return {str(p.relative_to(ROOT)):filehash(p) for p in sorted(paths)}

@contextlib.contextmanager
def lock(p):
 with Path(p).open('a') as f:
  fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);yield;fcntl.flock(f.fileno(),fcntl.LOCK_UN)

class Evidence:
 def __init__(self,root):self.root=Path(root);self.cache={}
 def get(self,rel):
  p=self.root/rel
  if p.exists():return read(p)
  group,tail=rel.split('/',1)
  if group not in self.cache:self.cache[group]=unpack(self.root/(group+'.json.gz'))
  return self.cache[group][tail]
