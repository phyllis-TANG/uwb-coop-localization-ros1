"""Check complete delivery record and independently reconstruct the vehicle clock."""
import gzip
import json
from collections import Counter
from pathlib import Path
import sys
import numpy as np
from trajectory import VERSIONS

def verify(folder):
    def read(name):
        return json.loads(gzip.decompress((folder/(name+'.json.gz')).read_bytes()))
    epochs,ticks,events=map(read,('epochs','ticks','tta'))
    meta=json.loads((folder/'summary.json').read_text())
    assert len(epochs)==63 and len(ticks)==2560
    last=0
    for i,e in enumerate(epochs,1):
        assert e['t']==i and e['all_arrived']==max(e['receipts']) and len(set(e['ids']))==4
        assert e['start']==max(e['all_arrived'],last) and e['finish']==e['ready']==e['start']+e['service']
        assert e['service']>0 and e['expiry']==i+2
        assert (e['stat']<=21.665994333461924)==(e['action']=='ACCEPT')
        if e['action']=='REJECT':
            assert e['bias']==epochs[i-2]['bias']
            np.testing.assert_allclose(np.subtract(e['covariance_diag'],epochs[i-2]['covariance_diag']),[.03**2]*4+[.01**2]*9)
        last=e['ready']
    assert Counter(e['action'] for e in epochs)==meta['actions']
    first={}
    counts=Counter()
    for j,r in enumerate(ticks):
        t=(j//2)/20
        car=j%2
        assert r['t']==t and r['car']==car+1
        e=next((e for e in reversed(epochs) if e['ready']<=t),None)
        if e and e['expiry']<t:
            e=None
        assert r['state_time']==(e['t'] if e else None)
        assert r['xy']==(e['cars'][car]['xy'] if e else None)
        if e:
            first.setdefault(e['t'],t)
        for v in VERSIONS:
            pl=e['cars'][car]['hcpl'][v] if e else None
            s=('NO_DECISION' if not e else 'ALARM' if e['action']=='REJECT' or pl>.10 else 'AVAILABLE')
            assert s==r['status'][v]
            counts[car+1,v,s]+=1
    assert all(first.get(e['t'])==e['first_display'] for e in epochs)
    for r in meta['summary']:
        k=(r['car'],r['variant'])
        assert [20*r[n] for n in ('available_s','alarm_s','no_decision_s')]==[counts[k+(s,)] for s in ('AVAILABLE','ALARM','NO_DECISION')]
    assert all({e['limit'] for e in events if (e['car'],e['variant'],e['episode'])==key}=={1,2,5}
               for key in {(e['car'],e['variant'],e['episode']) for e in events})
    return meta['scene']

if __name__=='__main__':
    for path in sorted(Path(sys.argv[1]).iterdir()):
        print(path.name,verify(path),'PASS')
