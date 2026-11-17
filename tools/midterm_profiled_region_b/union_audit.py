"""Post-freeze descriptive exact XY union comparison. Never searches or changes regions."""
from fractions import Fraction as F
from collections import defaultdict,Counter
import argparse,time,csv
from common import *

def union(rects):
 events=defaultdict(Counter)
 for rect in set(rects):
  (a,b),(c,d)=rect;assert a<b and c<d
  events[a][c,d]+=1;events[b][c,d]-=1
 xs=sorted(events);active=Counter();slabs=[];area=F(0)
 for i,x in enumerate(xs[:-1]):
  active.update(events[x]);active=Counter({k:v for k,v in active.items() if v})
  ys=sorted(k for k,v in active.items() if v>0);merged=[]
  for a,b in ys:
   if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
   else:merged.append((a,b))
  if not merged:continue
  y=tuple(merged);end=xs[i+1];area+=(end-x)*sum(b-a for a,b in y)
  if slabs and slabs[-1][1]==x and slabs[-1][2]==y:slabs[-1]=(slabs[-1][0],end,y)
  else:slabs.append((x,end,y))
 return area,slabs

def audit(src,out):
 rows=[];begin=time.perf_counter()
 for stage in ['deterministic','random']:
  for old in sorted((src/stage).glob('*_OLD.json.gz')):
   nr=old.with_name(old.name.replace('_OLD.json.gz','_PROFILED.json.gz'))
   if not nr.exists():continue
   a,b=read(old),read(nr);assert a['case']==b['case'];rects=[];areas=[];slabs=[];times=[]
   for r in (a,b):
    t=time.perf_counter();rr=[OC.unpack(n['box'])[:2] for n in OC.retained(r['result'])];u,s=union(rr);rects.append(rr);areas.append(u);slabs.append(s);times.append(time.perf_counter()-t)
    assert F(r['metrics']['area_lower_m2'])<=u<=F(r['metrics']['area_upper_m2'])
   same=slabs[0]==slabs[1]
   sym=F(0) if same else 2*union(rects[0]+rects[1])[0]-sum(areas)
   rows.append(dict(stage=stage,case=a['case']['id'],condition=a['case']['condition'],same_closed_XY_union=same,old_union_area=str(areas[0]),new_union_area=str(areas[1]),symmetric_difference_area=str(sym),same_outer_circle=a['metrics']['radius_upper_m']==b['metrics']['radius_upper_m'],old_union_audit_seconds=times[0],new_union_audit_seconds=times[1]))
 with out.open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 return dict(pairs=len(rows),identical=sum(r['same_closed_XY_union'] for r in rows),elapsed_seconds=time.perf_counter()-begin,post_freeze_descriptive=True,search_calls=0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(audit(a.results,a.out)))
