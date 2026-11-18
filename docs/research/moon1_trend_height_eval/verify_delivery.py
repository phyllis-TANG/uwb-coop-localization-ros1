#!/usr/bin/env python3
"""Post-freeze read-only audit wrapper. It never runs a real optimizer or changes the frozen model."""
import argparse,sys
from pathlib import Path
import scipy.optimize as opt
real_calls=[]
def forbid(*a,**kw):
 real_calls.append(1)
 raise RuntimeError('Real optimizer forbidden during independent delivery verification')
opt.least_squares=forbid
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/moon1_trend_height_eval'))
from tcommon import read,write,csvwrite,Evidence,np
from tmodel import problem
from tverify import evaluate
from tchecks import run as math_checks

p=argparse.ArgumentParser();p.add_argument('--input',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
evaluate(a.input,a.out/'metrics');math_checks(a.out/'math')
e=Evidence(a.input);plan=read(a.input/'PLAN.json');index={(i['window'],i['seed'],i['height_sigma_m'],i['condition']):i['id'] for i in plan};rows=[]
for item in plan:
 c=item['condition']
 if c not in ['constant03','ramp03']:continue
 base=index[(item['window'],item['seed'],item['height_sigma_m'],'normal')];uid=item['id']
 for method in (['M2','M3'] if c=='constant03' else ['M3']):
  o0=e.get('measurements/'+base+'.json');o1=e.get('measurements/'+uid+'.json');f,q,_=problem(o0,method);g,_,_=problem(o1,method);shift=q.copy()
  if c=='constant03':shift[24]+=.3
  else:shift[24]+=.15;shift[25]+=.3
  r,j=f(q);s,k=g(shift);err=float(np.max(abs(r-s)));je=float(np.max(abs(j-k)));assert err<2e-12 and je<1e-12
  z0=e.get('estimates/'+base+'-'+method+'/FINAL.json')['estimate'];z1=e.get('estimates/'+uid+'-'+method+'/FINAL.json')['estimate']
  change=None
  if z0 is not None and z1 is not None:change=float(np.max(abs(np.array(z0[:24])-np.array(z1[:24]))))
  rows.append(dict(unit=uid,base_unit=base,method=method,condition=c,height_sigma_m=item['height_sigma_m'],window=item['window'],seed=item['seed'],objective_residual_identity_error=err,jacobian_identity_error=je,observed_endpoint_xy_max_difference_m=change))
csvwrite(a.out/'MATCHED_IDENTITIES.csv',rows)
assert len(real_calls)==0
write(a.out/'INDEPENDENT_CHECK.json',dict(passed=True,real_optimizer_calls=0,guard_active=True,identity_cases=len(rows),max_identity_residual_error=max(r['objective_residual_identity_error'] for r in rows),max_identity_jacobian_error=max(r['jacobian_identity_error'] for r in rows),wrapper_scope='post-freeze verification only; frozen solver and summary code unchanged'))
print('PASS independent delivery verification, real optimizer calls = 0')
