#!/usr/bin/env python3
"""Noiseless and artificial-failure acceptance. Never uses smoke seeds."""
import argparse,copy,subprocess,sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from common import ROOT,DOC,read,write,sources,clean
from model import problem,information,legacy
from solve import solve
from generate import tracks,make_input

def execute(scene,out):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 cfg=read(DOC/'CONFIG.json');sc=read(DOC/'SOLVER.json');tt,asset=tracks(scene,cfg)
 report=dict(asset=asset,source_sha256=sources(),noiseless=[],artificial={},formal_runs=0,noisy_runs=0,noiseless_optimizer_calls=0,development_actual_optimizer_calls=0)
 for track in tt:
  for bias,methods in [(0.,cfg['methods']),(.3,['M2'])]:
   obs,ref=make_input(track,cfg,dict(id='acceptance',peer_bias_m=bias,car2_motion_multiplier=1),0,noiseless=True)
   for method in methods:
    label=f"w{track['window']}-{method}-b{bias}"
    f,start,_=problem(obs,method);truth=np.array(track['antenna_xyz_m'])[:,:,:2].ravel();q=np.r_[truth,bias] if method=='M2' else truth
    r,j=f(q);assert np.max(abs(r))<1e-10
    # Evaluate away from exact truth as well; fixed offset is independent of errors.
    point=start.copy();basis=np.eye(len(point))*1e-5
    fd=np.column_stack([(f(point+e)[0]-f(point-e)[0])/2e-5 for e in basis])
    error=float(np.max(abs(fd-f(point)[1])));assert error<2e-6
    measurement=out/'measurements'/f'{label}.json';write(measurement,obs)
    write(out/'reference'/f'{label}.json',ref)
    target=out/'estimates'/f'{label}.json'
    cmd=[sys.executable,str(ROOT/'tools/moon1_localization_eval/solve.py'),'--measurement',str(measurement),'--method',method,'--solver-config',str(DOC/'SOLVER.json'),'--out',str(target)]
    proc=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True);proc.check_returncode()
    fit=read(target);report['noiseless_optimizer_calls']+=fit['optimizer_calls']
    err=float(np.max(abs(np.array(fit['estimate'])[:24]-truth)))
    assert fit['accepted'] and err<1e-6,(label,fit['status'],err)
    if method=='M2':assert abs(fit['estimate'][-1]-bias)<1e-6
    report['noiseless'].append(dict(id=label,command=cmd,status=fit['status'],position_max_abs_error_m=err,jacobian_max_error=error,truth_residual_max=float(np.max(abs(r))),data_information=information(j[:-4],sc['rank_relative_tolerance']),total_information=information(j,sc['rank_relative_tolerance'])))
 # Same-value planar special case agrees with unchanged backend r/J, no optimizer.
 obs,_=make_input(tt[0],cfg,dict(id='fixture',peer_bias_m=0,car2_motion_multiplier=1),0,True)
 planar=copy.deepcopy(obs);planar['heights_m']=np.zeros((6,2)).tolist();planar['anchors_xyz_m']=np.column_stack([np.array(obs['anchors_xyz_m'])[:,:2],np.zeros(4)]).tolist()
 old=dict(anchors=np.array(planar['anchors_xyz_m'])[:,:2].tolist(),ranges=planar['ranges_m'],movement=np.array(planar['global_xy_increments_m']).ravel().tolist(),prior_center=np.array(planar['prior_center_xy_m']).ravel().tolist(),prior_sigma=planar['prior_sigma_m'],range_sigma=planar['range_sigma_m'],motion_sigma=planar['motion_sigmas_m'][0],start=problem(planar,'M1')[1].tolist(),kind='peer')
 differences=[]
 for method,b in zip(['M0','M1','M2'],['B0','B1','B2']):
  f,start,_=problem(planar,method);g,_,_=legacy.problem(old,b)
  differences.append(max(np.max(abs(a-b)) for a,b in zip(f(start),g(start))))
 assert max(differences)<1e-12
 report['planar_legacy_max_difference']=float(max(differences))
 # Invalid field/label/value/time/scale inputs must fail before optimization.
 for label,mutate in [('missing',lambda o:o.pop('heights_m')),('truth_leak',lambda o:o.update(truth=[])),('quality_leak',lambda o:o.update(quality=[])),('nan',lambda o:o['heights_m'][0].__setitem__(0,float('nan'))),('bad_time',lambda o:o['times_s'].__setitem__(1,o['times_s'][0])),('zero_scale',lambda o:o.update(range_sigma_m=0)),('negative_range',lambda o:o['ranges_m'].__setitem__(0,-1))]:
  bad=copy.deepcopy(obs);mutate(bad);r=solve(bad,'M1',sc);assert r['status']=='INVALID_INPUT' and r['optimizer_calls']==0;report['artificial'][label]=r
 singular=information(np.zeros((74,25)),1e-8);assert singular['covariance'] is None and singular['rank']==0
 report['artificial']['rank_deficient_information']=singular
 weak=copy.deepcopy(obs);weak['anchors_xyz_m']=[[float(x),0,0] for x in [-3,-1,10,20]];weak['heights_m']=np.zeros((6,2)).tolist()
 f,_,_=problem(weak,'M2');q=np.tile([1.,0.,2.,0.],6);q=np.r_[q,0.]
 ri=information(f(q)[1][:-4],1e-8);assert ri['rank']<25 and ri['covariance'] is None;report['artificial']['collinear_data_rank']=ri
 budget=solve(obs,'M1',dict(sc,max_nfev=1));assert budget['status']=='BUDGET_EXHAUSTED';report['artificial']['budget']=budget;report['development_actual_optimizer_calls']+=1
 def boom(*a,**kw):raise RuntimeError('INTENTIONAL_EXCEPTION')
 def nonfinite(f,start,**kw):return SimpleNamespace(x=np.full_like(start,np.nan),success=True,status=1,nfev=1,njev=1,message='INTENTIONAL_NONFINITE')
 for label,fun in [('exception',boom),('nonfinite',nonfinite)]:
  r=solve(obs,'M2',sc,optimizer=fun);assert r['status']==label.upper();report['artificial'][label]=r
 # Peer perturbations cannot affect M0 objective, initialization or consumed digest.
 changed=copy.deepcopy(obs);changed['ranges_m'][8::9]=(np.array(changed['ranges_m'][8::9])+.3).tolist()
 f,q,h=problem(obs,'M0');g,z,k=problem(changed,'M0');assert h==k and np.array_equal(q,z) and all(np.array_equal(a,b) for a,b in zip(f(q),g(z)))
 report['M0_peer_independence']=True
 # An ordinary CLI explicitly refuses a reference path even if its bytes are a valid observation.
 secret=out/'reference/forbidden_measurement.json';write(secret,obs)
 proc=subprocess.run([sys.executable,str(ROOT/'tools/moon1_localization_eval/solve.py'),'--measurement',str(secret),'--method','M1','--solver-config',str(DOC/'SOLVER.json'),'--out',str(out/'must_not_exist.json')],capture_output=True,text=True)
 assert proc.returncode!=0 and 'cannot open reference' in proc.stderr and not (out/'must_not_exist.json').exists()
 report['reference_access_guard']=True
 report['passed']=True;write(out/'ACCEPTANCE.json',report)
 print('PASS',len(report['noiseless']),'noiseless runs;',report['development_actual_optimizer_calls'],'real artificial-budget solve')
 return report

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scene',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();execute(a.scene,a.out)
