"""Independent AR/iid recipe audit plus unchanged no-optimizer readback."""
import argparse
from pathlib import Path
import numpy as np
import readback as base
original_check=base.check_input

def check(u,c):
    original_check(u,c);model=c['range_noise_models'][u['condition']['noise_model']];rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([u['seed'],c['noise']['range_stream']])));z=rng.normal(size=(6,9));sigma=model['actual_marginal_sigma_m']
    if model['type']=='iid':expected=sigma*z
    else:
        # Closed-form stationary AR expansion, independent of generator recurrence.
        rho=model['rho'];expected=np.empty((6,9))
        for t in range(6):
            expected[t]=sigma*(rho**t)*z[0]
            for j in range(1,t+1):expected[t]+=sigma*np.sqrt(1-rho**2)*(rho**(t-j))*z[j]
    assert np.max(abs(expected.ravel()-np.array(u['noise']['range'])))<1e-14
    assert u['obs']['range_sigma']==.04
base.check_input=check
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path);p.add_argument('--evidence',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(base.raw(a.run,a.out) if a.run else base.portable_check(a.evidence,a.out))
