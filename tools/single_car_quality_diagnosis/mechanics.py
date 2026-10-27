#!/usr/bin/env python3
"""Independent geometry, angular identities, policy/retained-weight recovery."""
import argparse,json,math
from pathlib import Path
import numpy as np
from analyze_logs import load,read,dump,write_csv,wrap,SEEDS,LINKS

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--experiment',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(exist_ok=False);rows=[];recovery=[]
 for seed in SEEDS:
  rr={q:load(a.experiment,'multi_common_uwb',seed,q) for q in ('Q1','Q3')}
  for ep,p in rr['Q1']['pubs'].items():
   if p['row']['state_time_s']<3:continue
   stat={}
   for q,r in rr.items():
    s=r['pubs'][ep]['row']['objective_snapshot'];pose=s['states'][-1];prev=s['states'][-2];interval=r['pubs'][ep]['row']['angular_interval'];dt=interval['dt_ns']/1e9;inc=wrap(pose[2]-prev[2]);innovation=wrap(inc-interval['raw_angle_rad']+prev[3]*dt);model=r['config']['base']['model'];sigma=model['graph_parameters']['range_sigma_m'];lx,ly=model['base_to_antenna_body_xy_m'];c,ss=math.cos(pose[2]),math.sin(pose[2]);tag=np.array([pose[0]+c*lx-ss*ly,pose[1]+ss*lx+c*ly,model['antenna_height_m']]);dtag=np.array([-ss*lx-c*ly,c*lx-ss*ly]);H=np.zeros((2,2));jy=[];jxy=[]
    for k,raw in s['observations'][-1].items():
     v=tag-model['anchors_xyz_m'][k];dist=np.linalg.norm(v);h=v[:2]/dist;z=(dist-(raw-model['range_bias_m'][k]))/sigma;u=math.sqrt(1+z*z);scale=math.sqrt((u+1)/2)/u/sigma*math.sqrt(s['quality_weights'][-1][k]);H+=scale**2*np.outer(h,h);jxy.append(scale*h);jy.append(scale*(h@dtag))
    # UWB yaw column is a linear combination of XY columns for one antenna.
    assert np.max(np.abs(np.array(jy)-np.array(jxy)@dtag))<1e-12
    stat[q]=dict(yaw_increment=inc,bias_left=prev[3],gyro_innovation=innovation,bias_increment=pose[3]-prev[3],xy_info_min=float(np.linalg.eigvalsh(H)[0]),xy_info_max=float(np.linalg.eigvalsh(H)[1]),current_weights=s['quality_weights'][-1])
   rows.append(dict(seed=seed,t_s=p['row']['state_time_s']+.01,Q1=stat['Q1'],Q3=stat['Q3'],delta_yaw_increment=wrap(stat['Q3']['yaw_increment']-stat['Q1']['yaw_increment']),negative_delta_bias_dt=-(stat['Q3']['bias_left']-stat['Q1']['bias_left'])*dt,delta_gyro_innovation=stat['Q3']['gyro_innovation']-stat['Q1']['gyro_innovation'],xy_min_curvature_ratio_Q3_Q1=stat['Q3']['xy_info_min']/stat['Q1']['xy_info_min']))
  for sc in ('uwb_step','uwb_ramp','multi_common_uwb'):
   for q in ('Q2','Q3'):
    r=load(a.experiment,sc,seed,q);origin=json.loads((a.experiment/'inputs'/f'{sc}_seed{seed}/labels.json').read_text())['origin_epoch_ns']
    epochs=list(r['pubs']);allnormal=None;windowclear=None;rawclear=None
    for i,ep in enumerate(epochs):
     if (ep-origin)/1e9<32:continue
     if allnormal is None and all(all(r['ledger'][(ee,k)]['policy']['state']=='normal' and r['ledger'][(ee,k)]['actual_information_multiplier']==1 for k in LINKS) for ee in epochs[i:]) :allnormal=ep
     s=r['pubs'][ep]['row']['objective_snapshot']
     if windowclear is None and all(all(v==1 for v in w.values()) for w in s['quality_weights']):windowclear=ep
     # All factor support bins must be after the last injected raw sample.
     if rawclear is None and s['times_s'][0]+.01-.4>=32:rawclear=ep
    last=r['pubs'][epochs[-1]]['row']['objective_snapshot'];recovery.append(dict(scenario=sc,seed=seed,group=q,all_links_persistently_normal_state_s=(allnormal-origin)/1e9 if allnormal else None,all_links_persistently_normal_available_s=(r['avs'][allnormal]['available_receive_epoch_ns']-origin)/1e9 if allnormal else None,window_first_all_gains_unity_state_s=(windowclear-origin)/1e9 if windowclear else None,window_first_no_injected_raw_support_state_s=(rawclear-origin)/1e9 if rawclear else None,final_window_nonunit_factors=sum(v!=1 for w in last['quality_weights'] for v in w.values()),final_time_s=(epochs[-1]-origin)/1e9))
 write_csv(a.output/'angular_geometry.csv',rows);write_csv(a.output/'recovery.csv',recovery);dump(a.output/'checks.json',dict(status='PASS',one_antenna_instantaneous_yaw_column_is_XY_combination=True,angular_rows=len(rows)))
 print('PASS independent angular/geometry identities and recovery')
if __name__=='__main__':main()
