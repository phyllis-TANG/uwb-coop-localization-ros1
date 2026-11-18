"""Zero-optimizer readback and deterministic diagnostic tables/plots."""
import csv,sys
from common import *
from model import objective
from two_car_updated_comparison import rotation

def inspect(out):
 out=Path(out);run=read(out/'RUN.json');cfg=read(DOC/'CONFIG.json');rows=[];pair=[]
 for p,h in run['freeze']['hashes'].items():assert digest(ROOT/p)==h,p
 attempts=list((out/'attempts').glob('*.json'));assert len(attempts)==6
 assert read(out/'COMPLETE.json')['optimizer_calls']==6
 for case in cfg['cases']:
  o=read(out/'measurements'/f'{case}.json');ant={}
  for method in cfg['methods']:
   name=case+'_'+method;a=read(out/'attempts'/f'{name}.json');assert a['input_sha256']==digest(out/'measurements'/f'{case}.json')
   e=read(out/'estimates'/f'{name}.json')
   if 'failure' in e:rows.append({'case':case,'method':method,'failure':e['failure']});continue
   f=objective(o,method=='joint');q=np.array(e['x']);r,j=f.evaluate(q);g=j.T@r
   np.testing.assert_allclose(r,e['residual'],atol=1e-12,rtol=0)
   np.testing.assert_allclose(j,e['jacobian'],atol=1e-12,rtol=0)
   assert abs(float(r@r/2)-e['cost'])<1e-10
   assert abs(float(max(abs(g)))-e['gradient_inf'])<1e-10
   assert e['stationary_1e_5']==bool(max(abs(g))<=1e-5)
   # Remove three boundary prior rows per car for separate data-only rank.
   keep=np.ones(len(r),bool);offset=0
   for part in f.parts:
    keep[offset:offset+3]=False;offset+=3*f.n+len(part.index)
   s=q.reshape(2,len(o['times']),3);ant[method]=[]
   for ci,c in enumerate(['car1','car2']):
    lever=o['cars'][c]['model']['base_to_antenna_body_xy_m']
    ant[method].append(s[ci,:,:2]+np.array([rotation(t)@lever for t in s[ci,:,2]]))
   rows.append({k:e[k] for k in ['case','method','cost','gradient_inf','scipy_success','stationary_1e_5','nfev','wall_factors','peer_factors','rank_with_prior'] }|{'data_only_rank':int(np.linalg.matrix_rank(j[keep])),'state_dim':len(q)})
  if len(ant)==2:
   for ci,c in enumerate(['car1','car2']):
    delta=np.linalg.norm(ant['joint'][ci]-ant['independent'][ci],axis=1);local=np.array(o['cars'][c]['local'])
    pair.append({'case':case,'car':c,'joint_minus_independent_rms_displacement_m':float(np.sqrt(np.mean(delta**2))),'max_displacement_m':float(max(delta)),'recorded_odom_path_m':float(np.linalg.norm(np.diff(local[:,:2],axis=0),axis=1).sum())})
 return rows,pair

def deliver(out,dest):
 rows,pair=inspect(out);dest=Path(dest);dest.mkdir(parents=True,exist_ok=True)
 for name,table in [('NUMERICS.csv',rows),('METHOD_CHANGES.csv',pair)]:
  fields=list(dict.fromkeys(k for row in table for k in row))
  with (dest/name).open('x',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(table)
 write(dest/'READBACK.json',{'passed':True,'runs':len(rows),'optimizer_calls_in_batch':6,'optimizer_calls_in_readback':0,'formal_runs':0,'finite_runs':sum('failure' not in r for r in rows),'stationary_1e_5':sum(r.get('stationary_1e_5',False) for r in rows)})
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,axes=plt.subplots(1,3,figsize=(13,4),constrained_layout=True)
 for ax,case in zip(axes,read(DOC/'CONFIG.json')['cases']):
  o=read(Path(out)/'measurements'/f'{case}.json')
  for method,style in [('independent','--'),('joint','-')]:
   e=read(Path(out)/'estimates'/f'{case}_{method}.json')
   if 'x' not in e:continue
   s=np.array(e['x']).reshape(2,20,3)
   for ci,c in enumerate(['car1','car2']):
    lever=o['cars'][c]['model']['base_to_antenna_body_xy_m'];xy=s[ci,:,:2]+np.array([rotation(t)@lever for t in s[ci,:,2]])
    ax.plot(xy[:,0],xy[:,1],style,label=c+' '+method,color=['tab:blue','tab:orange'][ci]);ax.scatter(*xy[0],s=15,color=['tab:blue','tab:orange'][ci])
  ax.set(title=case+' receipt 1-20 s',xlabel='room x (m)',ylabel='room y (m)');ax.axis('equal');ax.grid(alpha=.3);ax.legend(fontsize=7)
 fig.suptitle('Field antenna estimates under historical geometry assumptions; no trajectory truth');fig.savefig(dest/'trajectories.png',dpi=150);plt.close(fig)
if __name__=='__main__':
 if len(sys.argv)==3:deliver(*sys.argv[1:])
 else:print(__import__('json').dumps(inspect(sys.argv[1]),indent=2))
