"""No-search verification of every exported certificate and published-point radius."""
from monitor import *

def verify():
    install()
    E,A,I=modules()
    events={e['case']:e for e in read(D/'events.json')}
    summaries={(s['case'],s['method']):s for s in read(D/'services.json')}
    for path in sorted((D/'certificates').glob('*.json.gz')):
        data=read(path);x,c=data['original'],data['certificate']
        key=x['case_id'];method='P4' if c['mode']=='4d' else 'N4'
        assert A.check(x,c)['certificate_valid']
        e=events[key];s=summaries.pop((key,method))
        assert F(x['source_times']['p'])-F(x['source_times']['s'])==5
        assert all(str(I.covering_radius(c['projections'][car]['rectangles'],e['published_xy'][k]))==s['PL'][k] for k,car in enumerate('ps'))
    assert len(events)==94 and not summaries
    print('PASS 188 region certificates and 376 published-point radii')

if __name__=='__main__':verify()
