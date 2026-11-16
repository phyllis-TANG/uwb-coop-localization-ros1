"""Supplement: reusable current-model record interface (no fitting, no new method)."""
import numpy as np
from diagnostics import diagnose

def assess_saved(*,state,error,j_data,j_prior,layout,actual_noise,prior_spec,numerical_status,rtol=1e-8):
    """prior_spec explicitly describes fixed/random centre and whitened precision.
    Returns raw diagnose output plus per-record denominators; malformed contracts
    raise ValueError, whereas nonfinite evidence returns unavailable, never success.
    Coverage truth/error is offline evaluation only and cannot select estimates.
    """
    required={'centre','centre_mode','precision_description','position_indices'}
    if not required.issubset(prior_spec):raise ValueError('Explicit prior provenance required')
    if prior_spec['centre_mode']!='fixed':raise ValueError('Current noise view requires a fixed prior centre')
    if len(prior_spec['centre'])!=len(prior_spec['position_indices']):raise ValueError('Prior centre/index mismatch')
    planned=len(layout.position_blocks)
    if not all(np.isfinite(np.asarray(v,float)).all() for v in [state,error,j_data,j_prior]):
        return dict(numerical_status=dict(numerical_status),prior_spec=prior_spec,reason='NONFINITE_INPUT',diagnostic=None,
                    denominators={view:dict(planned=planned,available=0,unavailable=planned,covered95=0,covered99=0) for view in ['total_curvature','fixed_prior_noise','data_only']})
    d=diagnose(state=state,error=error,j_data=j_data,j_prior=j_prior,layout=layout,actual_noise=actual_noise,numerical_status=numerical_status,rtol=rtol)
    den={}
    for view,points in d['positions'].items():
        den[view]=dict(planned=planned,available=sum(p['available'] for p in points),unavailable=sum(not p['available'] for p in points),covered95=sum(p['available'] and p['levels']['0.95']['covered'] for p in points),covered99=sum(p['available'] and p['levels']['0.99']['covered'] for p in points))
    return dict(numerical_status=dict(numerical_status),prior_spec=prior_spec,reason='PROCESSED',diagnostic=d,denominators=den)
