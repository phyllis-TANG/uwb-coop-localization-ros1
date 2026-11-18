"""All seed-cluster scatter and fixed first-seed residuals, no selections by outcome."""
from tcommon import *

def plot(seedrows,contrasts,peer,firstseed,out):
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 out=Path(out);out.mkdir();seed_count=len({r['seed'] for r in seedrows});methods=['M0','M1','M2','M3'];colors=['#777777','#2978b5','#dd6d35','#3e9651'];conditions=['normal','constant03','step03','ramp03']
 fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
 for car in [1,2]:
  ax=axes[car-1,0]
  for k,c in enumerate(conditions):
   for mi,m in enumerate(methods):
    vals=[r for r in seedrows if r['height_sigma_m']==0 and r['condition']==c and r['method']==m and r['complete_finite']]
    for r in vals:ax.scatter(k+(mi-1.5)*.18,r[f'car{car}_rmse_m'],color=colors[mi],s=16,alpha=.7,marker='o' if r['all_accepted'] else 'x')
  ax.set_xticks(range(4),conditions,rotation=20);ax.set_ylabel(f'Car{car}: seed-cluster RMSE (m)');ax.set_title('Ideal heights: all seeds, three-window clusters');ax.grid(alpha=.2)
  ax=axes[car-1,1]
  for k,c in enumerate(conditions):
   for mi,m in enumerate(['M2','M3']):
    vals=[r for r in seedrows if r['height_sigma_m']==0 and r['condition']==c and r['method']==m and r['complete_finite']]
    ax.scatter([k+(mi-.5)*.2]*len(vals),[r[f'car{car}_cov_trace_m2'] for r in vals],s=16,color=colors[mi+2],alpha=.7)
  ax.set_xticks(range(4),conditions,rotation=20);ax.set_ylabel('mean conditional XY covariance trace (m²)');ax.set_title('M2 orange / M3 green: extra-degree cost');ax.grid(alpha=.2)
 fig.suptitle('Gray M0 / blue M1 / orange M2 / green M3; x = cluster not fully accepted');fig.savefig(out/'ideal_errors_information.png',dpi=140);plt.close(fig)
 fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
 for ci,c in enumerate(['normal','ramp03']):
  for car in [1,2]:
   ax=axes[car-1,ci]
   for hi,h in enumerate([.05,.15]):
    for mi,m in enumerate(methods):
     vals=[r for r in contrasts if r['contrast']=='height_minus_zero' and r['height_sigma_m']==h and r['condition']==c and r['method']==m and r['both_complete_finite']]
     for r in vals:ax.scatter(hi+(mi-1.5)*.17,r[f'car{car}_mse_delta_m2'],s=18,color=colors[mi],alpha=.7,marker='o' if r['both_all_accepted'] else 'x')
   ax.axhline(0,color='k',lw=.7);ax.set_xticks([0,1],['0.05 m','0.15 m']);ax.set_ylabel(f'Car{car} MSE(height) - MSE(oracle) (m²)');ax.set_title(c);ax.grid(alpha=.2)
 fig.suptitle(f'All {seed_count} seed clusters: height sensitivity, not calibrated risk');fig.savefig(out/'height_all_seeds.png',dpi=140);plt.close(fig)
 fig,axes=plt.subplots(3,4,figsize=(15,9),layout='constrained')
 for w in range(3):
  for ci,c in enumerate(conditions):
   ax=axes[w,ci]
   for mi,m in enumerate(methods):
    rows=[r for r in peer if r['window']==w and r['seed']==firstseed and r['height_sigma_m']==0 and r['condition']==c and r['method']==m]
    ax.plot([r['local_time_s'] for r in rows],[r['residual_m'] for r in rows],'-o',ms=3,color=colors[mi],label=m)
   ax.axhline(0,color='k',lw=.5);ax.set_title(f'w{w}: {c}');ax.set_xlabel('local time (s)');ax.set_ylabel('peer residual (m)');ax.grid(alpha=.2)
 axes[0,0].legend();fig.suptitle(f'Fixed first seed {firstseed}, ideal heights; M0 peer unused');fig.savefig(out/'peer_first_seed.png',dpi=140);plt.close(fig)
 fig,axes=plt.subplots(2,2,figsize=(12,7),layout='constrained')
 for ci,c in enumerate(['normal','ramp03']):
  for car in [1,2]:
   ax=axes[car-1,ci]
   for hi,h in enumerate([0.,.05,.15]):
    for mi,m in enumerate(methods):
     vals=[r for r in seedrows if r['height_sigma_m']==h and r['condition']==c and r['method']==m and r['complete_finite']]
     ax.scatter([hi+(mi-1.5)*.17]*len(vals),[r[f'car{car}_benefit_m2'] for r in vals],s=15,color=colors[mi],alpha=.7)
   ax.axhline(0,color='k',lw=.7);ax.set_xticks(range(3),['0','0.05','0.15']);ax.set_xlabel('height sigma (m)');ax.set_ylabel(f'Car{car}: MSE(M0)-MSE(method) (m²)');ax.set_title(c);ax.grid(alpha=.2)
 fig.suptitle('All seed clusters: positive = cooperative gain');fig.savefig(out/'gain_all_heights.png',dpi=140);plt.close(fig)
