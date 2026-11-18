"""Low-cost exact witness and truth replay, without running search or an optimizer."""
from study import *


def point_box(xy):
    return tuple((F(v),F(v)) for v in xy)


def verify(A):
    for name in PLAN['cases']:
        verify_witness(name)
        old=read(BASE/'results'/name/'fine_matched.json.gz')
        nodes={n['id']:n for n in old['certificate']['nodes']}
        zero=read(D/'inputs/zero'/(name+'.json'))['original']
        ctx=A.Context(zero,A.event_root(zero))
        for w in read(D/'witnesses'/(name+'.json'))['vehicles'].values():
            for p in w['points']:
                leaf=nodes[p['leaf']]
                assert leaf['kind']=='INSIDE' and [(F(a)+F(b))/2 for a,b in leaf['box']]==list(map(F,p['xy4']))
                assert ctx.bounds_parsed(point_box(p['xy4']),'4d')[1]<=26
        for variant,params in PLAN['variants'].items():
            obj=read(D/'inputs'/variant/(name+'.json'));x=obj['original']
            assert x['variance']==[params['variance']]*9 and x['bias_domain']==params['bias']
            unchanged=set(x)-{'input_hash','observations','variance','bias_domain'}
            assert all(x[k]==old['original'][k] for k in unchanged)
            if variant!='matched':assert x['observations']==old['original']['observations']
            b=read(D/'bounds'/variant/(name+'.json'));assert b['input_hash']==x['input_hash']
            ctx=A.Context(x,A.event_root(x))
            truth=obj['truth'];limits=ctx.bounds_parsed(point_box(truth),'4d')
            assert (sum(F(l) for l,h in b['true_profiled_terms']),upper(b['true_profiled_terms']))==limits
            assert score(x,truth)==b['true_noise_terms']
            for i,c in enumerate('ps'):
                proof=b['vehicles'][c];pts=proof['points']
                for p in pts:assert ctx.bounds_parsed(point_box(p),'4d')[1]<=26
                projection=lambda pt:tuple(map(F,pt[2*i:2*i+2]))
                dist=lambda a,b:sum((u-v)**2 for u,v in zip(a,b))
                assert dist(projection(pts[0]),projection(pts[1]))/4==F(proof['any_lower2'])
                assert dist(projection(pts[2]),map(F,obj['center'][i]))==F(proof['published_lower2'])
    print('PASS: eight zero-bias midpoint pairs, 24 center/diameter lower bounds and 12 truth tests.')


if __name__=='__main__':
    with tempfile.TemporaryDirectory() as tmp:
        A,_,_=prior.setup(Path(tmp));verify(A)
