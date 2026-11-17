"""Independent QR / eigenbasis readback; no optimizer and no new observations."""
from common import *
import argparse,collections

def main(src,summary,out):
 before=source_check();vectors=list(records(src/'VECTORS.jsonl.gz'));stats=readcsv(src/'DECOMPOSITION.csv.gz');assert len(vectors)==len(stats)==1800
 ai={r['id']:r['input'] for r in records(A/'INPUTS.jsonl.gz')};bi={r['value']['item']['id']:r['value']['input'] for r in records(B/'EVIDENCE.jsonl.gz') if r['type']=='UNIT'};qrmax=0.;identitymax=0.
 for v,row in zip(vectors,stats):
  assert (v['batch'],v['id'],v['method'],v['init'])==tuple(row[k] for k in ['batch','id','method','init'])
  vv=np.array(v['terms']);components=list(vv)+[vv.sum(0),np.array(v['difference']),np.array(v['nonlinear_delta']),np.array(v['affine_delta'])]
  for name,component in zip(['gradient','remainder','jacobian','sum','difference','nonlinear_error','affine_error'],components):
   assert abs(float(row[name+'_position_rms'])-np.linalg.norm(component[:24])/np.sqrt(12))<1e-12
   if v['method']=='B2':assert abs(float(row[name+'_bias_abs'])-abs(component[-1]))<1e-12
   else:assert row[name+'_bias_abs']==''
  u=(ai if v['batch']=='PR119' else bi)[v['id']];x0=np.array(v['reference']);dn=np.array(v['nonlinear_delta']);r0,j0=M.objective(u,v['method'],x0);rn,jn=M.objective(u,v['method'],x0+dn);Q,R=np.linalg.qr(j0,mode='reduced');dl=np.linalg.solve(R,-Q.T@r0);eta=rn-r0-j0@dn
  rhs=[jn.T@rn,-j0.T@eta,-(jn-j0).T@rn];vs=np.array([np.linalg.solve(R,np.linalg.solve(R.T,b)) for b in rhs]);qrmax=max(qrmax,float(np.max(abs(vs-v['terms']))));identitymax=max(identitymax,float(np.max(abs(vs.sum(0)-(dn-dl)))))
 assert qrmax<1e-8 and identitymax<1e-8
 # Recompute historical chosen identities and full/accepted endpoint groups.
 units=collections.defaultdict(list)
 for ep in records(A/'ENDPOINTS.jsonl.gz'):units[ep['id'],ep['method']].append(dict(init=ep['init'],final=ep['stages']['P1']))
 selections=json.loads((A/'readback/SELECTION.json').read_text())
 for z in selections:
  candidates=units[z['id'],z['method']];accept=[v for v in candidates if v['final']['accepted']];best=min(accept,key=lambda v:(v['final']['cost'],v['init']));assert best['init']==z['selected_init'];assert len(L.groups(candidates,z['method']))==z['finite_groups'];assert len(L.groups(candidates,z['method'],True))==z['accepted_groups']
 mats={(r['id'],r['epoch'],r['car']):r for r in records(src/'REGION_MATRICES.jsonl.gz')};points=readcsv(src/'REGIONS.csv.gz');groups=collections.defaultdict(list);checked=0;support_rejections=collections.Counter();radiusmax=0.
 for p in points:
  m=mats[p['id'],int(p['epoch']),int(p['car'])];P=np.array(m['covariance']);e=np.array([float(p['error_x']),float(p['error_y'])]);rank=m['rank'];Bmat=np.array(m['bias_gain']);ev,V=np.linalg.eigh(P);Q=np.array(m['support']);a=float(p['block_alpha']);crit=chi2.ppf(1-a,rank) if rank else 0
  # Independent eigendecomposition, with separately asserted structural support.
  if rank==1:
   assert np.linalg.norm(P-Q@(Q.T@P@Q)@Q.T)<1e-12;perp=np.linalg.norm(e-Q@(Q.T@e));q=float((e@Q[:,0])**2/(Q[:,0]@P@Q[:,0]))
  elif rank==2:perp=0.;q=float(np.sum((V.T@e)**2/ev))
  else:perp=np.linalg.norm(e);q=0.
  rad=np.sqrt(crit*ev[-1])+(float(p['rho'])*np.linalg.svd(Bmat,compute_uv=False)[0] if p['kind']=='outer_circle' else 0)
  hit=perp<=1e-10 and q<=crit+100*np.finfo(float).eps*max(1,crit) if p['kind']=='noise_support' else np.linalg.norm(e)<=rad+100*np.finfo(float).eps*max(1,rad)
  assert (p['covered']=='True')==hit,(p,hit);radiusmax=max(radiusmax,abs(rad-float(p['radius'])));checked+=1
  if p['kind']=='noise_support' and perp>1e-10:support_rejections[p['model']+'/'+p['scope']]+=1
  groups[tuple(p[k] for k in ['id','model','scope','kind','rho'])].append(p)
 # Independent full 12-block denominator & all-hit recomputation for every model, alpha and rho.
 checked_seed=0
 for r in readcsv(summary/'REGION_SEEDS.csv.gz'):
  ps=groups[tuple(r[k] for k in ['id','model','scope','kind','rho'])];ps=[p for p in ps if r['car']=='0' or p['car']==r['car']];assert len(ps)==int(r['planned_points']);av=[p for p in ps if p['reason']=='AVAILABLE'];assert len(av)==int(r['available_points']);assert sum(p['covered']=='True' for p in av)==int(r['covered_points']);assert (r['all_covered']=='True')==(len(av)==len(ps) and all(p['covered']=='True' for p in av));checked_seed+=1
 historical=collections.Counter()
 with gzip.open(B/'POINTS.csv.gz','rt') as f:
  for p in csv.DictReader(f):
   if p['reason']!='AVAILABLE':historical[p['reason']]+=1
 assert sum(historical.values())==4800
 result=dict(status='PASS',endpoints=1800,independent_qr_term_max=qrmax,independent_qr_identity_max=identitymax,selection_and_group_units=len(selections),independent_region_points=checked,independent_region_seed_rows=checked_seed,independent_radius_max=radiusmax,support_rejections=dict(support_rejections),historical_unavailable_unchanged=dict(historical),source_files_before=before,source_files_after=source_check(),**CALLS)
 save(out,result);print(result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--summary',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();protect();main(a.input,a.summary,a.out)
