"""Prepare paired slants, then run or resume individual pilot searches."""
import hashlib
import json
import math
import sys
from pathlib import Path
from fractions import Fraction as F
from concurrent.futures import ProcessPoolExecutor

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'layout_peer_pilot'))
import run as pilot
import numpy as np

PLAN = json.loads((HERE/'protocol.json').read_text())
OUT = HERE/'results'
pilot.OUT = OUT
pilot.MODES = {'anchor_only':('N4',F(0)), 'peer60':('P4',F(3,5)),
               'peer15':('P4',F(3,20)), 'peer05':('P4',F(1,20))}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inputs():
    template = pilot.original('main_start_normal')['original']
    original = np.array([[float(F(v)) for v in template['anchors'][f'a{i}']] for i in range(4)])
    center = original[:,:2].mean(axis=0)
    square = original.copy()
    square[:,:2] = center + np.sign(original[:,:2]-center)*math.sqrt(np.ptp(original[:,:2],axis=0).prod())/2
    h = np.array([.97,.95])
    records = []
    for seed in PLAN['seeds']:
        noise = np.random.Generator(np.random.PCG64(seed)).standard_normal((23,9))*.04
        path = OUT/f'noise_{seed}.npy'
        path.parent.mkdir(exist_ok=True)
        np.save(path, noise)
        for t in PLAN['epochs']:
            wave = .8*math.sin(t/6)
            xy = [4+.65*t,3+wave,7+.60*t,-1+wave]
            for layout, anchors in zip(PLAN['layouts'], (original,square)):
                y = pilot.slants(xy,h,anchors)+noise[t]
                rec = dict(id=f'parallel_{seed}_{t}_{layout}',split='parallel',seed=seed,epoch=t,
                    layout=layout,anchors=pilot.strings(anchors),heights=pilot.strings(h),
                    observations=pilot.strings(y),center=pilot.strings(pilot.published(anchors,h,y)),
                    reference_xy=pilot.strings(xy),generated_noise=pilot.strings(noise[t]),
                    noise_sha256=digest(path.read_bytes()),ids=template['measurement_ids'])
                pilot.save('observations/'+rec['id']+'.json',rec)
                records.append(rec)
    return records


def job(args):
    rec,mode = args
    tree = OUT/'trees'/(rec['id']+'_'+mode+'.gz')
    marker = tree.with_suffix('.done')
    certificates = [OUT/'certificates'/f"{rec['id']}_{mode}_{car}.json" for car in pilot.CAR]
    if all(p.is_file() for p in [tree,marker,*certificates]) and digest(tree.read_bytes()) == marker.read_text():
        return
    pilot.run_job(args)
    marker.write_text(digest(tree.read_bytes()))


if __name__=='__main__':
    records = inputs()
    with ProcessPoolExecutor(2) as pool:
        list(pool.map(job, [(r,m) for r in records for m in PLAN['modes']]))
