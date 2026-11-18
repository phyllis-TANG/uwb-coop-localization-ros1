"""Rebuild each certificate and evaluate the original-domain claims without search."""
import csv
import statistics
from formal import D, A, READY, PLAN, read, write, load_module, convert, evaluate, Fraction
from certificate import audit
from geometry import projections
from a_bridge import make_certificate


def inspect(folder):
    job=read(folder/'job.json')
    wall=read(folder/'wall.json')
    row=dict(id=job['id'],method=job['method'],arm=job['arm'],seconds=wall['seconds'],status=wall['status'])
    if wall['status']!='COMPLETE':
        return row
    case,s=job['case'],job['settings']
    x=case['a_input']
    proof=read(folder/'proof.json.gz')
    cert=proof['certificate']
    contract=load_module('verify_published',A/READY['entry'])
    assert proof['original']==x
    if job['arm']=='contracted':
        verdict=contract.check_composite(x,cert)
        y=contract.restricted_input(x,cert['preprocessing'])
        cert=cert['search_certificate']
    else:
        y=x
        verdict=contract.V2.check(x,cert)
    assert y==proof['restricted'] and verdict==proof['verdict']
    tree={'nodes':[], 'termination':'STRICT_EMPTY','queue':[]}
    if y is not None:
        tree=read(folder/'tree.json.gz')
        audit(convert(y),job['method'],s,tree)
        assert make_certificate(dict(case,a_input=y),job['method'],s,tree,proof['regions'])==cert
    regions=projections(case['model'],tree)
    ev=evaluate(case['model'],job['method'],s,tree,case['evaluation'])
    assert regions==proof['regions'] and ev==proof['evaluation']
    if ev['truth_in_declared_domain'] and ev['noise_event'] and ev['noise_event']['holds']:
        assert ev['finite_joint_outer_contains'] and all(ev['finite_car_projection_contains'].values())
        if ev['simultaneous_mirror']:assert ev['simultaneous_mirror']['finite_joint_outer_contains']
    if case.get('id')=='forced_budget':assert tree['queue']
    if case.get('id')=='empty_in_domain':assert not any(r['rectangles'] for r in regions.values())
    if case.get('id')=='domain_closed_contact':assert any(r['boundary_contact'] for r in regions.values())
    row.update(nodes=len(tree['nodes']),queue=len(tree['queue']),termination=tree['termination'],
               evaluation=ev,region={car:{k:v for k,v in region.items() if 'rectangles' not in k} for car,region in regions.items()},
               costs=read(folder/'worker.json'),status='PASS',group=case.get('group'))
    if row['termination']=='RESOLUTION_COMPLETE':
        assert all(all(Fraction(b)-Fraction(a)<=Fraction(t) for (a,b),t in zip(n['box'],s['tolerance'])) for n in tree['nodes'] if n['status']=='UNDECIDED')
    return row


if __name__=='__main__':
    import sys
    stage=sys.argv[1]
    root=D/'runs'/stage
    rows=[]
    for job in sorted(root.glob('*/job.json')):
        try:
            rows.append(inspect(job.parent))
        except Exception as error:
            rows.append(dict(id=job.parent.name,status='REJECTED',reason=repr(error)))
    target={'pilot':14,'deterministic':44,'random':240,'dev':2}[stage]
    valid=len(rows)==target and all(row['status']=='PASS' for row in rows)
    decision=dict(stage=stage,planned=target,rows=rows,expand=False)
    if valid and stage=='pilot':
        totals={a:sum(r['seconds'] for r in rows if r['arm']==a) for a in ['original','contracted']}
        decision.update(seconds=totals,expand=totals['contracted']<totals['original'])
    if valid and stage=='deterministic':
        main={m:[r for r in rows if r['method']==m and r['group']=='main'] for m in ['P4','N4']}
        med={m:statistics.median(r['seconds'] for r in group) for m,group in main.items()}
        decision.update(medians=med,expand=all(len(group)==12 and med[m]<=2 and all(r['termination']=='RESOLUTION_COMPLETE' for r in group) for m,group in main.items()))
    write(root/'decision.json',decision)
    print(stage,len(rows),valid,decision.get('seconds'),decision.get('medians'),decision['expand'])
