"""Actual antenna-XY constraints with full retained joint F0 history."""
import copy,time,types
from types import SimpleNamespace
import numpy as np
from scipy.optimize import minimize
from common import CONFIG
from bindings import base,legacy

def antennas(pose,config):
 x=np.asarray(pose).reshape(2,3)
 return np.array([legacy.antenna(x[i],config['models'][c]['base_to_antenna_body_xy_m']) for i,c in enumerate(legacy.CARS)])
def antenna_jac(pose,config):
 x=np.asarray(pose);J=np.zeros((2,2,6))
 for i,c in enumerate(legacy.CARS):
  lx,ly=config['models'][c]['base_to_antenna_body_xy_m'];yaw=x[3*i+2];co,si=np.cos(yaw),np.sin(yaw)
  J[i,:,3*i:3*i+2]=np.eye(2);J[i,:,3*i+2]=[-si*lx-co*ly,co*lx-si*ly]
 return J

def constraint(flat,reference,config,budget):
 x=np.asarray(flat);d=antennas(x[-6:],config)-antennas(reference,config)
 values=budget*budget-np.sum(d*d,axis=1);J=np.zeros((2,len(x)));J[:,-6:]=-2*np.einsum('ij,ijk->ik',d,antenna_jac(x[-6:],config))
 return values,J

def clip_pose(pose,reference,config,budget):
 x=np.array(pose,float);center=antennas(reference,config);a=antennas(x,config);d=a-center;norm=np.linalg.norm(d,axis=1)
 for i in range(2):
  if norm[i]>budget:x[3*i:3*i+2]+=(center[i]+budget*d[i]/norm[i])-a[i]
 return x.tolist()

class WeightedObjective(base.Objective):
 def __init__(self,*a,weight=1.,**kw):super().__init__(*a,**kw);self.weight=weight
 def evaluate(self,x):
  r,J=super().evaluate(x);r=r.copy();J=J.copy();n=len(self.peers)
  if n:r[-n:]*=np.sqrt(self.weight);J[-n:]*=np.sqrt(self.weight)
  return r,J

