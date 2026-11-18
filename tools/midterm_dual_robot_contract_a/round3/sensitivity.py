"""Paired replay on the preregistered 101 grid, changing only initial covariance."""
import csv
import gzip
import json
import math
from pathlib import Path
import tempfile
from unittest.mock import patch

import numpy as np

from decompose import DOC, FREEZE, OUT, SOURCE, blob, diagonal, frozen_filter

XY_SD=(.20,.08,.03,.01)
BIAS_SD=(.30,.10,.03,.01)
TRUTH='01e588021e7e3ddd918b1d1fc9561973373758c6'


def simulate(module, scene):
    path='docs/research/ground_b_round2/runtime/101_'+scene
    cfg=json.loads(blob(SOURCE,path+'/geometry.json'))
    raw=blob(SOURCE,path+'/events.jsonl.gz')
    archived=json.loads(gzip.decompress(blob(FREEZE,DOC+'/round2/dev/101_'+scene+'/epochs.json.gz')))
    factory=module.Filter
    runs=[]
    for xy in XY_SD:
        for bias in BIAS_SD:
            def create(config):
                f=factory(config)
                f.P=diagonal(xy**2,bias**2)
                return f
            with patch.object(module,'Filter',create):
                epochs=module.replay(raw,cfg)
            ticks=module.display(epochs)
            if (xy,bias)==(.2,.3):
                for e,a in zip(epochs,archived,strict=True):
                    assert e['action']==a['action']
                    for c,b in zip(e['cars'],a['cars']):
                        np.testing.assert_allclose(c['xy'],b['xy'],rtol=0,atol=1e-12)
                        for v in module.VERSIONS:
                            if c['hcpl'][v] is None:
                                assert b['hcpl'][v] is None
                            else:
                                assert abs(c['hcpl'][v]-b['hcpl'][v])<1e-12
            runs.append((xy,bias,epochs,ticks))
    return runs


def evaluate(scene,runs):
    truth=json.loads(gzip.decompress(blob(TRUTH,f'docs/research/ground_continuous_b/runs/101_{scene}/truth.json.gz')))
    rows=[]
    for xy,bias,epochs,ticks in runs:
        for idx in range(2):
            clock=ticks[idx::2]
            assert len(clock)==len(truth)==1280
            def available(r):
                return r['status']['history']=='AVAILABLE'
            def exposed(i):
                return available(clock[i]) and math.dist(clock[i]['xy'],truth[i][idx])>.1
            levels=[e['cars'][idx]['hcpl']['history'] for e in epochs]
            recovery=next((r['t'] for r in clock if r['t']>=38 and available(r)),None)
            row=dict(scene=scene,xy_sd=xy,bias_sd=bias,car=idx+1,epochs=len(epochs),ticks=len(clock),
                     rejects=sum(e['action']=='REJECT' for e in epochs),
                     available_after_first_epoch=sum(v is not None and v<=.10 for v in levels[1:]),
                     min_later_accepted_PL=min((v for v in levels[1:] if v is not None),default=None),
                     first_PL=levels[0],first_available_after_clear_s=recovery if scene=='wall' else None)
            for phase,start,end in [('all',0,64),('injection',24,38),('after_clear',38,64)]:
                if scene=='nominal' and phase!='all':
                    row[phase+'_available_s']=row[phase+'_exposed_s']=None
                    continue
                indices=range(20*start,20*end)
                row[phase+'_available_s']=sum(available(clock[i]) for i in indices)/20
                row[phase+'_exposed_s']=sum(exposed(i) for i in indices)/20
            rows.append(row)
    return rows


def main():
    rows=[]
    with tempfile.TemporaryDirectory() as tmp:
        module=frozen_filter(Path(tmp))
        for scene in ('nominal','wall'):
            runs=simulate(module,scene)
            rows.extend(evaluate(scene,runs))
            archive=[dict(xy_sd=x,bias_sd=b,epochs=e) for x,b,e,_ in runs]
            (OUT/f'scan_{scene}.json.gz').write_bytes(gzip.compress(
                json.dumps(archive,allow_nan=False,separators=(',',':')).encode(),mtime=0))
    with (OUT/'scan.csv').open('w') as f:
        w=csv.DictWriter(f,rows[0],lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    assert len(rows)==64


if __name__=='__main__':
    main()
