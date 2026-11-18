"""Read delivered CSVs only, recompute aggregates without optimizer/generator imports."""
import csv,json,math
from pathlib import Path
D=Path(__file__).resolve().parents[2]/'docs/research/lunar_end_to_end'
def read(n):return list(csv.DictReader((D/n).open()))
full=read('FULL_RESULTS.csv');summary=read('SUMMARY.csv');pairs=read('PAIRS.csv');paired=read('PAIRED_SUMMARY.csv');checks=0
for row in summary:
 selected=[r for r in full if all(r[k]==row[k] for k in ['group','peer','motion','sensitivity','method','car'])];assert len(selected)==int(row['planned_methods']);assert sum(r['state']=='ACCEPTED' for r in selected)==int(row['accepted']);cluster=[]
 for seed in sorted({r['seed'] for r in selected}):
  block=[r for r in selected if r['seed']==seed]
  if len(block)==3 and all(r['finite']=='True' for r in block) and (row['subset']=='all_finite' or all(r['state']=='ACCEPTED' for r in block)):cluster.append(sum(float(r['rmse_m']) for r in block)/3)
 assert len(cluster)==int(row['seed_clusters'])
 if cluster:assert math.isclose(sum(cluster)/len(cluster),float(row['mean_window_rmse_m']),abs_tol=1e-12)
 checks+=1
# Individual gains are independently joined to the full delivered run table.
lookup={tuple(r[k] for k in ['window','seed','peer','motion','sensitivity','method','car']):r for r in full}
for p in pairs:
 key=tuple(p[k] for k in ['window','seed','peer','motion','sensitivity','method','car']);a=lookup[key];bkey=list(key)
 if p['kind']=='gain_vs_M0':bkey[5]='M0'
 elif p['kind']=='gain_M3_vs_M2':bkey[5]='M2'
 else:bkey[4]='control'
 b=lookup[tuple(bkey)];assert (a['state']==b['state']=='ACCEPTED')==(p['both_accepted']=='True');assert math.isclose(float(b['rmse_m'])-float(a['rmse_m']),float(p['gain_m']),abs_tol=1e-12);checks+=1
for row in paired:
 subset=[p for p in pairs if all(p[k]==row[k] for k in ['kind','peer','motion','sensitivity','method','car'])];assert len(subset)==int(row['total_pairs']);assert sum(p['both_accepted']=='True' for p in subset)==int(row['both_accepted_pairs']);clusters=[]
 for seed in sorted({p['seed'] for p in subset}):
  block=[p for p in subset if p['seed']==seed]
  if len(block)==3 and all(p['both_finite']=='True' for p in block) and (row['subset']=='all_finite' or all(p['both_accepted']=='True' for p in block)):clusters.append(sum(float(p['gain_m']) for p in block)/3)
 assert len(clusters)==int(row['seed_clusters'])
 if clusters:assert math.isclose(sum(clusters)/len(clusters),float(row['mean_gain_m']),abs_tol=1e-12)
 checks+=1
result=dict(passed=True,full_rows=len(full),summary_rows=len(summary),individual_pairs=len(pairs),paired_summary_rows=len(paired),checks=checks,optimizer_calls=0)
(D/'TABLE_READBACK.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
