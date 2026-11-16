"""Pair-aware availability and zero-bias cost from saved final iterates."""
import csv,gzip,json,collections
from pathlib import Path
from prototype import ROOT
P=ROOT/'docs/research/midterm_simulation_s2'
u=[json.loads(x) for x in gzip.open(P/'UNITS.jsonl.gz','rt')]
rows=[]
for unit in u:
 b0=unit['results'][0]
 for r in unit['results'][1:]:
  for metric in r['metrics']:
   rows.append(dict(**{k:unit[k] for k in ['profile','seed','geometry','motion','kind','bias_m']},method=r['method'],car=metric['car'],D_last_iterate_m2=metric['D_m2'],B0_success=b0['success'],method_success=r['success'],both_success=b0['success'] and r['success']))
with (P/'PAIRED_STATUS.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
g=collections.defaultdict(list)
for r in rows:g[tuple(r[k] for k in ['profile','geometry','motion','kind','bias_m','method','car'])].append(r)
ss=[]
for key,rr in g.items():
 good=[r['D_last_iterate_m2'] for r in rr if r['both_success']]
 ss.append(dict(zip(['profile','geometry','motion','kind','bias_m','method','car'],key),n_total=len(rr),n_both_success=len(good),D_successful_pairs_mean_m2=sum(good)/len(good) if good else None,D_all_last_iterates_mean_m2=sum(r['D_last_iterate_m2'] for r in rr)/len(rr)))
with (P/'PAIRED_SUMMARY.csv').open('x') as f:
 w=csv.DictWriter(f,fieldnames=ss[0]);w.writeheader();w.writerows(ss)
print('PAIRED_SUMMARY complete; failed pairs retained')
