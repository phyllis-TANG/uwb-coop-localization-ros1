import json,gzip,csv,hashlib,subprocess
from pathlib import Path
P=Path(__file__).resolve().parents[2]/'docs/research/integrity_recovery_window_20261030';ROOT=P.parents[2]
receipt={}
for name in ['README.txt','TARGET_CARD.txt','REPRODUCTION.txt']:
 path='docs/research/research_convergence_20261030/'+name
 data=subprocess.check_output(['git','show','origin/main:'+path],cwd=ROOT)
 receipt[path]=dict(git_blob=subprocess.check_output(['git','rev-parse','origin/main:'+path],cwd=ROOT,text=True).strip(),sha256=hashlib.sha256(data).hexdigest())
manifest=json.loads((ROOT/'tools/cooperative_peer_gate_probe_20261028/frozen_manifest.json').read_text())
for path,expected in manifest['files'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==expected
receipt['kernel']=manifest;receipt['base_commit']='7001d33da1f77875aa9cd2adbd7ffd155bc13610';receipt['main_read']=subprocess.check_output(['git','rev-parse','origin/main'],cwd=ROOT,text=True).strip()
(P/'SOURCE_RECEIPTS.json').write_text(json.dumps(receipt,indent=2)+'\n')
for condition in ['nominal','wall_long']:
 records=json.load(gzip.open(P/condition/'audit.json.gz','rt'));factors=[]
 for r in records:
  for role,g in r['graphs'].items():
   snapshot=g['snapshot'];wall=[]
   for t,obs in zip(snapshot['times_s'],snapshot['observations']):
    for car in ['car1','car2']:
     if obs[car]:wall.append(dict(bin_s=t,car=car,anchors=list(obs[car]),**g['factor_sources'][str(t)][car]))
   factors.append(dict(t_s=r['t_s'],graph=role,wall_factors=wall,peer_factor_bins=[t for t,v in zip(snapshot['times_s'],snapshot['peers_m']) if snapshot['peer_enabled'] and v is not None],prior_primitive_columns=g['primitive']['prior_noise_columns'],consumed_ids=g['primitive']['consumed_ids']))
 with gzip.open(P/condition/'FACTOR_INDEX.json.gz','wt') as f:json.dump(factors,f)
# Read-only plot: source hypotheses are not assigned fault truth.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
s=list(csv.DictReader((P/'SOURCE_GROUPS.csv').open()));fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True)
for ax,car in zip(axes,['car1','car2']):
 for group in ['car1_absolute','car2_absolute','peer']:
  rows=[r for r in s if r['condition']=='wall_long' and r['car']==car and r['source_group']==group and r['computable']=='True']
  ax.plot([float(r['t_s']) for r in rows],[float(r['statistic']) for r in rows],label=group)
 ax.axhline(11.407564949312402,color='black',ls='--');ax.axvspan(24,52,alpha=.1,color='red');ax.axvline(68,color='green',ls=':');ax.axvline(73,color='grey',ls=':');ax.set_ylabel(car+' SS statistic');ax.legend()
axes[-1].set_xlabel('state time (s); green: Car2 available; grey: last fault bin exits');fig.tight_layout();fig.savefig(P/'RECOVERY.png',dpi=140)
