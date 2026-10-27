"""B-only scalar objective and finite-difference prior audit, no online code."""
import math
import sys
import numpy as np
from .common import ROOT,require
# Reuse B PR59 independent scalar formulas; this module imports no A policy,
# production graph/Jacobian or qaudit. Range rows are last in this B formula.
sys.path.insert(0,str(ROOT/'tools/single_car_imu_fgo_eval'))
from verify_fgo import residual as B_PR59_residual


def wrap(x):return math.atan2(math.sin(x),math.cos(x))


def weighted_residual(snapshot,states,base):
    r=B_PR59_residual(snapshot,states,base).copy();observations=snapshot['observations'];weights=snapshot.get('quality_weights',[{k:1. for k in row} for row in observations]);count=sum(len(row) for row in observations)
    if count:
        w=[weights[i][k] for i,row in enumerate(observations) for k in sorted(row)];require(all(math.isfinite(v) and 0<=v<=1 for v in w),'weight bounds');r[-count:]*=np.sqrt(w)
    return r


def marginal(item,base):
    s=item['linearization_input'];x=np.array(s['states'],float);flat=x.ravel();d=x.shape[1];r=weighted_residual(s,x,base);columns=[]
    for j in range(len(flat)):
        delta=np.zeros_like(flat);delta[j]=1e-6;columns.append((weighted_residual(s,(flat+delta).reshape(x.shape),base)-weighted_residual(s,(flat-delta).reshape(x.shape),base))/2e-6)
    J=np.column_stack(columns);a,b=J[:,:d],J[:,d:];projected=b-a@np.linalg.lstsq(a,b,rcond=None)[0];offset=r-a@np.linalg.lstsq(a,r,rcond=None)[0];p=item['prior_after'];M=np.asarray(p['matrix']).reshape(-1,d);c=np.asarray(p['offset'])
    h=M.T@M;expected_h=projected.T@projected;g=M.T@c;expected_g=projected.T@offset
    require(np.allclose(h,expected_h,rtol=1e-5,atol=.03),'marginal information/cross terms mismatch');require(np.allclose(g,expected_g,rtol=1e-5,atol=.001),'marginal affine gradient mismatch')
    constant=abs(float(offset@offset-c@c)-item['eliminated_constant']);require(constant<.001,'marginal constant mismatch');require(np.allclose(p['point'],x[1],atol=1e-12,rtol=0),'boundary linearization point')
    return dict(information_abs=float(np.max(np.abs(h-expected_h))),gradient_abs=float(np.max(np.abs(g-expected_g))),constant_abs=constant,bias_cross_max=float(np.max(np.abs(h[:3,3]))) if d==4 else None)


def prior_mean(base):
    m=base['model'];yaw=math.radians(m['initial_heading_deg']);lx,ly=m['base_to_antenna_body_xy_m'];point=[m['start_antenna_xyz_m'][0]-math.cos(yaw)*lx+math.sin(yaw)*ly,m['start_antenna_xyz_m'][1]-math.sin(yaw)*lx-math.cos(yaw)*ly,yaw];p=m['graph_parameters'];sigmas=[p['prior_position_sigma_m'],p['prior_position_sigma_m'],math.radians(p['prior_heading_sigma_deg'])]
    if base['arm']=='F3':point.append(base['angular']['bias_initial_rad_s']['value']);sigmas.append(base['angular']['bias_initial_sigma_rad_s']['value'])
    return dict(point=point,matrix=np.diag(1/np.array(sigmas)).tolist(),offset=[0.]*len(point))


def prediction(previous,local,edge,base):
    old=np.array(previous['objective_snapshot']['states'][-1]);lo=np.array(previous['local_odom']);change=np.array(local[:2])-lo[:2];a=-lo[2];body=np.array([math.cos(a)*change[0]-math.sin(a)*change[1],math.sin(a)*change[0]+math.cos(a)*change[1]]);a=old[2];out=old.copy();out[:2]+=np.array([math.cos(a)*body[0]-math.sin(a)*body[1],math.sin(a)*body[0]+math.cos(a)*body[1]])
    if base['arm']=='F0':out[2]+=wrap(local[2]-lo[2])
    elif edge['valid']:out[2]=wrap(old[2]+edge['raw_angle_rad']-old[3]*edge['dt_ns']/1e9)
    return out
