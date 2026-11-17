"""Directed Decimal intervals; sqrt endpoints additionally certified by integers."""
from decimal import Decimal as D, Context, ROUND_FLOOR, ROUND_CEILING, FloatOperation, Underflow, Subnormal
from fractions import Fraction as F
from math import isqrt
PREC=40
LO=Context(prec=PREC,rounding=ROUND_FLOOR)
HI=Context(prec=PREC,rounding=ROUND_CEILING)
for c in (LO,HI):
 for signal in (FloatOperation,Underflow,Subnormal):c.traps[signal]=True

def point(x):
 if isinstance(x,float):raise TypeError('Float not accepted by certified core')
 x=D(x)
 if not x.is_finite():raise ValueError('Nonfinite input')
 return (x,x)
def add(a,b):return LO.add(a[0],b[0]),HI.add(a[1],b[1])
def sub(a,b):return LO.subtract(a[0],b[1]),HI.subtract(a[1],b[0])
def mul(a,b):
 return min(LO.multiply(x,y) for x in a for y in b),max(HI.multiply(x,y) for x in a for y in b)
def divpos(a,b):
 if b[0]<=0:raise ValueError('positive denominator required')
 return mul(a,(LO.divide(D(1),b[1]),HI.divide(D(1),b[0])))
def square(a):
 mn=D(0) if a[0]<=0<=a[1] else min(a[0].copy_abs(),a[1].copy_abs())
 mx=max(a[0].copy_abs(),a[1].copy_abs())
 return LO.multiply(mn,mn),HI.multiply(mx,mx)
def root_bound(x,upper=False):
 if x<0:raise ValueError('negative sqrt')
 n,d=x.as_integer_ratio();s=10**35;k=isqrt(n*s*s//d)
 if upper and k*k*d!=n*s*s:k+=1
 # Construct exactly; no ambient context rounding.
 return D((0,tuple(map(int,str(k))),-35))
def sqrt(a):return root_bound(a[0]),root_bound(a[1],True)
def norm2(a,b):return sqrt(add(square(a),square(b)))
def encode(box):return [[str(a),str(b)] for a,b in box]
def decode(box):
 z=tuple((D(a),D(b)) for a,b in box)
 if any(not a.is_finite() or not b.is_finite() or a>b for a,b in z):raise ValueError('invalid box')
 return z

def threshold_certificate(q='9.488'):
 # chi-square_4 survival exp(-q/2)*(1+q/2). Prove upper tail < .05
 # using positive Taylor partial sum as a LOWER bound for exp(q/2).
 t=F(q)/2;term=F(1);s=term
 for k in range(1,81):term*=t/k;s+=term
 upper=(1+t)/s
 assert upper<F(1,20)
 return dict(df=4,q=q,tail_upper_fraction=str(upper),tail_upper_display=float(upper),terms=81)
