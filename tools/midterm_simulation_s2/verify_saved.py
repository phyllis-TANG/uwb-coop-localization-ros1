"""Recheck committed evidence without solving or modifying outputs."""
import gzip,json,hashlib
from pathlib import Path
import numpy as np
from prototype import ROOT,generate,problem,digest
P=ROOT/'docs/research/midterm_simulation_s2'
cfg=json.loads((P/'CONFIG.json').read_text())
for p,h in json.loads((P/'SOURCE_LOCK.json').read_text()).items():assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h
u=[json.loads(x) for x in gzip.open(P/'UNITS.jsonl.gz','rt')]
key=lambda x:tuple(x[k] for k in ['profile','seed','geometry','motion','kind','bias_m'])
lookup={key(x):x for x in u};max_b3=0.;max_target=0.
for unit in u:
 nominal=lookup[(*key(unit)[:-1],0.)]
 obs,truth,corr,noise=generate(unit['geometry'],unit['motion'],unit['kind'],unit['bias_m'],unit['profile'],unit['seed'],cfg)
 no,_,_,_=generate(unit['geometry'],unit['motion'],unit['kind'],0.,unit['profile'],unit['seed'],cfg)
 assert digest(obs)==unit['observation_sha256']
 _,_,r3=problem(obs,'B3',corr);_,_,r1=problem(no,'B1')
 max_target=max(max_target,float(np.max(np.abs(np.array(r3['ranges'])-r1['ranges']))))
 max_b3=max(max_b3,float(np.max(np.abs(np.array(unit['results'][3]['estimate'])-nominal['results'][1]['estimate']))))
 assert unit['noise_sha256']==nominal['noise_sha256']
# Paired noisy prior profiles preserve every range and motion sample, change only declared center/start.
for unit in u:
 if unit['profile']=='noisy_biased_prior':
  peer=lookup[('noisy_unbiased_prior',*key(unit)[1:])]
  assert unit['noise_sha256']==peer['noise_sha256']
assert max_target<1e-14 and max_b3<cfg['tests']['numeric_equivalence_abs_tol']
# Complete weighted factor Jacobian, including prior and displacement, not just raw range rows.
o,_,corr,_=generate('good','turn','wall',.3,'noisy_biased_prior',cfg['development_seeds'][0],cfg)
f,q,_=problem(o,'B2');j=f(q)[1]
fd=np.column_stack([(f(q+np.eye(25)[i]*1e-6)[0]-f(q-np.eye(25)[i]*1e-6)[0])/2e-6 for i in range(25)])
# Whitened FD error scales raw tolerance by maximum whitening weight (50).
err=float(np.max(np.abs(fd-j)));assert err<cfg['tests']['jacobian_abs_tol']/min(cfg['range_sigma_m'],cfg['motion_sigma_m'],cfg['position_prior_sigma_m'])
print(json.dumps(dict(status='PASS',units=len(u),B3_vs_nominal_B1_max_coordinate_delta_m=max_b3,B3_target_max_delta_m=max_target,weighted_factor_jacobian_max_error=err,formal_runs=0),indent=2))
