import copy
import gzip
import json
import numpy as np
import dynamic_compare as d

checks={}
for case in ('A1','B1'):
    base=d.HERE/case
    for path,expected in d.read(base/'INPUT_LOCK.json').items():
        assert d.sha(path)==expected, path
    with gzip.open(base/'bins.jsonl.gz','rt',encoding='utf-8') as f:
        bins=[json.loads(l) for l in f]
    cfg=d.read(base/'config.json')
    b=bins[0]; prior=d.core.initial(cfg); x=prior.point.copy(); x[0]+=.13
    args=([b['second']],[b['local']],[b['wall']],[b['peer']],[],cfg,prior,True)
    full=d.core.Objective(*args); weighted=d.WeightedObjective(*args)
    r,j=full.evaluate(x); rw,jw=weighted.evaluate(x)
    assert len(full.peers)==1
    assert np.array_equal(r[:-1],rw[:-1]) and np.array_equal(j[:-1],jw[:-1])
    assert np.array_equal(r[-1:]*.5,rw[-1:]) and np.array_equal(j[-1:]*.5,jw[-1:])
    # Cached evaluation must not shrink repeatedly.
    assert np.array_equal(weighted.evaluate(x)[0],rw)
    eps=1e-6
    fd=np.column_stack([(weighted.fun(x+np.eye(8)[k]*eps)-weighted.fun(x-np.eye(8)[k]*eps))/(2*eps) for k in range(8)])
    err=float(np.max(np.abs(fd-jw))); assert err<1e-5,err
    assert d.weighted_update.__globals__['Objective'] is d.WeightedObjective
    assert d.weighted_update.__globals__['eliminate'] is d.weighted_eliminate
    assert d.weighted_eliminate.__globals__['Objective'] is d.WeightedObjective
    assert all(v.get('dependency_max_ns',v['cutoff_ns'])<=v['cutoff_ns'] for v in bins)
    # Cross the first fixed-lag marginalization using real cached inputs.
    g=d.WeightedGraph(cfg)
    for b in bins[:24]:
        g.next_intervals=b['intervals']; result=g.update(b['second'],b['local'],b['wall'],b['peer'])
    assert g.marginalizations==3
    assert np.isfinite(np.array(result['pose'])).all()
    checks[case]={'input_locks':'passed','weighted_rows_and_cache':'passed','weighted_jacobian_max_error':err,'short_real_prefix_frames':24,'marginalizations':g.marginalizations,'last_status':result['status'],'interpretation':'implementation check only, no accuracy inference'}
d.write(d.HERE/'ADAPTER_CHECK.json',checks)
print(json.dumps(checks),flush=True)
