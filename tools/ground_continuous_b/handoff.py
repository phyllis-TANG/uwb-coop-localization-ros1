"""Export a recorded B-ground epoch and query frozen A publication semantics."""
import argparse
import json
from fractions import Fraction
from timeline import DOC,load
from report import read
from a_interface import identity,module,A_SHA

def packet(seed,scene,state,car):
    folder=DOC/'runs'/f'{seed}_{scene}'
    r=next(r for r in load(folder/'records.json.gz') if r['t']==state)
    pub=next(p for p in read(folder/'publications.csv') if p['state_time']==str(state) and p['car']==car)
    public={k:pub[k] for k in 'case seed car state_time decision_ready_time AL as_of deadline valid_until published_at input_hash frame mode'.split()}
    public['estimate_xy']=json.loads(pub['estimate_xy'])
    assert public['input_hash']==identity(r['obs'])
    obs=r['obs']; checker=module.verifier('height')
    def q(v):return str(Fraction(v))
    # Honest frame and simultaneous times. Do not rewrite these for Moon acceptance.
    inp=dict(schema_version=checker.VERSION,source_commit=checker.BASE,case_id=pub['case'],frame=pub['frame'],units='m',
             source_times=dict(p=str(state),s=str(state)),heights=dict(zip(('p','s'),map(q,obs['heights']))),
             anchors={f'a{i}':list(map(q,xyz)) for i,xyz in enumerate(obs['anchors'])},
             measurement_ids=checker.K.IDS[:9], observations=[[q(v),q(v)] for v in obs['ranges']],variance=['1/625']*9,
             bias_domain=['-3/5','3/5'],arithmetic_policy=checker.K.POLICY,domain_source='joint_event_26',
             budget=dict(max_nodes=1,max_seconds='1',position_resolution='1/20'))
    # The height schema requires positive budgets; these two fields are unused by
    # this compatibility probe. Ground evidence uses the complete finite product.
    inp['input_hash']=checker.K.digest(inp)
    try:checker.validate(inp)
    except ValueError as exc:rejection=str(exc)
    else:raise AssertionError('Review compatibility because the frozen contract changed')
    assert 'UNSUPPORTED_FRAME_OR_DOMAIN' in rejection
    return dict(A_sha=A_SHA,publication=public,raw=obs,ground_certificate=r['region'],clock_and_radius_record=pub,
                full_A_ground_accepted=False,A_height_validation=rejection)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('seed',type=int);p.add_argument('scene');p.add_argument('state',type=int);p.add_argument('car',choices=['p','s'])
    a=p.parse_args();print(json.dumps(packet(a.seed,a.scene,a.state,a.car),separators=(',',':')))
