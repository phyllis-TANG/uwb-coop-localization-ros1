"""Generate paired inputs and checkpoint each completed pilot search."""
import csv
import hashlib
import importlib.util
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent / 'layout_peer_pilot'
sys.path.insert(0, str(PILOT))
spec = importlib.util.spec_from_file_location('pilot_run', PILOT / 'run.py')
pilot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pilot)
np = pilot.np
OUT = pilot.OUT = HERE / 'results'
CFG = json.loads((HERE / 'config.json').read_text())
pilot.MODES = {k: ('N4', F(0)) if v is None else ('P4', F(v))
               for k, v in CFG['peer_bias_halfwidth_m'].items()}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs():
    source = pilot.original('main_start_normal')['original']
    original = np.array([[float(F(v)) for v in source['anchors'][f'a{i}']] for i in range(4)])
    c = original[:, :2].mean(axis=0)
    square = original.copy()
    square[:, :2] = c + np.sign(original[:, :2]-c)*math.sqrt(np.prod(np.ptp(original[:, :2],axis=0)))/2
    route = [(5+.60*t,1+.12*t,17-.45*t,5-.10*t) for t in range(23)]
    heights = np.array([.97,.95])
    pilot.save('route.json', [dict(t=t,xy4=xy,z2=heights.tolist()) for t,xy in enumerate(route)])
    for seed in CFG['seeds']:
        noise = np.random.Generator(np.random.PCG64(seed)).standard_normal((23,9))*.04
        pilot.save(f'noise/{seed}.json', dict(seed=seed,noise_m=noise.tolist(),
                   sha256_float64_le=sha(noise.astype('<f8').tobytes())))
        for t in CFG['epochs']:
            xy = route[t]
            for layout, a in zip(CFG['layouts'], (original,square)):
                slants = pilot.slants(xy,heights,a)
                y = slants+noise[t]
                key = f'{seed}_{t:02d}_{layout}'
                rec = dict(id=key,route=CFG['route'],seed=seed,split=str(seed),epoch=t,layout=layout,
                           anchors=pilot.strings(a),heights=pilot.strings(heights),
                           observations=pilot.strings(y),center=pilot.strings(pilot.published(a,heights,y)),
                           reference_xy=pilot.strings(xy),generated_noise=pilot.strings(noise[t]),
                           ids=source['measurement_ids'],true_peer_m=float(slants[-1]))
                path = f'observations/{key}.json'
                pilot.save(path,rec)
                rec['input_hash'] = sha((OUT/path).read_bytes())
                yield rec


def job(args):
    rec, mode = args
    key = rec['id']+'_'+mode
    marker = OUT/'completed'/(key+'.json')
    if marker.exists():
        rows = json.loads(marker.read_text())
        if all(r['input_hash']==rec['input_hash'] for r in rows):
            return rows
    rows = pilot.run_job(args)
    for r in rows:
        cert = json.loads((OUT/'certificates'/(key+'_'+r['car']+'.json')).read_text())
        r.update(route=rec['route'],seed=rec['seed'],t=rec['epoch'],input_hash=rec['input_hash'],
                 truth_feasible=r['true_feasible'],true_peer_m=rec['true_peer_m'],
                 status_20cm=('EXCLUDED' if F(cert['any_lower_squared'])>F(1,25) else
                              'CERTIFIED' if F(cert['outer_squared'])<=F(1,25) else 'UNRESOLVED'))
    marker.parent.mkdir(exist_ok=True)
    tmp = marker.with_suffix('.tmp')
    tmp.write_text(json.dumps(rows,indent=2)+'\n')
    tmp.replace(marker)
    return rows


if __name__=='__main__':
    jobs = [(r,m) for r in inputs() for m in pilot.MODES]
    with ProcessPoolExecutor(2) as pool:
        rows = [r for pair in pool.map(job,jobs) for r in pair]
    with (OUT/'rows.csv').open('w',newline='') as f:
        w = csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
