"""Configuration, independent objective and affine diagnostics; no optimizer import."""
import gzip,hashlib,importlib.util,itertools,json,platform
from pathlib import Path
import numpy as np,scipy
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/research/midterm_inset_validation_b'
def module(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
R=module('frozen_regions','tools/midterm_bias_region_b/regions.py');M=R.OLD.M
REC=module('frozen_recovery','tools/midterm_bias_region_b/recovery.py')
canonical=R.canonical;digest=R.digest;save=R.save;clean=R.OLD.clean

def read(p):
 p=Path(p)
 with gzip.open(p,'rt') if p.suffix=='.gz' else p.open() as f:return json.load(f)
def config():return read(DOC/'CONFIG.json')
def versions():return dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__)
def sources():
 paths=list((ROOT/'tools/midterm_inset_validation_b').glob('*.py'))
 paths += [ROOT/p for p in ['tools/midterm_bias_region_b/recovery.py','tools/midterm_bias_region_b/regions.py','tools/midterm_prior_propagation_b/model.py','tools/midterm_prior_mechanism_b/math_model.py','tools/midterm_simulation_validation/core.py','tools/midterm_simulation_s2/prototype.py','tools/midterm_simulation_phase1/identifiability.py']]
 return sorted(paths)
def hashes():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources()}
def conditions(c):
 return [dict(id=f'i{k:02}',geometry=g,motion='static',kind='peer',bias_m=.3,prior='survey_core' if s==.5 else 'survey_strong',prior_sigma=s,delta_m=d,mechanism='fixed_inset') for k,(g,s,d) in enumerate(itertools.product(c['matrix']['geometries'],c['matrix']['prior_sigmas'],c['matrix']['deltas_m']))]
def tasks(c,mode):return [dict(id=f"{q['id']}-s{seed}",condition=q,seed=seed) for q in conditions(c) for seed in c['seeds'][mode]]
def affine(u,c):
 """Same whitened residual linearized at [true positions, true b], direct scaled SVD."""
 x0=M.reference(u,'B2');r,j=M.objective(u,'B2',x0);D=np.r_[np.ones(24),.1];U,s,vt=np.linalg.svd(j*D,full_matrices=False);rank=int(sum(s>s[0]*c['region']['rank_relative']))
 out=dict(estimate=None,usable_estimate=False,accepted=False,category='RANK_DEFICIENT',rank=rank,reference=x0.tolist(),jacobian=j.tolist(),normal_inf=None,mean=None,covariance=None,residual=None,cost=None)
 if rank<25:return out
 K=(D[:,None]*vt.T/s)@U.T;dx=-K@r;estimate=x0+dx;rr=r+j@dx;G=K[:,:-4];T=K[:,-4:]/u['obs']['prior_sigma'];delta=np.array(u['obs']['prior_center'])-x0[:4];mu=T@delta;C=G@G.T;normal=float(max(abs(j.T@rr)))
 # Independent unscaled QR/SVD least-squares and explicit noise/center RHS.
 independent=np.linalg.lstsq(j,-r,rcond=None)[0];eps=np.r_[np.array(u['noise']['range'])/u['obs']['range_sigma'],np.array(u['noise']['motion'])/u['obs']['motion_sigma']];pred=G@eps+mu
 err=float(max(abs(dx-pred)));qr=float(max(abs(dx-independent)))
 if err>c['checks']['affine_state_abs'] or qr>c['checks']['affine_state_abs'] or normal>c['checks']['normal_equation_inf']:raise ArithmeticError(f'affine gate failed: {err}, {qr}, {normal}')
 out.update(estimate=estimate.tolist(),usable_estimate=True,accepted=True,category='DIRECT_ACCEPTED',normal_inf=normal,mean=mu.tolist(),covariance=C.tolist(),T=T.tolist(),G=G.tolist(),residual=rr.tolist(),cost=float(rr@rr/2),noise_identity_max=err,independent_solve_max=qr)
 return clean(out)
def stage_identity(c,item,u,stage,previous=None):
 consumed=dict(input=u,actual_start=u['obs']['start']+[c['frozen_model']['initialization']['bias_m']] if stage=='P0' else (None if previous is None else previous.get('estimate')),P0_endpoint=previous if stage=='P1' else None)
 return REC.identity(item['id'],'B2',stage,consumed,dict(config=c,dependencies=versions()),sources())