class InfluenceGraph(base.WindowGraph):
 def __init__(self,config,method,*,test_fault=None):
  super().__init__(config,True);self.method=method;self.weight=.25 if method=='W025' else 1.
  self.budget={'K004':.04,'K100':1.}.get(method);self.use_slsqp=method in ['U','K004','K100']
  self.reference=base.WindowGraph(config,False);self.reference_initial=copy.deepcopy(self.reference.prior.record())
  self.test_fault=test_fault;self.current=None
  def factory(*a,**kw):return WeightedObjective(*a,weight=self.weight,**kw)
  env=dict(base.incident_system.__globals__);env['Objective']=factory
  incident=types.FunctionType(base.incident_system.__code__,env)
  env=dict(base.eliminate_oldest.__globals__);env['incident_system']=incident
  original_eliminate=types.FunctionType(base.eliminate_oldest.__code__,env)
  def eliminate(*a,**kw):
   prior,constant,details=original_eliminate(*a,**kw);details['peer_information_weight']=self.weight;return prior,constant,details
  env=dict(base.WindowGraph.update.__globals__);env.update(Objective=factory,eliminate_oldest=eliminate,least_squares=self.solve)
  self.original_update=types.FunctionType(base.WindowGraph.update.__code__,env)
 def solve(self,fun,x0,jac,**kwargs):
  if not self.use_slsqp:return base.least_squares(fun,x0,jac=jac,**kwargs)
  start=time.perf_counter();spec=CONFIG['solver'];self.solve_attempted=True
  def deadline():
   if self.test_fault=='timeout' or time.perf_counter()-start>spec['max_solve_wall_s']:raise ValueError('CONTROL_TIMEOUT')
  if self.test_fault=='failure':raise ValueError('CONTROL_SOLVER_FAILURE_TEST')
  if self.budget is not None and not self.reference_current['accepted_graph']:raise ValueError('CONTROL_REFERENCE_UNKNOWN')
  def objective(x):deadline();r=fun(x);return float(r@r/2)
  def gradient(x):deadline();return jac(x).T@fun(x)
  def callback(x):
   deadline();self.iterations.append(dict(states=np.asarray(x).reshape(-1,6).tolist(),cost=objective(x),separation_m=np.linalg.norm(antennas(x[-6:],self.config)-antennas(self.reference_current['pose'],self.config),axis=1).tolist()))
  cons=[]
  if self.budget is not None:
   cons=[dict(type='ineq',fun=lambda x:constraint(x,self.reference_current['pose'],self.config,self.budget)[0],jac=lambda x:constraint(x,self.reference_current['pose'],self.config,self.budget)[1])]
  sol=minimize(objective,x0,jac=gradient,method='SLSQP',constraints=cons,callback=callback,options={'ftol':spec['ftol'],'maxiter':spec['maxiter'],'disp':False})
  deadline();self.candidate_states=sol.x.reshape(-1,6).tolist();distance=np.linalg.norm(antennas(sol.x[-6:],self.config)-antennas(self.reference_current['pose'],self.config),axis=1)
  feasible=self.budget is None or bool(np.all(distance<=self.budget+CONFIG['tolerances']['published_budget_m']))
  self.solver_diagnostics=dict(method='SLSQP',nit=int(sol.nit),gradient_inf=float(np.max(abs(sol.jac))),max_budget_violation_m=None if self.budget is None else float(max(0.,max(distance-self.budget))),success_before_budget_check=bool(sol.success))
  if self.budget is not None:
   cv,cj=constraint(sol.x,self.reference_current['pose'],self.config,self.budget);active=cv<1e-7
   lam=np.linalg.lstsq(cj[active].T,sol.jac,rcond=None)[0] if active.any() else np.array([])
   self.solver_diagnostics.update(active_constraints=active.tolist(),multipliers=lam.tolist(),stationarity_inf=float(np.max(abs(sol.jac-cj[active].T@lam))))
  return SimpleNamespace(x=sol.x,success=bool(sol.success and feasible),status=int(sol.status),nfev=int(sol.nfev),cost=float(sol.fun),optimality=float(np.max(abs(sol.jac))),message=str(sol.message) if feasible else 'CONTROL_BUDGET_REJECTED')
 def update(self,stamp,local,observations,peer):
  started=time.perf_counter();ref=self.reference.update(stamp,local,observations,None);refwall=time.perf_counter()-started
  # A test-only invalidation never changes the private reference graph itself.
  if self.test_fault=='reference_unknown':ref=copy.deepcopy(ref);ref['accepted_graph']=False
  self.reference_current=ref;self.iterations=[];self.candidate_states=None;self.solver_diagnostics={};self.solve_attempted=False
  started=time.perf_counter();raw=self.original_update(self,stamp,local,observations,peer);mainwall=time.perf_counter()-started
  refknown=bool(ref['accepted_graph'] and ref['pose'] is not None and np.isfinite(ref['pose']).all())
  result=copy.deepcopy(raw);sep=None;bounded=self.budget is not None
  if raw['pose'] is not None and ref['pose'] is not None:sep=np.linalg.norm(antennas(raw['pose'],self.config)-antennas(ref['pose'],self.config),axis=1)
  fits=not bounded or sep is not None and bool(np.all(sep<=self.budget+CONFIG['tolerances']['published_budget_m']))
  if not refknown:
   mode='unknown';reason='REFERENCE_NOT_ACCEPTED';published=ref['pose'];joint=False
  elif raw['accepted_graph'] and fits:
   mode='normal_joint';reason='ACCEPTED_WITHIN_BUDGET' if bounded else 'ACCEPTED_UNCONTROLLED';published=raw['pose'];joint=True
  else:
   mode='reference_fallback';published=ref['pose'];joint=False
   msg=str(raw.get('optimizer',{}))
   reason='TIMEOUT' if 'CONTROL_TIMEOUT' in msg else 'BUDGET_REJECTED' if (raw['accepted_graph'] and not fits) or 'CONTROL_BUDGET_REJECTED' in msg else 'SOLVER_FAILURE'
  result.update(peer_information_weight=self.weight,pose=copy.deepcopy(published),accepted_graph=joint,main_pose=raw['pose'],main_accepted_graph=raw['accepted_graph'],main_status=raw['status'],
    publication_mode=mode,publication_reason=reason,joint_optimization_success=joint,reference_accepted=refknown,budget_m=self.budget,covariance=None,
    budget_certified=bool(bounded and refknown and published is not None),
    published_separation_m=None if published is None or ref['pose'] is None else np.linalg.norm(antennas(published,self.config)-antennas(ref['pose'],self.config),axis=1).tolist(),
    candidate_states=self.candidate_states,solver_diagnostics=self.solver_diagnostics,solver_iterations=self.iterations,main_update_wall_s=mainwall,reference_update_wall_s=refwall)
  self.current=dict(reference=dict(ref,snapshot=copy.deepcopy(self.reference.snapshot()),initial_prior=self.reference_initial),state_time_s=stamp)
  return result
