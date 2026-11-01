#!/usr/bin/env python3
"""Plot uploaded saved field metrics. No localization or trajectory rerun."""
import csv
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, ScalarFormatter
import numpy as np

ROOT=Path(__file__).resolve().parent
BLUE,ORANGE,PURPLE,GREY='#0072B2','#D55E00','#7B3294','#666666'
RUNS=['G1_R2_N','G1_R3_N','G2_R1_N','G2_R2_N','G2_R3_N']
plt.rcParams.update({'font.family':'STIXGeneral','mathtext.fontset':'stix','font.size':9.5,
 'axes.titlesize':10,'axes.labelsize':9.5,'xtick.labelsize':9,'ytick.labelsize':9,
 'legend.fontsize':9,'axes.linewidth':.65,'pdf.fonttype':42,'ps.fonttype':42,
 'svg.fonttype':'none','figure.facecolor':'white','axes.facecolor':'white',
 'savefig.facecolor':'white','xtick.direction':'out','ytick.direction':'out'})

def axis(ax,nonnegative=False):
 ax.spines[['top','right']].set_visible(False)
 ax.grid(axis='y',color='.87',linewidth=.45);ax.set_axisbelow(True)
 ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
 formatter=ScalarFormatter(useMathText=True);formatter.set_powerlimits((-2,3));ax.yaxis.set_major_formatter(formatter)
 if nonnegative:ax.set_ylim(bottom=0)

def save(fig,name):
 (ROOT/'figures').mkdir(exist_ok=True)
 for ext in ['pdf','svg','png']:
  fig.savefig(ROOT/'figures'/f'{name}.{ext}',**({'dpi':600} if ext=='png' else {}))
 plt.close(fig)

