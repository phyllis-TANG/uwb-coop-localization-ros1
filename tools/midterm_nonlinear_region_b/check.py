"""Independent rational certificate readback; never searches or optimizes."""
import argparse,json,gzip,hashlib
from fractions import Fraction as F
from math import isqrt
from pathlib import Path

def plus(a,b):return a[0]+b[0],a[1]+b[1]
def minus(a,b):return a[0]-b[1],a[1]-b[0]
def times(a,b):
 v=[x*y for x in a for y in b];return min(v),max(v)
def sq(a):return (F(0) if a[0]<=0<=a[1] else min(x*x for x in a),max(x*x for x in a))
def root(a):
 s=10**45;v=[]
 for i,x in enumerate(a):
  k=isqrt(x.numerator*s*s//x.denominator)
  if i and k*k*x.denominator!=x.numerator*s*s:k+=1
  v.append(F(k,s))
 return tuple(v)
def point(x):return F(x),F(x)
def rational_bound(box,m):
 p=[]
 if m.get('affine'):
  for row,o in zip(m['A'],m['offset']):
   h=point(o)
   for a,b in zip(row,box):h=plus(h,times(point(a),b))
   p.append(h)
 else:
  for k,a in enumerate(m['anchors']):
   h=root(plus(sq(minus(box[0],point(a[0]))),sq(minus(box[1],point(a[1])))))
   if k==m['affected_index']:h=plus(h,box[2] if m['unknown_bias'] else point(m['known_bias']))
   p.append(h)
 z=point(0)
 for h,y,s in zip(p,m['observations'],m['sigma']):
  z=plus(z,sq(times(minus(tuple(map(F,y)),h),point(1/F(s)))))
 return z

def unpack(b):return tuple(tuple(map(F,x)) for x in b)
def retained(result):return [n for n in result['nodes'] if n['status'] not in ('SPLIT','OUTSIDE')]
def contains(result,p):return any(all(a<=F(x)<=b for x,(a,b) in zip(p,unpack(n['box']))) for n in retained(result))
def audit(model,settings,result):
 nodes={n['path']:n for n in result['nodes']};assert len(nodes)==len(result['nodes']);assert nodes['']['box']==model['domain']
 stack=[''];visited=set();q=F(settings['q']);certs=0
 while stack:
  path=stack.pop();assert path not in visited;visited.add(path);n=nodes[path];box=unpack(n['box'])
  if n['status']=='SPLIT':
   j=n['axis'];m=F(n['mid']);assert box[j][0]<m<box[j][1]
   for side in (0,1):
    b=list(box);b[j]=(box[j][0],m) if side==0 else (m,box[j][1]);child=path+str(side)
    assert unpack(nodes[child]['box'])==tuple(b);stack.append(child)
  elif n['status'] in ('OUTSIDE','INSIDE'):
   l,h=rational_bound(box,model)
   assert l>q if n['status']=='OUTSIDE' else h<=q
   certs+=1
  else:assert n['status'] in ('PENDING','UNDECIDED','NUMERICAL_UNDECIDED')
 assert visited==set(nodes)
 kept=retained(result);assert result['empty_proved']==(len(kept)==0)
 assert result['processed']==sum(n['status']!='PENDING' for n in nodes.values())
 return dict(status='PASS',nodes=len(nodes),certified_leaves=certs,retained=len(kept))

def metrics(model,result):
 kept=retained(result);bs=[unpack(n['box']) for n in kept]
 if not bs:return dict(area_upper_m2='0',area_lower_m2='0',center=None,radius_upper_m=None,hull=None,projection_rectangles=[])
 rects=sorted(set(b[:2] for b in bs));hull=tuple((min(b[i][0] for b in bs),max(b[i][1] for b in bs)) for i in range(2))
 center=tuple((a+b)/2 for a,b in hull)
 area=sum((b[0][1]-b[0][0])*(b[1][1]-b[1][0]) for b in rects)
 hullarea=(hull[0][1]-hull[0][0])*(hull[1][1]-hull[1][0]);area=min(area,hullarea)
 inner=[unpack(n['box']) for n in kept if n['status']=='INSIDE'];lower=max(((b[0][1]-b[0][0])*(b[1][1]-b[1][0]) for b in inner),default=F(0))
 rad2=max(sum(max((p-center[i])**2 for p in b[i]) for i in range(2)) for b in rects);radius=root((rad2,rad2))[1]
 enc=lambda b:[[str(a),str(v)] for a,v in b]
 return dict(area_upper_m2=str(area),area_lower_m2=str(lower),center=list(map(str,center)),radius_upper_m=str(radius),hull=enc(hull),projection_rectangles=[enc(b) for b in rects])

def verify_directory(path):
 meta=json.loads((path/'RUN.json').read_text());root=Path(__file__).resolve().parents[2]
 for file,h in meta['manifest']['files'].items():assert hashlib.sha256((root/file).read_bytes()).hexdigest()==h,file
 planned=json.loads((root/'docs/research/midterm_nonlinear_region_b/INPUTS.json').read_text());plan={c['id']:c for c in planned}
 assert {f.name.removesuffix('.json.gz') for f in path.glob('*.json.gz')}==set(plan)
 summary=[]
 for f in sorted(path.glob('*.json.gz')):
  with gzip.open(f,'rt') as h:r=json.load(h)
  c=plan[r['id']];assert all(r[k]==v for k,v in c.items());assert r['identity']['freeze']==meta['freeze']
  assert r['identity']['input_sha']==hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
  z=audit(r['model'],r['settings'],r['result']);assert metrics(r['model'],r['result'])==r['metrics'];z['case']=r['id'];summary.append(z)
 assert len(summary)==8
 return dict(status='PASS',cases=summary,search_calls=0,optimizer_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();z=verify_directory(a.results)
 with a.out.open('x') as f:json.dump(z,f,indent=2)
 print(json.dumps(z))
