"""Truth enters here only. Paired descriptive metrics; no parameter selection."""
import csv, json, math, time
import numpy as np
from support import *
from publication import antennas,publish

def csvwrite(p,rows):
 with Path(p).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def rms(x):return float(np.sqrt(np.mean(np.square(x)))) if len(x) else None
def wrap(x):return float(np.arctan2(np.sin(x),np.cos(x)))
def main():
 series=[];costs=[];snapshots=[];snapcontrast=[];bycase={}
 for case in SET['cases']:
  cfg=config(case);truth={r['time_s']:r for r in read(EVIDENCE/'inputs'/case/'truth.jsonl')};data={m:old(case,m) for m in SET['reuse_methods']};data['N']=read(OUT/'v1'/(case+'__N.jsonl.gz'));ref=data['I'];derivedtimes={}
  for m,b in SET['publication_budgets_m'].items():
   src=data['N' if m=='Nclip' else 'J'];rows=[];tic=time.perf_counter()
   for r,i in zip(src,ref):
    d=publish(r,i,cfg,b);rows.append(dict(r,pose=d['pose'],publication_mode=d['mode'],budget_certified=d['budget_certified'],main_accepted_graph=r['accepted_graph'],accepted_graph=False,joint_optimization_success=False,covariance=None,derived_budgets=b))
   data[m]=rows;derivedtimes[m]=time.perf_counter()-tic
  common=set.intersection(*[{r['state_time_s'] for r in rows if r.get('main_accepted_graph',r['accepted_graph'])} for rows in data.values()])
  for m,rows in data.items():
   for r,i in zip(rows,ref):
    t=r['state_time_s'];p=r['pose'];finite=p is not None and bool(np.isfinite(p).all());known=i['accepted_graph'];mode=r.get('publication_mode',('independent' if m=='I' else 'normal_joint') if r['accepted_graph'] else 'unknown');a=antennas(p,cfg) if finite else None;b=antennas(i['pose'],cfg);tr=truth[t];ta=np.array([tr['cars'][c]['antenna_xyz_m'] for c in ('car1','car2')]);state=np.array(p).reshape(2,3) if finite else None;s=r['snapshot'];M=np.array(s['prior']['matrix']);prov=r.get('provenance',{});win=prov.get('window_peer_times_s',prov.get('window_peer_factor_ids',[]));prior=prov.get('prior_peer_times_s',prov.get('prior_peer_factor_ids',[]))
    budgets=SET['publication_budgets_m'].get(m,[.04,.04] if m in ('C004','K004') else [None,None])
    for k,c in enumerate(('car1','car2')):
     err=float(np.linalg.norm(a[k]-ta[k,:2])) if finite else None;ie=float(np.linalg.norm(b[k]-ta[k,:2]));disp=float(np.linalg.norm(a[k]-b[k])) if finite else None
     series.append(dict(case=case,method=m,car=c,t_s=t,state_epoch_ns=r['state_epoch_ns'],cutoff_epoch_ns=r['availability_cutoff_epoch_ns'],finite=finite,common_accepted=t in common,main_accepted=r.get('main_accepted_graph',r['accepted_graph']),reference_accepted=known,mode=mode,status=r['status'],joint_success=r.get('joint_optimization_success',r['accepted_graph'] and m not in ('I',)),antenna_x_m=None if a is None else a[k,0],antenna_y_m=None if a is None else a[k,1],yaw_rad=None if state is None else state[k,2],xy_error_m=err,yaw_error_rad=None if state is None else wrap(state[k,2]-tr['cars'][c]['pose'][2]),reference_error_m=ie,help_m=None if err is None else max(0,ie-err),harm_m=None if err is None else max(0,err-ie),separation_m=disp,budget_m=budgets[k],budget_violation_m=None if budgets[k] is None or not known or disp is None else max(0,disp-budgets[k]),relative_xy_error_m=None if a is None else float(np.linalg.norm((a[0]-a[1])-(ta[0,:2]-ta[1,:2]))),distance_error_m=None if a is None else float(np.sqrt(np.sum((a[0]-a[1])**2)+(ta[0,2]-ta[1,2])**2)-np.linalg.norm(ta[0]-ta[1])),window_peer_n=len(win),prior_peer_n=len(prior),cross_information_norm=float(np.linalg.norm((M.T@M)[:3,3:])),actual_new_peer=r['peer_factor_used']))
   costs.append(dict(case=case,method=m,kind='current_replay' if m=='N' else 'derived_no_estimator' if m in derivedtimes else 'verified_reuse',n=len(rows),main_total_s=sum(r.get('main_update_wall_s',r['update_wall_s']) for r in rows),reference_total_s=sum(r.get('reference_update_wall_s',i['update_wall_s'] if m in derivedtimes else 0) for r,i in zip(rows,ref)),derived_total_s=derivedtimes.get(m),timing_note='virtual; historical baseline timings are not current-machine speed comparisons; derived main/reference cost inherited'))
  bycase[case]=data
  sn={};snr={}
  for pn in SET['snapshot_priors']:
   for xn in SET['snapshot_initializations']:
    r=read(OUT/'v1'/(case+'__prior'+pn+'__init'+xn+'.jsonl.gz'))[0];sn[pn,xn]=r['snapshot'];snr[pn,xn]=r;st=np.array(r['snapshot']['states']);a=antennas(st[-1],cfg);s=r['snapshot'];M=np.array(s['prior']['matrix']);oldn=data['N'][58]['snapshot'];commonpoint=np.array(oldn['states'][0]);delta=commonpoint-np.array(s['prior']['point']);delta[[2,5]]=np.arctan2(np.sin(delta[[2,5]]),np.cos(delta[[2,5]]));grad=M.T@(M@delta+np.array(s['prior']['offset']))
    for k,c in enumerate(('car1','car2')):snapshots.append(dict(case=case,prior=pn,init=xn,car=c,t_s=59,success=r['success'],status=r['status'],nfev=r['nfev'],cost=r['cost'],optimality=r['optimality'],eliminated_constant=s['eliminated_constant'],xy_error_m=float(np.linalg.norm(a[k]-truth[59]['cars'][c]['antenna_xyz_m'][:2])),yaw_error_rad=wrap(st[-1,k*3+2]-truth[59]['cars'][c]['pose'][2]),antenna_x_m=a[k,0],antenna_y_m=a[k,1],cross_information_norm=float(np.linalg.norm((M.T@M)[:3,3:])),commonpoint_prior_gradient_norm=float(np.linalg.norm(grad[k*3:k*3+3]))))
  for name,l,r in [('change_prior_initN',('N','N'),('I','N')),('change_prior_initI',('N','I'),('I','I')),('change_init_priorN',('N','N'),('N','I')),('change_init_priorI',('I','N'),('I','I')),('sham_N_reopt',None,('N','N')),('sham_I_reopt',None,('I','I'))]:
   left=(data['N' if name=='sham_N_reopt' else 'I'][58]['snapshot'] if l is None else sn[l]);right=sn[r];pl=np.array(left['states']);pr=np.array(right['states']);al=antennas(pl[-1],cfg);ar=antennas(pr[-1],cfg)
   for k,c in enumerate(('car1','car2')):
    d=pr[:,3*k:3*k+3]-pl[:,3*k:3*k+3];d[:,2]=np.arctan2(np.sin(d[:,2]),np.cos(d[:,2]));snapcontrast.append(dict(case=case,contrast=name,car=c,current_xy_shift_m=float(np.linalg.norm(ar[k]-al[k])),current_yaw_shift_rad=wrap(pr[-1,3*k+2]-pl[-1,3*k+2]),window_max_scalar_shift_m_rad=float(np.max(abs(d))),review_tolerance=SET['snapshot_path_review_m_rad'],path_within_tolerance=None if name.startswith('change_prior') else bool(np.max(abs(d))<=SET['snapshot_path_review_m_rad'])))
 metrics=[]
 for case,data in bycase.items():
  for m in data:
   for c in ('car1','car2'):
    rr=[r for r in series if r['case']==case and r['method']==m and r['car']==c]
    for phase,(lo,hi) in SET['periods'].items():
     total=[r for r in rr if lo<=r['t_s']<hi]
     for scope in ('all_finite','common_accepted'):
      selected=[r for r in total if r['finite'] and (scope=='all_finite' or r['common_accepted'])];vals=lambda key:[r[key] for r in selected if r[key] is not None]
      metrics.append(dict(case=case,method=m,car=c,phase=phase,scope=scope,denominator=len(total),n=len(selected),xy_rmse_m=rms(vals('xy_error_m')),yaw_rmse_rad=rms(vals('yaw_error_rad')),relative_xy_rmse_m=rms(vals('relative_xy_error_m')),distance_rmse_m=rms(vals('distance_error_m')),mean_help_m=float(np.mean(vals('help_m'))) if selected else None,mean_harm_m=float(np.mean(vals('harm_m'))) if selected else None,max_separation_m=max(vals('separation_m'),default=None),max_budget_violation_m=max(vals('budget_violation_m'),default=None),unknown=sum(r['mode']=='unknown' for r in total),fallback=sum(r['mode']=='reference_fallback' for r in total),failed=sum('failed' in r['status'] or 'error' in r['status'] for r in total),joint_success=sum(r['joint_success'] for r in total)))
 contrasts=[]
 for r in metrics:
  for kind,case,method in [('same_input_vs_I',r['case'],'I')]+([('same_method_fault_vs_nominal',SET['cases'][0],r['method'])] if r['case']!=SET['cases'][0] else []):
   other=next(x for x in metrics if x['case']==case and x['method']==method and all(x[k]==r[k] for k in ('car','phase','scope')));assert r['n']==other['n']
   contrasts.append({k:r[k] for k in ('case','method','car','phase','scope','n')}|dict(contrast=kind,delta_xy_rmse_m=r['xy_rmse_m']-other['xy_rmse_m'],delta_yaw_rmse_rad=r['yaw_rmse_rad']-other['yaw_rmse_rad']))
 for name,rs in [('TIMESERIES',series),('METRICS',metrics),('CONTRASTS',contrasts),('COSTS',costs),('SNAPSHOTS',snapshots),('SNAPSHOT_CONTRASTS',snapcontrast)]:csvwrite(DOC/(name+'.csv'),rs)
 # Every published bound is checked at the antenna, including asymmetric zero budget.
 assert max(r['budget_violation_m'] or 0 for r in series)<=SET['budget_atol_m']
 import matplotlib;matplotlib.use('Agg');import matplotlib.pyplot as plt
 fig,ax=plt.subplots(2,2,figsize=(11,6),sharex=True)
 for col,case in enumerate(SET['cases']):
  for k,c in enumerate(('car1','car2')):
   for m in ('I','J','C004','K004','N','Nclip'):
    rr=[r for r in series if r['case']==case and r['method']==m and r['car']==c];ax[k,col].plot([r['t_s'] for r in rr],[1000*r['xy_error_m'] for r in rr],label=m,linewidth=1)
   ax[k,col].axvspan(24,38,color='grey',alpha=.13);ax[k,col].axvline(39,color='black',ls='--',lw=.7);ax[k,col].axvline(59,color='black',ls=':',lw=.7);ax[k,col].set_ylabel(c+' antenna XY error (mm)');ax[k,col].grid(alpha=.2)
  ax[0,col].set_title(case);ax[1,col].set_xlabel('State time (s); virtual cutoff = state + 1s')
 ax[0,0].legend(ncol=3,fontsize=8);fig.tight_layout();fig.savefig(DOC/'RECOVERY.png',dpi=160);plt.close(fig)
 fig,ax=plt.subplots(2,2,figsize=(11,6),sharex=True)
 for col,case in enumerate(SET['cases']):
  for m in ('J','N','Nclip'):
   rr=[r for r in series if r['case']==case and r['method']==m and r['car']=='car2'];ax[0,col].plot([r['t_s'] for r in rr],[1000*r['separation_m'] for r in rr],label=m);ax[1,col].plot([r['t_s'] for r in rr],[r['cross_information_norm'] for r in rr],label=m)
  ax[0,col].axhline(40,color='grey',ls=':');ax[0,col].set_title(case)
  for a in ax[:,col]:a.axvline(39,color='black',ls='--',lw=.7);a.axvline(59,color='black',ls=':',lw=.7);a.grid(alpha=.2)
  ax[1,col].set_xlabel('State time (s)')
 ax[0,0].set_ylabel('Car2 displacement from I (mm)');ax[1,0].set_ylabel('Prior cross-information Frobenius norm\n(mixed coordinates; not an error bound)');ax[0,0].legend();fig.tight_layout();fig.savefig(DOC/'HISTORY.png',dpi=160);plt.close(fig)
 print('Exported descriptive metrics, all 8 snapshots, budget checks and plots')
if __name__=='__main__':main()