def main():
 source=ROOT/'data/selected_five_bag_metrics.csv'
 with source.open(newline='') as f:
  compact=list(csv.DictReader(f))
 data=[]
 for r in compact:
  data.append(dict(run_id=r['run_id'],geometry=r['geometry'],phase='normal',car=r['car'],profile=r['profile'],arm=r['arm'],
   n_common=int(r['n_common']),n_scheduled=int(r['n_scheduled']),
   independent_rmse_m=float(np.sqrt(float(r['independent_mse_m2']))),arm_rmse_m=float(np.sqrt(float(r['arm_mse_m2']))),
   paired_mean_squared_error_difference_m2=float(r['D_m2']),mean_arm_minus_I_xy_m=[float(r['mean_shift_x_m']),float(r['mean_shift_y_m'])],
   reported_reference_assumption=dict(epsilon_m=float(np.sqrt(2)*.02),lower_m2=float(r['D_sensitivity_low_m2']),upper_m2=float(r['D_sensitivity_high_m2']))))
 selected=[r for r in data if r['run_id'] in RUNS and r['phase']=='normal']
 assert len(selected)==40
 index={(r['run_id'],r['car'],r['profile'],r['arm']):r for r in selected}
 assert len(index)==40
 mse_error=max(abs(r['arm_rmse_m']**2-r['independent_rmse_m']**2-r['paired_mean_squared_error_difference_m2']) for r in data)
 envelope_error=0.
 for r in selected:
  assert r['n_common']==r['n_scheduled']==15
  e=r['reported_reference_assumption'];half=2*e['epsilon_m']*np.linalg.norm(r['mean_arm_minus_I_xy_m'])
  d=r['paired_mean_squared_error_difference_m2']
  envelope_error=max(envelope_error,abs(e['lower_m2']-(d-half)),abs(e['upper_m2']-(d+half)))
 assert max(mse_error,envelope_error)<1e-12
 fig,axes=plt.subplots(2,2,figsize=(7.16,4.95))
 fig.subplots_adjust(left=.10,right=.985,bottom=.16,top=.87,wspace=.36,hspace=.66)
 fig.legend(handles=[Line2D([],[],color=BLUE,marker='o',label='Independent (I)'),
  Line2D([],[],color=ORANGE,marker='s',ls='--',label='Cooperative (J)'),
  Line2D([],[],color=PURPLE,marker='D',label='Paired effect D')],loc='upper center',
  bbox_to_anchor=(.53,.995),ncol=3,frameon=False,handlelength=1.8,columnspacing=1.2)
 for row,car in enumerate(['car1','car2']):
  left,right=axes[row]
  left.set_title(f"({'ac'[row]}) Robot {row+1}: absolute error",pad=10)
  right.set_title(f"({'bd'[row]}) Robot {row+1}: relative effect",pad=10)
  for g,xs in [('G1',np.array([0.,1.])),('G2',np.array([3.,4.]))]:
   runs=[r for r in RUNS if r.startswith(g)];offsets=np.linspace(-.07,.07,len(runs))
   for method,colour,marker,ls in [('I',BLUE,'o','-'),('J',ORANGE,'s','--')]:
    values=[]
    for k,run in enumerate(runs):
     yy=[index[(run,car,p,'J')]['independent_rmse_m' if method=='I' else 'arm_rmse_m']**2 for p in ['raw','historical']]
     values.append(yy)
     left.plot(xs+offsets[k],yy,color=colour,marker=marker,ls=ls,alpha=.45,lw=.65,ms=3)
    left.plot(xs,np.mean(values,axis=0),color=colour,marker=marker,ls=ls,lw=1.5,ms=4.5)
   values=[]
   for k,run in enumerate(runs):
    rr=[index[(run,car,p,'J')] for p in ['raw','historical']]
    dd=np.array([r['paired_mean_squared_error_difference_m2'] for r in rr]);values.append(dd)
    low=np.array([r['reported_reference_assumption']['lower_m2'] for r in rr])
    high=np.array([r['reported_reference_assumption']['upper_m2'] for r in rr])
    right.errorbar(xs+offsets[k],dd,yerr=np.vstack([dd-low,high-dd]),color=PURPLE,
      marker='D',alpha=.5,lw=.65,ms=3,capsize=2)
   right.plot(xs,np.mean(values,axis=0),color=PURPLE,marker='D',lw=1.5,ms=4.5)
  for ax in [left,right]:
   ax.set_xlim(-.4,4.4);ax.set_xticks([0,1,3,4],['Raw','Historical','Raw','Historical'])
   ax.text(.5,-.25,'G1 (n=2)',ha='center',va='top',transform=ax.get_xaxis_transform())
   ax.text(3.5,-.25,'G2 (n=3)',ha='center',va='top',transform=ax.get_xaxis_transform())
   axis(ax,ax is left)
  left.set_ylabel(r'Position MSE (m$^2$)');right.set_ylabel(r'$D$ (m$^2$)')
  right.axhline(0,color='.15',lw=.7)
 fig.text(.5,.024,'Thin lines: bags. Bold lines: means. Whiskers: conditional reference sensitivity.',ha='center',fontsize=9)
 save(fig,'static_five_bag_main_ieee')
 effects=[]
 for car in ['car1','car2']:
  for arm in ['J','W025']:
   for run in RUNS:
    raw=index[(run,car,'raw',arm)];hist=index[(run,car,'historical',arm)]
    c=hist['paired_mean_squared_error_difference_m2']-raw['paired_mean_squared_error_difference_m2']
    shift=np.array(hist['mean_arm_minus_I_xy_m'])-raw['mean_arm_minus_I_xy_m']
    eps=hist['reported_reference_assumption']['epsilon_m'];half=2*eps*np.linalg.norm(shift)
    effects.append(dict(run_id=run,geometry=run[:2],car=car,arm=arm,C_m2=c,half_sensitivity_m2=float(half)))
 with (ROOT/'data/per_bag_calibration_effects.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(effects[0]));w.writeheader();w.writerows(effects)
 interactions=[]
 for car in ['car1','car2']:
  for arm in ['J','W025']:
   a={g:[r for r in effects if r['car']==car and r['arm']==arm and r['geometry']==g] for g in ['G1','G2']}
   means={g:float(np.mean([r['C_m2'] for r in a[g]])) for g in a}
   half=sum(float(np.mean([r['half_sensitivity_m2'] for r in a[g]])) for g in a)
   t=means['G2']-means['G1']
   interactions.append(dict(car=car,arm=arm,C_G1_m2=means['G1'],C_G2_m2=means['G2'],T_m2=t,T_low_m2=t-half,T_high_m2=t+half))
 with (ROOT/'data/interactions_recomputed.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(interactions[0]));w.writeheader();w.writerows(interactions)
 fig,axes=plt.subplots(1,2,figsize=(7.16,2.8),sharey=True)
 fig.subplots_adjust(left=.1,right=.985,bottom=.22,top=.78,wspace=.26)
 fig.legend(handles=[Line2D([],[],color=ORANGE,marker='s',label='Full peer (J)'),Line2D([],[],color=GREY,marker='^',ls='--',label='Reduced peer (W025)')],loc='upper center',ncol=2,frameon=False)
 for k,car in enumerate(['car1','car2']):
  ax=axes[k];ax.set_title(f"({'ab'[k]}) Robot {k+1}",pad=9)
  for arm,colour,marker,offset in [('J',ORANGE,'s',-.06),('W025',GREY,'^',.06)]:
   means=[]
   for j,g in enumerate(['G1','G2']):
    rr=[r for r in effects if r['car']==car and r['arm']==arm and r['geometry']==g]
    for z,r in zip(np.linspace(-.03,.03,len(rr)),rr):
     ax.errorbar(j+offset+z,r['C_m2'],yerr=r['half_sensitivity_m2'],color=colour,marker=marker,ms=3,lw=.6,alpha=.5,capsize=2)
    means.append(float(np.mean([r['C_m2'] for r in rr])))
   ax.plot(np.array([0,1])+offset,means,color=colour,marker=marker,lw=1.3,ls='-' if arm=='J' else '--')
  ax.set_xlim(-.28,1.28);ax.set_xticks([0,1],['G1 (n=2)','G2 (n=3)']);ax.axhline(0,color='.15',lw=.7);axis(ax)
 axes[0].set_ylabel(r'Calibration effect $C$ (m$^2$)')
 fig.text(.5,.025,'Points: individual bags. Whiskers: reference sensitivity, not confidence intervals.',ha='center',fontsize=9)
 save(fig,'static_calibration_effects_ieee')
 report=dict(status='PASS',source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
  source_rows=len(data),selected_rows=40,normal_bags=RUNS,common_samples_per_reported_window=15,
  max_mse_identity_error=mse_error,max_reference_envelope_error=envelope_error,
  interactions=interactions,new_localization_runs=0,
  scope='Reproduction from the 40-row sanitized figure table; original 160-row upload and trajectories are not bundled',
  reference_assumption='Operator estimate +/-2 cm per coordinate; conditional sensitivity, not certified or statistical confidence',
  mse_conversion='Square each per-bag RMSE; never square a mean of bag RMSEs')
 (ROOT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))

if __name__=='__main__':main()
