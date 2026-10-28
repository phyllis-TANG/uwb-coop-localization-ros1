#!/usr/bin/env python3
"""Compact plots/tables for every preregistered cell; no estimation."""
import argparse,csv,gzip,json,shutil
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import METHODS,SCENARIOS,sha,dump
COLORS={'I':'#777777','J':'#ce7b13','W025':'#8f5cb3','C004':'#2869bd','K004':'#168361','U':'#bf4967','C100':'#79a3dc','K100':'#50bdad'}
def rows(p):
 with (gzip.open(p,'rt') if str(p).endswith('.gz') else open(p)) as f:return list(csv.DictReader(f))
def make(inp,out):
 out.mkdir(exist_ok=False);(out/'figures').mkdir();(out/'results').mkdir()
 for name in ['metrics.csv','contrasts.csv','costs.csv','solver_controls.csv','receipt.json','audits.json']:shutil.copyfile(inp/name,out/'results'/name)
 data=rows(inp/'timeline.csv.gz');metrics=rows(inp/'metrics.csv');cost=rows(inp/'costs.csv')
 table=['# 全部预登记单元结果','','天线XY是主指标，base XY/yaw另列。help/harm为每时刻max(e_I−e_pub,0)/max(e_pub−e_I,0)的平均，非团队平均；RMSE以真值计算。下表reference_accepted口径，全部有限含两次unknown启动的口径保留在results/metrics.csv。每包原分母63，reference有效61；fault14，recovery10，late16，pre21。','']
 for s in SCENARIOS:
  table+=['## '+s,'','|段|方法|车|n/分母|天线XY RMSE m|base XY RMSE m|yaw RMSE rad|平均帮助 m|平均损害 m|最大相对I位移 m|超过4cm量 m|','|---|---|---|---|---|---|---|---|---|---|---|']
  for period in ['all','pre','fault','recovery','late']:
   for m in METHODS:
    for r in [r for r in metrics if r['scenario']==s and r['method']==m and r['period']==period and r['scope']=='reference_accepted']:
     keys=['antenna_xy_rmse_m','base_xy_rmse_m','yaw_rmse_rad','mean_help_m','mean_harm_m','max_separation_m','max_excess004_m']
     table.append('|'+ '|'.join([period,m,r['car'],r['n']+'/'+r['denominator']]+[f'{float(r[k]):.7f}' for k in keys])+'|')
  table+=['']
 table+=['## 状态、可用率与计算账目','','独立I没有联合成功；C的post_clip不记联合成功，但仍为有限可用发布。C主图与参照为历史计算，clip为本次派生处理（含记录复制），三者不冒充同期回放。新图主耗时包含求解/消元，私有参考另列，虚拟时序不是ROS实时延迟。','','|场景|方法|有限/原分母|参照有效|联合成功|裁剪|回退|unknown|失败|超时|主图s|参照s|新增裁剪处理s|计算来源|','|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
 for r in cost:table.append('|'+ '|'.join([r['scenario'],r['method'],r['finite']+'/'+r['denominator']]+[r[k] for k in ['reference_accepted','joint_success','post_clip','fallback','unknown','failure','timeout']]+[f'{float(r[k]):.6f}' for k in ['main_total_s','reference_total_s','clip_total_s']]+[r['timing_origin']])+'|')
 table+=['','## 宽松预算与求解器关闭对照','','|场景|对照|车|n|最大天线差 m|RMS天线差 m|','|---|---|---|---|---|---|']
 for r in rows(inp/'solver_controls.csv'):table.append('|'+ '|'.join([r[k] for k in ['scenario','comparison','car','n']]+[f'{float(r[k]):.9f}' for k in ['max_antenna_difference_m','rms_antenna_difference_m']])+'|')
 (out/'TABLES.md').write_text('\n'.join(table)+'\n')
 selected=['I','J','W025','C004','K004']
 for s in SCENARIOS:
  fig,axs=plt.subplots(3,2,figsize=(12,10),sharex=True)
  for m in selected:
   rs=[r for r in data if r['scenario']==s and r['method']==m];t=[float(r['t_s']) for r in rs]
   for j,car in enumerate(['car1','car2']):
    axs[0,j].plot(t,[float(r[car+'_antenna_xy_error_m']) for r in rs],label=m,color=COLORS[m],lw=1.4)
    axs[1,j].plot(t,[float(r[car+'_separation_m']) for r in rs],color=COLORS[m],lw=1.4)
    axs[2,j].plot(t,[float(r[car+'_help_m'])-float(r[car+'_harm_m']) for r in rs],color=COLORS[m],lw=1.4)
  for j,car in enumerate(['Car1','Car2']):
   axs[0,j].set_title(car);axs[1,j].axhline(.04,c='black',ls='--',lw=.8,label='development budget 0.04 m');axs[2,j].axhline(0,c='black',lw=.8)
   for i,label in enumerate(['Antenna XY true error [m]','Displacement from independent [m]','Help (+) / harm (-) vs independent [m]']):
    ax=axs[i,j];ax.set_ylabel(label);ax.grid(alpha=.2);ax.axvspan(1,3,color='grey',alpha=.12)
    if s!='nominal':ax.axvspan(24,38,color='#e9b349',alpha=.16);ax.axvline(48,c='grey',ls=':')
   axs[2,j].set_xlabel('State time [s]; virtual availability t + 1 s')
  axs[0,0].legend(ncol=5);axs[1,0].legend(fontsize=8);fig.suptitle(s+' / seed101 / all finite publications')
  fig.text(.5,.01,'Grey startup is unknown, not a certified budget or joint optimization success. C is output clipping; K is constrained optimization.',ha='center',fontsize=9)
  fig.tight_layout(rect=(0,.03,1,.97));fig.savefig(out/'figures'/f'{s}.png',dpi=145);plt.close(fig)
 fig,axs=plt.subplots(2,2,figsize=(12,8),sharex=True)
 for i,s in enumerate(SCENARIOS):
  k=[r for r in data if r['scenario']==s and r['method']=='K004'];cl=[r for r in data if r['scenario']==s and r['method']=='C004'];w=[r for r in data if r['scenario']==s and r['method']=='W025']
  for car,co in [('car1','#bf7b28'),('car2','#275caa')]:
   key=car+'_antenna_xy_error_m';t=[float(r['t_s']) for r in k];axs[i,0].plot(t,[(float(a[key])-float(b[key]))*1000 for a,b in zip(k,cl)],label=car,color=co);axs[i,1].plot(t,[(float(a[key])-float(b[key]))*1000 for a,b in zip(k,w)],label=car,color=co)
  for j in range(2):
   ax=axs[i,j];ax.axhline(0,c='black',lw=.7);ax.grid(alpha=.2);ax.set_ylabel('True-error difference [mm]');ax.set_title(s+' | K004 minus '+('C004' if j==0 else 'W025'));ax.legend()
   if s!='nominal':ax.axvspan(24,38,color='#e9b349',alpha=.15);ax.axvline(48,c='grey',ls=':')
   if i==1:ax.set_xlabel('State time [s]')
 fig.suptitle('Positive = candidate worse; exact same epochs, no trajectory alignment');fig.tight_layout();fig.savefig(out/'figures'/'candidate_differences.png',dpi=150);plt.close(fig)
 # All new solver paths and historical/derived timing separately identified.
 fig,axs=plt.subplots(1,2,figsize=(12,4))
 for ax,s in zip(axs,SCENARIOS):
  rs=[r for r in cost if r['scenario']==s and r['kind']=='new'];x=np.arange(len(rs));ax.bar(x,[float(r['main_total_s']) for r in rs],label='main graph');ax.bar(x,[float(r['reference_total_s']) for r in rs],bottom=[float(r['main_total_s']) for r in rs],label='private reference');ax.set_xticks(x,[r['method'] for r in rs]);ax.set_title(s);ax.set_ylabel('Current offline processing [s] / 63 epochs');ax.legend()
 fig.tight_layout();fig.savefig(out/'figures'/'current_compute.png',dpi=150);plt.close(fig)
 dump(out/'PRESENTATION.json',dict(script_sha256=sha(Path(__file__)),evaluation_receipt_sha256=sha(inp/'receipt.json'),estimator_runs=0,all_16_cells_in_tables=True))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--evaluation',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();make(a.evaluation,a.output)
