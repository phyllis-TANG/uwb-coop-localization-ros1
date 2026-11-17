"""Independent no-optimizer verification of archive identities, direct QR and saved regions."""
import argparse,csv,collections
from common import *
from analyze import from_archive

def close(a,b):assert np.allclose(a,b,atol=2e-9,rtol=2e-7,equal_nan=True),'numeric mismatch'
def verify(archive,results):
 c=config();units=[];meta=None;calls=0;stages=0
 for entry in from_archive(archive):
  if entry['type']=='META':meta=entry['value'];assert meta['config']==c and meta['sources']==hashes();continue
  v=entry['value'];u=v['input'];item=v['item'];prev=None
  codehash=REC.digest({str(Path(meta['execution_root'])/p):h for p,h in meta['sources'].items()})
  for stage in ['P0','P1']:
   expected=stage_identity(c,item,u,stage,prev);expected['code_sha256']=codehash;s=v['stages'][stage];a=s['attempt'];r=s['result'];d=s['done'];assert a['identity']==expected and r['identity']==expected and a['attempt_id']==r['attempt_id']
   assert r['payload_sha256']==digest(r['payload']) and d==dict(identity=expected,attempt_id=a['attempt_id'],result_sha256=digest(r));assert r['payload']['execution']=='RETURNED';prev=r['payload']['value'];stages+=1;calls+=prev['optimizer_invocations'] or 0
   if prev['usable_estimate']:
    x=np.array(prev['estimate']);rr,j=M.objective(u,'B2',x);close(rr,prev['residual']);close(j,prev['jacobian']);close(rr@rr/2,prev['cost']);close(max(abs(j.T@rr)),prev['gradient_inf']);e=x[:24].reshape(6,2,2)-u['truth'];close(np.mean(np.sum(e*e,axis=2),axis=0),prev['position_mse'])
  lin=v['linear'];x0=M.reference(u,'B2');rr,j=M.objective(u,'B2',x0);K=np.linalg.lstsq(j,np.eye(len(rr)),rcond=None)[0];direct=x0-K@rr;close(direct,lin['estimate']);close(K[:,:-4]@K[:,:-4].T,lin['covariance']);delta=np.array(u['obs']['prior_center'])-x0[:4];close(K[:,-4:]@delta/u['obs']['prior_sigma'],lin['mean']);units.append(v)
 with np.load(results/'LOCAL_MATRICES.npz') as z:arrays={k:z[k] for k in z.files}
 assert arrays['id'].tolist()==[v['item']['id'] for v in units];index={v['item']['id']:k for k,v in enumerate(units)};matrixchecks=0
 for i,v in enumerate(units):
  u=v['input'];lin=v['linear'];nl=v['stages']['P1']['result']['payload']['value']
  for mi,(model,r) in enumerate([('NL',nl),('LINEAR',lin)]):
   if not r['usable_estimate']:continue
   for vi,view in enumerate(['GN','exact']):
    if arrays['status'][i,mi,vi]!='AVAILABLE':continue
    point=np.array(r['estimate']) if model=='NL' else np.array(lin['reference']);rr,j=M.objective(u,'B2',point)
    if model=='NL' and view=='exact':
     H=R.OLD.exact_hessian(u,'B2',point);G=np.linalg.solve(H,j[:-4].T);rhs=np.zeros((25,4));rhs[:4]=np.eye(4)/u['obs']['prior_sigma']**2;T=np.linalg.solve(H,rhs);cur=None
    else:
     K=np.linalg.lstsq(j,np.eye(len(rr)),rcond=None)[0];G=K[:,:-4];T=K[:,-4:]/u['obs']['prior_sigma'];cur=K@K.T
    C=G@G.T
    for t in range(6):
     for car in range(2):
      sl=slice(t*4+car*2,t*4+car*2+2);close(C[sl,sl],arrays['P'][i,mi,vi,t,car]);close(T[sl],arrays['B'][i,mi,vi,t,car])
      if view=='GN':close(cur[sl,sl],arrays['curvature'][i,mi,vi,t,car])
    matrixchecks+=1
 grouped=collections.defaultdict(list);points=0
 with gzip.open(results/'POINTS.csv.gz','rt') as f:
  for p in csv.DictReader(f):
   i=index[p['id']];v=units[i];mi=0 if p['model']=='NL' else 1;vi=0 if p['view']=='GN' else 1;t=int(p['epoch']);car=int(p['car'])-1;rho=float(p['rho']);r=v['stages']['P1']['result']['payload']['value'] if mi==0 else v['linear'];u=v['input'];delta=np.array(u['obs']['prior_center'])-np.array(u['truth'])[0].ravel()
   if p['kind']!='curvature_ellipse':assert (p['in_set']=='True')==bool(np.linalg.norm(delta)<=rho+c['boundary_tolerance_m'])
   if r['usable_estimate']:
    error=np.array(r['estimate'][:24]).reshape(6,2,2)[t,car]-u['truth'][t][car];close(error,[float(p['error_x']),float(p['error_y'])])
    if p['reason']=='AVAILABLE':
     P=arrays['curvature'][i,mi,vi,t,car] if p['kind']=='curvature_ellipse' else arrays['P'][i,mi,vi,t,car];B=arrays['B'][i,mi,vi,t,car];eigs=np.linalg.eigvalsh(P);q95=R.quantile(.95);radius=np.sqrt(q95*eigs[-1])+rho*np.linalg.norm(B,2);ellipse=p['kind'].endswith('ellipse');area=np.pi*q95*np.sqrt(np.linalg.det(P)) if ellipse else np.pi*radius**2;cover=error@np.linalg.solve(P,error)<=q95 if ellipse else np.linalg.norm(error)<=radius;close(float(p['radius']),radius);close(float(p['area']),area);assert (p['covered']=='True')==bool(cover)
   grouped[(p['id'],p['model'],p['view'],p['kind'],p['rho'],p['car'])].append(p);points+=1
 nseed=0
 with gzip.open(results/'PER_SEED.csv.gz','rt') as f:
  for r in csv.DictReader(f):
   ps=grouped[tuple(r[k] for k in ['id','model','view','kind','rho','car'])];assert len(ps)==6;av=[p for p in ps if p['reason']=='AVAILABLE'];assert len(av)==int(r['available_points']) and sum(p['covered']=='True' for p in av)==int(r['covered_points']);nseed+=1
 return dict(status='PASS',units=len(units),stages=stages,persisted_optimizer_calls=calls,independent_linear_solutions=len(units),local_matrices=matrixchecks,point_rows=points,per_seed_rows=nseed,verification_optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=verify(a.archive,a.results);save(a.out,z);print(json.dumps(z))
