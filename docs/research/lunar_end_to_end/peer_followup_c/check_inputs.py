"""Reconstruct observations, route, random draws and the common published fix."""
import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
D = HERE/'results'


def load(p):
    return json.loads(p.read_text())


def numeric(a):
    return np.vectorize(lambda x:float(F(x)))(a)


def check():
    prior = load(HERE.parent/'layout_peer_pilot/inputs/main_start_normal.json')['original']
    anchors = numeric([prior['anchors'][f'a{i}'] for i in range(4)])
    xy = anchors[:,:2]
    midpoint = (xy.max(axis=0)+xy.min(axis=0))/2
    square = anchors.copy()
    square[:,:2] = midpoint+np.sign(xy-midpoint)*math.sqrt(np.ptp(xy[:,0])*np.ptp(xy[:,1]))/2
    track = load(D/'route.json')
    assert len(track)==23
    for t, row in enumerate(track):
        assert row==dict(t=t,xy4=[5+.60*t,1+.12*t,17-.45*t,5-.10*t],z2=[.97,.95])
    for seed in range(2026112311,2026112314):
        draws = np.random.Generator(np.random.PCG64(seed)).standard_normal((23,9))*.04
        noise = load(D/'noise'/f'{seed}.json')
        assert noise['seed']==seed and np.array_equal(draws,noise['noise_m'])
        assert hashlib.sha256(draws.astype('<f8').tobytes()).hexdigest()==noise['sha256_float64_le']
        for t in (4,14):
            pos = np.column_stack((np.reshape(track[t]['xy4'],(2,2)),track[t]['z2']))
            for layout,geom in [('original',anchors),('equal_area_square',square)]:
                key = f'{seed}_{t:02d}_{layout}'
                rec = load(D/'observations'/f'{key}.json')
                assert (rec['id'],rec['route'],rec['seed'],rec['epoch'],rec['layout'])==(key,'crossing_offset',seed,t,layout)
                assert rec['ids']==prior['measurement_ids']
                assert np.array_equal(numeric(rec['reference_xy']),pos[:,:2].ravel())
                assert np.array_equal(numeric(rec['heights']),pos[:,2])
                a = numeric(rec['anchors'])
                np.testing.assert_allclose(a,geom,atol=8e-15,rtol=0)
                assert np.array_equal(numeric(rec['generated_noise']),draws[t])
                true_peer = np.linalg.norm(pos[1]-pos[0])
                assert true_peer==rec['true_peer_m']
                y = numeric(rec['observations'])
                ranges = np.linalg.norm(pos[:,None]-a,axis=2)
                assert np.array_equal(y,np.r_[ranges.ravel(),true_peer]+draws[t])
                for i in range(2):
                    rhs = (a[:,:2]**2).sum(axis=1)+(pos[i,2]-a[:,2])**2-y[i*4:i*4+4]**2
                    fix = np.linalg.lstsq(2*(a[1:,:2]-a[0,:2]),rhs[1:]-rhs[0],rcond=None)[0]
                    np.testing.assert_allclose(fix,numeric(rec['center'][i]),atol=1e-12,rtol=0)
    print('PASS 23 route epochs, 3 complete noise matrices, 12 paired observations and fixes')


if __name__=='__main__':
    check()
