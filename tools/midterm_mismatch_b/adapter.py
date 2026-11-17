"""Injection/oracle adapter only; numerical objective and solver are frozen dependencies."""
import copy,importlib.util,itertools
import numpy as np
from io_utils import ROOT,DOC,read,digest
spec=importlib.util.spec_from_file_location('frozen_validation_core',ROOT/'tools/midterm_simulation_validation/core.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)

def config():return read(DOC/'CONFIG.json')
def conditions(c):
    x=c['matrix'];return [dict(id=f'm{i:02}',geometry=g,motion=m,candidate=k,injection=f) for i,(g,m,k,f) in enumerate(itertools.product(x['geometries'],x['motions'],x['candidates'],x['injections']))]
def injection(c,q):
    link=c['links'][q['candidate']];seq=c['injection_sequences_m'][q['injection']];v=np.zeros(54)
    v[link['indices']]=seq['candidate'];v[link['other_indices']]=seq['other'];return v

def generate(c,q,seed):
    baseq=dict(id=q['id'],geometry=q['geometry'],motion=q['motion'],kind=q['candidate'],bias_m=0.,prior='survey_core')
    u=V.generate(c,baseq,seed);y0=np.array(u['obs']['ranges']);inj=injection(c,q)
    u['obs']['ranges']=(y0+inj).tolist();u.update(condition=q,injection=inj.tolist(),no_fault_ranges=y0.tolist(),actual_faults=[dict(index=i,epoch=i//9,row=i%9,link_id=('Car1-anchor'+str(i%9)) if i%9<4 else ('Car2-anchor'+str(i%9-4)) if i%9<8 else 'Car1-Car2',bias_m=float(v)) for i,v in enumerate(inj) if v!=0.])
    u.pop('oracle');u['input_sha256']=digest(u['obs']);return u

def solver_problem(c,obs,method,full_oracle=None):
    old='B3' if method=='B3_full_oracle' else method
    if method!='B3_full_oracle' and full_oracle is not None:raise ValueError('Oracle must not be supplied to B0/B1/B2')
    return V.objective(c,obs,old,full_oracle)

def solve(c,u,method,stage,previous=None,solver=None):
    # Only observations enter objective/init. Truth is read by the old OFFLINE evaluator
    # after least_squares returns; actual injection/mask never enters B0/B1/B2.
    payload=dict(obs=u['obs'],truth=u['truth'],condition={'bias_m':0.})
    old='B3' if method=='B3_full_oracle' else method
    if method=='B3_full_oracle':payload['oracle']=u['injection']
    kw={} if solver is None else {'solver':solver}
    r=V.solve_stage(c,payload,old,stage,previous,**kw)
    # Erase old single-b truth error; only label a true parameter in the two matched cases.
    r['bias_error']=None;r['bias_error_exceeds']=None
    r['candidate_injection_mean_m']=None;r['b_minus_candidate_mean_m']=None;r['unabsorbed_injection_rms_m']=None;r['unabsorbed_candidate_rms_m']=None;r['unabsorbed_other_rms_m']=None
    if method=='B2' and r['usable_estimate']:
        b=r['bias_estimate'];link=c['links'][u['condition']['candidate']];inj=np.array(u['injection']);mean=float(inj[link['indices']].mean());remaining=inj-b*V.B.active(u['condition']['candidate'])
        r.update(candidate_injection_mean_m=mean,b_minus_candidate_mean_m=b-mean,unabsorbed_injection_rms_m=float(np.sqrt(np.mean(remaining**2))),unabsorbed_candidate_rms_m=float(np.sqrt(np.mean(remaining[link['indices']]**2))),unabsorbed_other_rms_m=float(np.sqrt(np.mean(remaining[link['other_indices']]**2))))
        if u['condition']['injection'] in ['zero','constant']:
            r['bias_error']=b-mean;r['bias_error_exceeds']=abs(b-mean)>c['statistics']['absolute_bias_error_threshold_m']
    return r
