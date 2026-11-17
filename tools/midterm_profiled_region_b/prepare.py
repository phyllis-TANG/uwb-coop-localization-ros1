"""Before-freeze input manifest. No search or optimizer."""
from common import *
import numpy as np

def build():
 c=config();legacy=read(ROOT/'docs/research/midterm_nonlinear_region_b/INPUTS.json');det=[]
 for old in legacy:
  p=ROOT/'docs/research/midterm_nonlinear_region_b/results'/(old['id']+'.json.gz')
  det.append(dict(id='legacy_'+old['id'],group='legacy',condition=old['id'],model=old['model'],settings=old['settings'],evaluation=old['evaluation'],legacy_path=str(p.relative_to(ROOT)),legacy_sha=sha(p)))
 def newcase(id,g,b,noise,seed=None):
  truth=c['position_truth']+[b];m=OINPUT.make_model(c['geometries'][g],truth,True,noise)
  assert m['domain']==c['position_domain']+[c['bias_domain']] and m['sigma']==[c['sigma']]*4
  return dict(id=id,group='random' if seed is not None else 'new_deterministic',condition=g+'_b'+b,geometry=g,bias=b,seed=seed,model=m,settings=c['settings'],evaluation=dict(truth=truth,noise_m=noise,mirror_truth=[truth[0],str(-I.D(truth[1])),b] if g=='mirror' else None))
 for g in c['geometries']:
  for b in c['bias_values']:
   for j,noise in enumerate(c['noise_directions']):det.append(newcase(f'd{len(det)-8:02d}',g,b,noise))
 random=[];seedlist=list(range(c['seeds']['start'],c['seeds']['start']+c['seeds']['count']))
 # All 600 inputs frozen before deterministic validation; never adapt to observed results.
 for g in c['geometries']:
  for b in c['bias_values']:
   for seed in seedlist:
    z=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,c['seeds']['stream']]))).standard_normal(4)
    noise=[repr(float(v*float(c['sigma']))) for v in z]
    random.append(newcase(f'r{len(random):04d}',g,b,noise,seed))
 write(DOC/'INPUTS.json.gz',dict(deterministic=det,random=random))
 write(DOC/'SEED_REGISTRY.json',dict(seeds=seedlist,development_seeds=[],stream=c['seeds']['stream'],independence='100 independent seeds per condition; shared across conditions and methods',generator_version=np.__version__))
 return len(det),len(random)
if __name__=='__main__':print(build())
