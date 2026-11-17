"""Post-freeze descriptive geometry/representation diagnostic from saved records."""
import argparse,csv,collections,statistics
from fractions import Fraction as F
from common import *
def describe(src,unionfile,out):
 out.mkdir(parents=True,exist_ok=False);groups=collections.defaultdict(list)
 unions={r['case']:r for r in csv.DictReader(unionfile.open()) if r['stage']=='random'}
 for f in sorted((src/'random').glob('*_PROFILED.json.gz')):
  r=read(f);kept=OC.retained(r['result']);rects=[OC.unpack(n['box']) for n in kept]
  groups[r['case']['condition']].append(dict(exact_feasible=r['evaluation']['bias_reconstruction_at_truth_xy']['status']=='FEASIBLE_PROVED',exact_empty=r['evaluation']['bias_reconstruction_at_truth_xy']['status']=='EMPTY_PROVED',outer_contains=r['evaluation']['truth_xy_contained'],negative_candidate=any(b[1][1]<0 for b in rects),negative_inside=any(OC.unpack(n['box'])[1][1]<0 for n in kept if n['status']=='INSIDE'),radius=float(F(r['metrics']['radius_upper_m'])),union_area=float(F(unions[r['case']['id']]['new_union_area'])),upper=float(F(r['metrics']['area_upper_m2']))))
 rows=[]
 for c,rs in sorted(groups.items()):rows.append(dict(condition=c,seeds=len(rs),exact_feasible=sum(r['exact_feasible'] for r in rs),exact_empty=sum(r['exact_empty'] for r in rs),outer_contains=sum(r['outer_contains'] for r in rs),negative_candidate=sum(r['negative_candidate'] for r in rs),negative_inside=sum(r['negative_inside'] for r in rs),mean_exact_output_union_area=statistics.mean(r['union_area'] for r in rs),mean_reported_area_upper=statistics.mean(r['upper'] for r in rs),mean_radius=statistics.mean(r['radius'] for r in rs)))
 with (out/'REGION_DIAGNOSTIC.csv').open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 fig,ax=plt.subplots(1,3,figsize=(15,4));x=list(range(len(rows)))
 ax[0].bar(x,[r['mean_exact_output_union_area'] for r in rows]);ax[0].set_title('Exact area of output XY union (m²)')
 ax[1].bar(x,[r['mean_radius'] for r in rows]);ax[1].set_title('Circle enclosing ALL branches (m)')
 ax[2].plot(x,[r['exact_feasible']/r['seeds'] for r in rows],'o-',label='truth XY in exact profiled C_I');ax[2].plot(x,[r['outer_contains']/r['seeds'] for r in rows],'x-',label='truth XY in finite outer union');ax[2].set_ylim(.9,1.01);ax[2].legend(fontsize=7);ax[2].set_title('Descriptive inclusion: 100 seeds/condition')
 for a in ax:a.set_xticks(x,[r['condition'] for r in rows],rotation=35);a.grid(alpha=.2)
 fig.tight_layout();fig.savefig(out/'GEOMETRY_REPRESENTATION.png',dpi=150);plt.close(fig)
 return rows
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--union',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();print(json.dumps(describe(a.results,a.union,a.out)))
