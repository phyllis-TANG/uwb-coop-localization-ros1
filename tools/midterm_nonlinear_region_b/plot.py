"""Read-only projections and explicitly uncertified local affine comparisons."""
import argparse,json,gzip,csv
from pathlib import Path
from fractions import Fraction as F
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.patches import Rectangle,Ellipse

def numeric(v):return float(F(v))
def affine_reference(r):
 z=r['metrics'];m=r['model'];q=float(r['settings']['q'])
 if z['center'] is None:return dict(status='NO_OUTPUT_CENTER',optimizer_calls=0)
 x=np.array([numeric(t) for t in z['center']]+([0.] if m['unknown_bias'] else []));anchors=np.array(m['anchors'],float);v=x[:2]-anchors;dist=np.linalg.norm(v,axis=1)
 if np.any(dist==0):return dict(status='NONDIFFERENTIABLE',optimizer_calls=0)
 h=dist.copy();h[3]+=x[2] if m['unknown_bias'] else float(m['known_bias']);J=v/dist[:,None]
 if m['unknown_bias']:J=np.c_[J,[0,0,0,1]]
 sigma=np.array(m['sigma'],float);J/=sigma[:,None];y=np.array([(numeric(a)+numeric(b))/2 for a,b in m['observations']]);res=(y-h)/sigma
 d,_,rank,_=np.linalg.lstsq(J,res,rcond=1e-12);remaining=q-float(np.sum((res-J@d)**2));answer=dict(status='AVAILABLE',linearization=x.tolist(),center=(x+d).tolist(),rank=int(rank),remaining_budget=remaining,optimizer_calls=0)
 if rank<len(x):answer['status']='RANK_DEFICIENT';return answer
 if remaining<0:answer['status']='AFFINE_EMPTY';return answer
 K=np.linalg.lstsq(J,np.eye(4),rcond=1e-12)[0];answer['projected_shape']=(remaining*(K@K.T)[:2,:2]).tolist();return answer

def main(src,out):
 out.mkdir(parents=True,exist_ok=False);rows=[];local=[]
 for f in sorted(src.glob('*.json.gz')):
  with gzip.open(f,'rt') as h:r=json.load(h)
  res=r['result'];z=r['metrics'];comp=affine_reference(r);local.append(dict(case=r['id'],**comp));fig,axes=plt.subplots(1,2,figsize=(11,5))
  for ax in axes:
   for status,color in [('INSIDE','#4daf4a'),('UNDECIDED','#ffb347'),('PENDING','#a78bfa'),('NUMERICAL_UNDECIDED','#e41a1c')]:
    rects=[]
    for n in res['nodes']:
     if n['status']==status:
      b=n['box'];x,y=numeric(b[0][0]),numeric(b[1][0]);rects.append(Rectangle((x,y),numeric(b[0][1])-x,numeric(b[1][1])-y))
    if rects:ax.add_collection(PatchCollection(rects,facecolor=color,alpha=.65,edgecolor='none',label=status))
   truth=list(map(numeric,r['evaluation']['truth']));ax.plot(truth[0],truth[1],'kx',ms=9,label='truth (evaluation only)')
   if r['evaluation']['mirror_truth']:
    p=list(map(numeric,r['evaluation']['mirror_truth']));ax.plot(p[0],p[1],'k+',ms=9,label='mirror witness')
   if comp['status']=='AVAILABLE':
    w,V=np.linalg.eigh(comp['projected_shape']);angle=np.degrees(np.arctan2(V[1,1],V[0,1]));ax.add_patch(Ellipse(comp['center'][:2],2*np.sqrt(w[1]),2*np.sqrt(w[0]),angle=angle,fill=False,edgecolor='blue',linestyle='--',label='local affine: NOT nonlinear bound'))
   ax.set_aspect('equal');ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)');ax.grid(alpha=.2)
  domain=r['model']['domain'];axes[0].set_xlim(*map(numeric,domain[0]));axes[0].set_ylim(*map(numeric,domain[1]));axes[0].set_title('Full fixed XY domain')
  if z['hull']:
   h=z['hull'];xmin,xmax=map(numeric,h[0]);ymin,ymax=map(numeric,h[1]);pad=max(.15,.1*max(xmax-xmin,ymax-ymin));axes[1].set_xlim(xmin-pad,xmax+pad);axes[1].set_ylim(ymin-pad,ymax+pad)
  else:axes[1].set_xlim(-6,6);axes[1].set_ylim(-6,6)
  axes[1].set_title('All retained branches; display zoom only');axes[1].legend(fontsize=7)
  fig.suptitle(f"{r['id']}: {res['termination']} | inside=green, undecided=orange, pending=purple")
  fig.tight_layout();fig.savefig(out/(r['id']+'.png'),dpi=150);plt.close(fig)
  rows.append(dict(case=r['id'],stage=r['stage'],processed=res['processed'],retained=sum(res['counts'].get(k,0) for k in ['INSIDE','UNDECIDED','PENDING','NUMERICAL_UNDECIDED']),inside=res['counts'].get('INSIDE',0),undecided=res['counts'].get('UNDECIDED',0),pending=res['counts'].get('PENDING',0),seconds=res['elapsed_seconds'],termination=res['termination'],boundary=res['boundary_contact'],empty=res['empty_proved'],area_lower=float(F(z['area_lower_m2'])),area_upper=float(F(z['area_upper_m2'])),radius_upper=float(F(z['radius_upper_m'])) if z['radius_upper_m'] else None,affine_status=comp['status']))
 with (out/'RESULTS.csv').open('x') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (out/'LOCAL_AFFINE.json').write_text(json.dumps(local,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();main(a.results,a.out)
