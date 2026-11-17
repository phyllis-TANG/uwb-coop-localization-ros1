"""Independent QR/noise-response and full point/seed arithmetic readback; no optimizer."""
import argparse,csv,collections
from regions import *
def close(a,b):
 if not np.allclose(a,b,rtol=2e-7,atol=2e-10,equal_nan=True):raise AssertionError('Numeric mismatch')
def verify(out):
 c=config();src=source();z=np.load(out/'LOCAL_MATRICES.npz');ids=z['id'].tolist();assert ids==[r['id'] for r in src];lookup={x:i for i,x in enumerate(ids)};count=0
 for i,v in enumerate(src):
  x=z['state'][i];n=25 if v['method']=='B2' else 24;x=x[:n];u=v['input'];m=v['method']
  if not np.isfinite(x).all():continue
  for vi,view in enumerate(c['views']):
   point=OLD.M.reference(u,m) if view=='oracle_truth_GN' else x;r,j=OLD.M.objective(u,m,point)
   if z['status'][i,vi]!='AVAILABLE':continue
   if view=='endpoint_exact':
    h=OLD.exact_hessian(u,m,point);G=np.linalg.solve(h,j[:-4].T);rhs=np.zeros((n,4));rhs[:4]=np.eye(4)/u['obs']['prior_sigma']**2;T=np.linalg.solve(h,rhs);cur=None
   else:
    # Independent unscaled least-squares operator, not the frozen scaled inverse formula.
    K=np.linalg.lstsq(j,np.eye(len(r)),rcond=c['rank_relative'])[0];G=K[:,:-4];T=K[:,-4:]/u['obs']['prior_sigma'];cur=K@K.T
   C=G@G.T
   for t in range(6):
    for car in range(2):
     sl=slice(t*4+car*2,t*4+car*2+2);close(C[sl,sl],z['P'][i,vi,t,car]);close(T[sl],z['B'][i,vi,t,car])
     if cur is not None:close(cur[sl,sl],z['curvature'][i,vi,t,car])
   count+=1
 grouped=collections.defaultdict(list);points=0;q=float(chi2.ppf(c['confidence'],2))
 with gzip.open(out/'POINTS.csv.gz','rt') as f:
  for r in csv.DictReader(f):
   i=lookup[r['id']];vi=c['views'].index(r['view']);t=int(r['epoch']);car=int(r['car'])-1;rho=float(r['rho']);v=src[i];u=v['input'];x=z['state'][i,:24].reshape(6,2,2);err=x[t,car]-u['truth'][t][car];close(err,[float(r['error_x']),float(r['error_y'])]);normcenter=np.linalg.norm(np.array(u['obs']['prior_center'])-np.array(u['truth'])[0].ravel());close(normcenter,float(r['center_error_norm']))
   if r['kind']!='curvature_ellipse':assert (r['in_set']=='True')==bool(normcenter<=rho+1e-12)
   if r['reason']=='AVAILABLE':
    P=z['curvature'][i,vi,t,car] if r['kind']=='curvature_ellipse' else z['P'][i,vi,t,car];B=z['B'][i,vi,t,car];ev=np.linalg.eigvalsh(P);nr=np.sqrt(q*ev[-1]);br=rho*np.linalg.norm(B,2);radius=nr+br;ellipse=r['kind'].endswith('ellipse');area=np.pi*q*np.sqrt(np.linalg.det(P)) if ellipse else np.pi*radius**2;cover=(err@np.linalg.solve(P,err)<=q) if ellipse else (np.linalg.norm(err)<=radius)
    close(float(r['radius']),nr if ellipse else radius);close(float(r['area']),area);assert (r['covered']=='True')==bool(cover)
   grouped[(r['id'],r['car'],r['view'],r['kind'],r['rho'])].append(r);points+=1
 seeds=0
 with gzip.open(out/'PER_SEED.csv.gz','rt') as f:
  for r in csv.DictReader(f):
   ps=grouped[(r['id'],r['car'],r['view'],r['kind'],r['rho'])];assert len(ps)==6;valid=[v for v in ps if v['reason']=='AVAILABLE'];assert int(r['available_points'])==len(valid) and int(r['covered_points'])==sum(v['covered']=='True' for v in valid)
   if len(valid)==6:close(float(r['coverage_point']),sum(v['covered']=='True' for v in valid)/6);assert (r['all_covered']=='True')==all(v['covered']=='True' for v in valid)
   if valid:close(float(r['radius_mean']),np.mean([float(v['radius']) for v in valid]));close(float(r['area_mean']),np.mean([float(v['area']) for v in valid]))
   seeds+=1
 return dict(status='PASS',unique_endpoints=len(src),independent_local_matrix_checks=count,point_rows=points,seed_rows=seeds,formal_runs=0,real_optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=verify(a.results);save(a.out,r);print(json.dumps(r))
