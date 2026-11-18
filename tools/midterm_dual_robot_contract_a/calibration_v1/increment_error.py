"""Offline one-second antenna increment check on the nominal development replay."""
import csv
import gzip
import json
from math import cos, radians, sin
from pathlib import Path
import sys
import tempfile

import numpy as np

from development import CARS, EVAL, OUT, ROOT, blob, frozen


def rotate(angle, xy):
    x, y = xy
    return np.array([cos(angle)*x - sin(angle)*y, sin(angle)*x + cos(angle)*y])


def evaluate():
    package = ROOT / 'docs/research/ground_b_round2/runtime/101_nominal'
    cfg = json.loads((package / 'geometry.json').read_text())
    headings = json.loads((OUT / 'calibration.json').read_text())['mean_heading_deg']
    truth = json.loads(gzip.decompress(blob(EVAL,
        'docs/research/ground_continuous_b/runs/101_nominal/truth.json.gz')))
    with tempfile.TemporaryDirectory() as temp:
        method = frozen(Path(temp))
        frames = method.groups((package / 'events.jsonl.gz').read_bytes(), cfg)
        for i, car in enumerate(CARS):
            model = dict(cfg['models'][car], initial_heading_deg=headings[i])
            lever = model['base_to_antenna_body_xy_m']
            origin = frames[1][car, 'odom']['value']['pose']
            angle = radians(headings[i]) - origin[2]
            for t in range(2, 64):
                observations = [frames[k][car, 'odom'] for k in (t-1, t)]
                a, b = [np.asarray(e['value']['pose']) for e in observations]
                base = rotate(angle, b[:2] - a[:2])
                arm = rotate(angle+b[2], lever) - rotate(angle+a[2], lever)
                predicted = base + arm
                offsets = [method.ref.antenna_offset(p, origin, model) for p in (a, b)]
                np.testing.assert_allclose(predicted, offsets[1]-offsets[0], atol=2e-14, rtol=0)
                reference = np.asarray(truth[20*t][i]) - truth[20*(t-1)][i]
                yield [car, t-1, t, *(e['source_observation_id'] for e in observations),
                       *base, *arm, *predicted, *reference, *(predicted-reference)]


if __name__ == '__main__':
    rows = list(evaluate())
    writer = csv.writer(sys.stdout, lineterminator='\n')
    writer.writerow(['car','start_s','end_s','start_id','end_id','base_dx','base_dy',
                     'lever_dx','lever_dy','odom_dx','odom_dy','ref_dx','ref_dy','err_x','err_y'])
    writer.writerows(rows)
    for car in CARS:
        errors = np.array([r[-2:] for r in rows if r[0] == car])
        print(car, 'first, mean, rms, max abs (cm):',
              errors[0]*100, errors.mean(axis=0)*100, np.sqrt((errors**2).mean(axis=0))*100,
              abs(errors).max(axis=0)*100, file=sys.stderr)
