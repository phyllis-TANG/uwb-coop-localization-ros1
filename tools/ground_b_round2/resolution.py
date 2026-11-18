"""Compare only outer radii at fixed resolutions, with the same G1 output."""
import gzip
import json
import sys
from unittest.mock import patch
from evaluate import DOC, OLD, ROOT, save

sys.path.insert(0,str(ROOT/'tools/ground_continuous_b'))
import region
from a_interface import check_radius


def compare():
    p=json.loads((DOC/'protocol/PLAN.json').read_text())['conditional_resolution']
    rows=[]
    for scene in p['scenes']:
        with gzip.open(OLD/f"{p['seed']}_{scene}"/'records.json.gz','rt') as f:
            r=next(x for x in json.load(f) if x['t']==p['state_s'])
        coarse=r['region']
        for width in p['resolution_m']:
            with patch.object(region,'CELL',round(width*region.U)):
                certificate=region.solve(r['obs'],r['xy'])
            if width==.05:
                assert json.loads(json.dumps(certificate))==coarse
            check_radius(dict(region=certificate,xy=r['xy']))
            for c,(old,new) in enumerate(zip(coarse['pl'],certificate['pl']),1):
                assert new is None or (old is not None and new<=old)
                rows.append(dict(seed=p['seed'],scene=scene,state_s=r['t'],car=c,resolution_m=width,
                    status='NONEMPTY_OUTER' if new is not None else 'EMPTY',radius_m=new,
                    reduction_from_05_m=round(old-new,6) if new is not None else None,
                    joint_pairs=sum(len(js) for _,js in certificate['joint'])))
    save('resolution.csv',rows)

if __name__=='__main__':
    compare()
