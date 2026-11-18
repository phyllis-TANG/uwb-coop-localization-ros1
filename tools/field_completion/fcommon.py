import sys,json,hashlib,os
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'tools/field_moon1_integration'
sys.path.insert(0,str(OLD))
from common import clean,read,write,digest,SOURCE
sys.path.insert(0,str(ROOT/'tools'))
DOC=ROOT/'docs/research/field_completion'
from two_car_updated_comparison import CARS,rotation

def source_hashes():
 paths=list((ROOT/'tools/field_completion').glob('*.py'))+list(OLD.glob('*.py'))
 paths += [ROOT/p for p in ['tools/two_car_updated_comparison.py','tools/single_car_fixed_lag.py','tools/single_car_sequential_replay.py','docs/research/field_moon1_integration/CONFIG.json','docs/research/field_moon1_integration/results/portable.json.gz','docs/field_tests/field_observation_readiness/results/SOURCES.json','docs/research/field_completion/CONFIG.json','docs/research/field_completion/PROTOCOL.md']]
 paths+=list(SOURCE.glob('*/measurements.jsonl.gz'))
 return {str(p.relative_to(ROOT)):digest(p) for p in sorted(paths)}
