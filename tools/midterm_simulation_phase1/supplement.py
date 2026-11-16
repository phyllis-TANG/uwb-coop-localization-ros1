import json,csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parents[2]/'docs/research/midterm_simulation_phase1'
def write(name,rows):
 with (P/name).open('x') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
data=json.loads((P/'field_readback/static_pair_rows.json').read_text());runs=sorted({r['run_id'] for r in data});per=[];loo=[]
for run in runs:
 for car in ['car1','car2']:
  for arm in ['J','W025']:
   pair={p:next(r for r in data if (r['run_id'],r['car'],r['arm'],r['phase'],r['profile'])==(run,car,arm,'normal',p)) for p in ['raw','historical']}
   per.append(dict(run_id=run,geometry=run[:2],car=car,arm=arm,D_raw_m2=pair['raw']['D_m2'],D_historical_m2=pair['historical']['D_m2'],C_m2=pair['historical']['D_m2']-pair['raw']['D_m2']))
for omitted in [None]+runs:
 for car in ['car1','car2']:
  for arm in ['J','W025']:
   r=[x for x in per if x['run_id']!=omitted and x['car']==car and x['arm']==arm];a=[x['C_m2'] for x in r if x['geometry']=='G1'];b=[x['C_m2'] for x in r if x['geometry']=='G2']
   loo.append(dict(omitted=omitted or 'none',car=car,arm=arm,n_G1=len(a),n_G2=len(b),T_m2=sum(b)/len(b)-sum(a)/len(a)))
write('FIELD_ALL10_PER_RECORD.csv',per);write('FIELD_ALL10_LEAVE_ONE_RECORD.csv',loo)
fig,axes=plt.subplots(1,2,figsize=(12,4))
for ax,car in zip(axes,['car1','car2']):
 for arm in ['J','W025']:
  rs=[r for r in per if r['car']==car and r['arm']==arm];ax.plot(range(len(rs)),[r['C_m2'] for r in rs],marker='o',label=arm)
 ax.set_xticks(range(len(runs)),runs,rotation=65,ha='right');ax.axhline(0,color='black',ls='--');ax.set_title(car+' record-level C');ax.set_ylabel('C (m²)');ax.legend()
fig.tight_layout();fig.savefig(P/'FIELD_RECORDS.png',dpi=140);plt.close(fig)
s=json.loads((P/'S1_INFORMATION.json').read_text());fig,axes=plt.subplots(1,2,figsize=(11,4))
for ax,geometry in zip(axes,['good','weak']):
 for motion in ['static','straight','turn']:
  r=next(r for r in s if (r['geometry'],r['motion'],r['bias_source'],r['information'])==(geometry,motion,'peer','data_motion'))
  ax.semilogy(range(1,26),[max(x,1e-15) for x in r['singular_values']],marker='.',label=motion+' rank='+str(r['rank']))
 ax.set_title(geometry+' geometry, scaled data+motion');ax.set_xlabel('singular value index');ax.set_ylabel('singular value');ax.legend()
fig.tight_layout();fig.savefig(P/'S1_SINGULAR_VALUES.png',dpi=140)
