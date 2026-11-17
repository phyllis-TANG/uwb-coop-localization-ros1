#!/usr/bin/env bash
# Post-freeze descriptive diagnostic only. Does not change frozen primary statistics.
set -euo pipefail
"${PY:-python3}" - "$1" "$2" <<'PY'
import csv,gzip,collections,pathlib,sys
src=pathlib.Path(sys.argv[1]);out=pathlib.Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=False)
with gzip.open(src/'POINTS.csv.gz','rt') as f:rows=list(csv.DictReader(f))
idx={(r['id'],r['model'],r['view'],r['kind'],r['rho'],r['car'],r['epoch']):r for r in rows};groups=collections.defaultdict(list);ks=['id','condition','seed','geometry','sigma','delta','view','kind','rho','car']
for r in rows:
 if r['model']=='NL':groups[tuple(r[k] for k in ks)].append((r,idx[(r['id'],'LINEAR',r['view'],r['kind'],r['rho'],r['car'],r['epoch'])]))
seedrows=[]
for key,ps in groups.items():
 v=[(r,b) for r,b in ps if r['reason']==b['reason']=='AVAILABLE'];z=dict(zip(ks,key));z.update(planned_points=6,common_points=len(v),common_epochs=','.join(r['epoch'] for r,b in v),both_accepted=all(r['accepted']==b['accepted']=='True' for r,b in ps),NL_common_coverage=sum(r['covered']=='True' for r,b in v)/len(v) if v else None,LINEAR_common_coverage=sum(b['covered']=='True' for r,b in v)/len(v) if v else None);seedrows.append(z)
with gzip.open(out/'COMMON_AVAILABLE_PER_SEED.csv.gz','wt',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(seedrows[0]),lineterminator='\n');w.writeheader();w.writerows(seedrows)
groups=collections.defaultdict(list)
for r in seedrows:groups[tuple(r[k] for k in ks if k not in ['id','seed'])].append(r)
summary=[]
for key,rs in groups.items():
 valid=[r for r in rs if r['common_points']>0];z=dict(zip([k for k in ks if k not in ['id','seed']],key));z.update(planned_seeds=len(rs),paired_seeds=len(valid),planned_points=6*len(rs),common_points=sum(r['common_points'] for r in rs),NL_common_coverage=sum(r['NL_common_coverage'] for r in valid)/len(valid) if valid else None,LINEAR_common_coverage=sum(r['LINEAR_common_coverage'] for r in valid)/len(valid) if valid else None,interpretation='post-freeze descriptive common-availability diagnostic; no replacement of frozen full-denominator statistics');summary.append(z)
with (out/'COMMON_AVAILABLE_SUMMARY.csv').open('x',newline='') as f:
 w=csv.DictWriter(f,fieldnames=list(summary[0]),lineterminator='\n');w.writeheader();w.writerows(summary)
print('Descriptive common-availability rows:',len(seedrows),'summary rows:',len(summary),'optimizer calls: 0')
PY
