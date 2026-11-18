"""Bind A's published radius calculation to B's ground projection boxes."""
import hashlib
import json
import subprocess
import types
from fractions import Fraction
from pathlib import Path

A_SHA = '94e70e9d50011802d867c849d21fe7935f78ebc9'
ROOT = Path(__file__).resolve().parents[2]
name = 'tools/midterm_dual_robot_contract_a/integrity_v1/decision.py'
module = types.ModuleType('a_published_decision')
module.__file__ = str(ROOT / name)
exec(compile(subprocess.check_output(['git','show',A_SHA+':'+name],cwd=ROOT),name,'exec'),module.__dict__)


def identity(obs):
    return hashlib.sha256(json.dumps(obs,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def check_radius(row):
    region = row['region']
    joint = region['joint']
    indices = ([i for i,_ in joint], sorted({j for _,items in joint for j in items}))
    radii = []
    for car, valid in enumerate(indices):
        rectangles = [dict(box=[[str(Fraction(l,1000000)),str(Fraction(u,1000000))] for l,u in region['cells'][car][i][0]]) for i in valid]
        xy = [str(Fraction(v)) for v in row['xy'][car]]
        radius = module.covering_radius(rectangles,xy) if valid else None
        if radius is not None:
            delta = Fraction(str(region['pl'][car])) - radius
            assert 0 <= delta <= Fraction(3,1000000), delta
        else:
            assert region['pl'][car] is None
        radii.append(str(radius) if radius is not None else None)
    return radii
