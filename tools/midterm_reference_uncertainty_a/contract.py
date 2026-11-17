"""Small exact arithmetic helpers; not a positioning or interval-search solver."""
from fractions import Fraction
from math import isqrt
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/research/midterm_reference_uncertainty_a'
CALLS=dict(optimizer_calls=0,search_calls=0,random_calls=0)
def F(x,denominator=None):
 if isinstance(x,float) or isinstance(denominator,float):raise TypeError('exact inputs must be rational strings or integers')
 return Fraction(x) if denominator is None else Fraction(x,denominator)
def vec(x):return [F(v) for v in x]
def dot(x,y):return sum((a*b for a,b in zip(x,y)),F(0))
def sub(x,y):return [a-b for a,b in zip(x,y)]
def matvec(A,x):return [dot(row,x) for row in A]
def norm2(x):return dot(x,x)
def sqrt_bounds(x,places=30):
 x=F(x)
 if x<0:raise ValueError('negative squared norm')
 s=10**places;k=isqrt(x.numerator*s*s//x.denominator);lo=F(k,s);hi=lo if k*k*x.denominator==x.numerator*s*s else F(k+1,s)
 assert lo*lo<=x<=hi*hi
 return lo,hi
def ball_range(d,rho):
 d,rho=F(d),F(rho)
 if d<0 or rho<0:raise ValueError('negative range or radius')
 return max(F(0),d-rho),d+rho
def bias_envelope(d,rho,b):
 lo,hi=ball_range(d,rho);bl,bh=vec(b)
 if bl>bh:raise ValueError('empty bias domain')
 return (lo+bl,hi+bh),(F(d)+bl-F(rho),F(d)+bh+F(rho))
def score2(R,e):
 R=[vec(row) for row in R];e=vec(e)
 if len(R)!=2 or any(len(row)!=2 for row in R) or len(e)!=2:raise ValueError('explicit 2D contract only')
 a,b=R[0];c,d=R[1];det=a*d-b*c
 if b!=c or a<=0 or det<=0:raise ValueError('R_NOT_POSITIVE_DEFINITE')
 return (d*e[0]*e[0]-2*b*e[0]*e[1]+a*e[1]*e[1])/det

def tail4(q,terms=81):
 t=F(q)/2;term=F(1);s=term
 for k in range(1,terms):term*=t/k;s+=term
 # exp(t)>positive finite Taylor sum; survival=(1+t)/exp(t).
 return (1+t)/s

def clean(v):
 if isinstance(v,Fraction):return str(v)
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 return v
def save(path,obj):
 with Path(path).open('x') as f:json.dump(clean(obj),f,indent=2,ensure_ascii=False);f.write('\n')
def digest(obj):return hashlib.sha256(json.dumps(clean(obj),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def source_check():
 hs=json.loads((DOC/'SOURCE_HASHES.json').read_text());bad=[p for p,h in hs['files'].items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
 if bad:raise RuntimeError('SOURCE_CHANGED:'+str(bad))
 return len(hs['files'])
def guard(frame,event,arg):
 if event!='call':return
 path=frame.f_code.co_filename;name=frame.f_code.co_name
 if '/scipy/optimize/' in path:CALLS['optimizer_calls']+=1;raise RuntimeError('optimizer forbidden')
 if '/numpy/random/' in path or path.endswith('/random.py'):CALLS['random_calls']+=1;raise RuntimeError('random sampling forbidden')
 if '/tools/' in path and name in ['solve','generate','generate_input']:CALLS['search_calls']+=1;raise RuntimeError('search/old generator forbidden')
def protect():sys.setprofile(guard)
