"""Field SE(2) four-method comparison, with no boundary-prior information."""
from fcommon import *
from model import objective as old_objective

class Field:
 def __init__(self,o,method):
  if method not in ['F0','F1','F2','F3']:raise ValueError('method')
  self.o=o;self.method=method;self.base=old_objective(o,False);self.n=len(o['times']);self.posdim=6*self.n
  self.extra={'F0':0,'F1':0,'F2':1,'F3':2}[method];self.dim=self.posdim+self.extra
  self.keep=np.ones(self.base.rows,bool);offset=0
  for part in self.base.parts:self.keep[offset:offset+3]=False;offset+=3*self.n+len(part.index)
  self.ids=np.array([i for i,p in enumerate(o['peers']) if p['range_m'] is not None],int)
  self.tau=np.array(o['times'])-(o['times'][0]+o['times'][-1])/2
  self.scales=np.r_[np.tile([1.,1.,.1],2*self.n),([.1] if self.extra==1 else [.1,.01] if self.extra==2 else [])]
 def initial(self):return np.r_[np.array([self.o['cars'][c]['initial'] for c in CARS]).ravel(),np.zeros(self.extra)]
 def peer(self,q):
  s=np.asarray(q[:self.posdim]).reshape(2,self.n,3);ant=[];der=[]
  for ci,c in enumerate(CARS):
   arm=np.array([rotation(t)@self.o['cars'][c]['model']['base_to_antenna_body_xy_m'] for t in s[ci,:,2]])
   ant.append(s[ci,:,:2]+arm);der.append(np.column_stack((-arm[:,1],arm[:,0])))
  d=ant[0]-ant[1];dz=self.o['cars']['car1']['model']['antenna_height_m']-self.o['cars']['car2']['model']['antenna_height_m'];dist=np.sqrt(np.sum(d*d,axis=1)+dz*dz)
  if np.any(dist<1e-12):raise ValueError('coincident antenna')
  j=np.zeros((len(self.ids),self.dim));b=np.zeros(self.n)
  if self.extra:b+=q[-self.extra]
  if self.extra==2:b+=q[-1]*self.tau
  for k,i in enumerate(self.ids):
   for ci,sign in [(0,1),(1,-1)]:j[k,3*(ci*self.n+i):3*(ci*self.n+i)+3]=sign*np.r_[d[i]/dist[i],d[i]@der[ci][i]/dist[i]]
   if self.extra:j[k,-self.extra]=1
   if self.extra==2:j[k,-1]=self.tau[i]
  y=np.array([self.o['peers'][i]['range_m'] for i in self.ids])
  return dist[self.ids]+b[self.ids]-y,j,np.array(ant),b
 def evaluate(self,q):
  r,j=self.base.evaluate(np.asarray(q[:self.posdim]));r=r[self.keep];j=np.pad(j[self.keep],((0,0),(0,self.extra)))
  if self.method!='F0':
   raw,jp,_,_=self.peer(q);sigma=self.o['peer_sigma_m'];e=raw/sigma;s=np.sqrt(1+e*e)
   r=np.r_[r,e*np.sqrt(2/(s+1))];j=np.vstack((j,jp*(np.sqrt((s+1)/2)/s/sigma)[:,None]))
  return r,j
 def fun(self,q):return self.evaluate(q)[0]
 def jac(self,q):return self.evaluate(q)[1]
