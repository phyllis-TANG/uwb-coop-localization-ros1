"""Read back archived states with the frozen vehicle-clock and excursion scorer."""
import csv
import gzip
import json
import math
import tempfile
from pathlib import Path
from sensitivity import OUT,XY_SD,BIAS_SD,TRUTH,blob,frozen_filter

rows=list(csv.DictReader((OUT/'scan.csv').open()))
key=lambda r:(r['scene'],float(r['xy_sd']),float(r['bias_sd']),int(r['car']))
by_key={key(r):r for r in rows}
assert len(rows)==len(by_key)==64
with tempfile.TemporaryDirectory() as tmp:
    module=frozen_filter(Path(tmp))
    for scene in ('nominal','wall'):
        truth=json.loads(gzip.decompress(blob(TRUTH,f'docs/research/ground_continuous_b/runs/101_{scene}/truth.json.gz')))
        runs=json.loads(gzip.decompress((OUT/f'scan_{scene}.json.gz').read_bytes()))
        assert len(runs)==16 and {(r['xy_sd'],r['bias_sd']) for r in runs}=={(x,b) for x in XY_SD for b in BIAS_SD}
        for run in runs:
            epochs=run['epochs']
            assert [e['t'] for e in epochs]==list(range(1,64))
            ticks=module.display(epochs)
            scores,_=module.score(ticks,truth)
            for s in scores:
                if s['variant']=='history':
                    row=by_key[scene,run['xy_sd'],run['bias_sd'],s['car']]
                    assert float(row['all_available_s'])==s['available_s']
                    assert float(row['all_exposed_s'])==s['exceed_available_s']
            if scene=='nominal' and run['xy_sd']==.01 and run['bias_sd']==.3:
                print('t=1 matched-time errors (m)',[math.dist(c['xy'],v) for c,v in zip(epochs[0]['cars'],truth[20])])
print('32/32 archives and 64/64 primary car scores verified')
