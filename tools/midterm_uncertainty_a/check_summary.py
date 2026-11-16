"""Check unavailable denominators and within-seed dependence analytically."""
import json
import numpy as np
from summarize import metrics
rng=np.random.default_rng(91327061)
counts=np.array([np.bincount(x,minlength=50) for x in rng.integers(0,50,(10000,50))])
q=np.ones((50,1));q[:10]=10;q[10:12]=np.nan
one=metrics(q,np.ones(50,bool),6,counts)
six=metrics(np.repeat(q,6,axis=1),np.ones(50,bool),6,counts)
assert one['planned']==50 and one['available']==48 and one['covered']==38 and one['unavailable']==2
assert one['covered_over_full_plan']==38/50 and one['coverage_available']==38/48
for k in ['ci_low','ci_high','joint_ci_low','joint_ci_high']:assert abs(one[k]-six[k])<1e-12
empty=metrics(q,np.zeros(50,bool),6,counts);assert empty['coverage_available'] is None and empty['covered_over_full_plan']==0
constant=metrics(np.ones((50,6)),np.ones(50,bool),6,counts);assert constant['ci_low'] is None and constant['ci_status']=='CONSTANT_EMPIRICAL_CLUSTERS'
trajectory=metrics(np.repeat(q,6,axis=1),np.ones(50,bool),6,counts,True);assert trajectory['planned']==50 and trajectory['covered']==38
print(json.dumps(dict(passed=True,unavailable_not_success=True,six_duplicate_times_do_not_shrink_CI=True,empty_ratio_null=True,constant_clusters_no_false_precision=True,trajectory_denominator=50),indent=2))
