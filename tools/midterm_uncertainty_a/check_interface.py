import json
import numpy as np
from diagnostics import Layout,Noise
from interface import assess_saved
layout=Layout(('x','y'),('m','m'),((1,0,0,1),),None,(1,1),2,0,'identity data; no prior')
kw=dict(state=np.zeros(2),error=np.ones(2)*.1,j_data=np.eye(2),j_prior=np.empty((0,2)),layout=layout,actual_noise=Noise('identity',2),prior_spec=dict(centre=[],centre_mode='fixed',precision_description='none',position_indices=[]),numerical_status={'category':'NOT_STATIONARY'})
a=assess_saved(**kw);assert a['denominators']['total_curvature']['covered95']==1 and a['numerical_status']['category']=='NOT_STATIONARY'
b=assess_saved(**dict(kw,j_data=np.array([[1,0],[0,0]])));assert b['denominators']['total_curvature']['available']==0
c=assess_saved(**dict(kw,state=np.array([np.nan,0])));assert c['reason']=='NONFINITE_INPUT' and c['denominators']['total_curvature']['covered95']==0
print(json.dumps(dict(passed=True,numerical_label_preserved=True,rank_deficiency_unavailable=True,nonfinite_unavailable=True),indent=2))
