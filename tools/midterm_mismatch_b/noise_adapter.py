"""Subsequent noise experiment. Original fault adapter remains byte-unchanged."""
import itertools
import numpy as np
import adapter as fault
from io_utils import digest

def conditions(c):
    x=c['matrix'];return [dict(id=f'n{i:02}',geometry=g,motion=m,candidate=k,injection=f,noise_model=z) for i,(g,m,k,f,z) in enumerate(itertools.product(x['geometries'],x['motions'],x['candidates'],x['injections'],x['noise_models']))]

def transform(z,model):
    sigma=model['actual_marginal_sigma_m'];a=np.asarray(z,float)
    if model['type']=='iid':return sigma*a
    rho=model['rho'];out=np.empty_like(a);out[...,0,:]=sigma*a[...,0,:]
    for t in range(1,a.shape[-2]):out[...,t,:]=rho*out[...,t-1,:]+sigma*np.sqrt(1-rho*rho)*a[...,t,:]
    return out

def generate(c,q,seed):
    u=fault.generate(c,q,seed);model=c['range_noise_models'][q['noise_model']]
    rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed,c['noise']['range_stream']])));z=rng.normal(0,1,(6,9));actual=transform(z,model).ravel()
    clean=fault.V.B.pr97.model(np.r_[np.array(u['truth']).ravel(),0.],np.array(u['obs']['anchors']),q['candidate'])[0]
    u['noise']['range']=actual.tolist();u['no_fault_ranges']=(clean+actual).tolist();u['obs']['ranges']=(clean+actual+np.array(u['injection'])).tolist();u['actual_range_noise_model']=q['noise_model'];u['assumed_range_noise_model']='iid_sigma_0.04';u['input_sha256']=digest(u['obs'])
    assert u['obs']['range_sigma']==.04
    return u
