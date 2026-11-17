"""Seed-cluster descriptive summaries. Never treat initializations or points as independent n."""
from common import *
import argparse,collections

def num(v):return float(v) if v not in ('',None) else None
def desc(vals):
 a=np.array([v for v in vals if v is not None and np.isfinite(v)],float)
 return dict(valid_seeds=len(a),mean=float(a.mean()) if len(a) else None,p025=float(np.quantile(a,.025)) if len(a) else None,p975=float(np.quantile(a,.975)) if len(a) else None,min=float(a.min()) if len(a) else None,max=float(a.max()) if len(a) else None)
def main(src,out):
 out.mkdir(parents=True,exist_ok=False);rs=readcsv(src/'DECOMPOSITION.csv.gz');points=readcsv(src/'REGIONS.csv.gz')
 # Retain historical curvature comparison as descriptive association, no changed labels.
 old=collections.defaultdict(list)
 with gzip.open(B/'POINTS.csv.gz','rt') as f:
  for p in csv.DictReader(f):
   if p['model']=='NL' and p['view']=='GN' and p['kind']=='curvature_ellipse':old[p['id'],int(p['car'])].append(p)
 for r in rs:
  if r['batch']=='PR121':
   for car in [1,2]:
    ps=old[r['id'],car];assert len(ps)==6
    r[f'old_coverage95_car{car}']=str(sum(p['covered']=='True' for p in ps)/6);r[f'old_area95_car{car}']=str(np.mean([float(p['area']) for p in ps if p['reason']=='AVAILABLE']))
 metrics=[k for k in rs[0] if k.endswith(('_rms','_norm','_bias','_bias_abs')) or k in ['condition_j','condition_h','gradient_inf','position_cancellation','old_coverage95_car1','old_coverage95_car2','old_area95_car1','old_area95_car2','accepted_groups','finite_groups']]
 seedrows=[];groups=collections.defaultdict(list)
 for r in rs:groups[r['batch'],r['condition'],r['method']].append(r)
 for key,rr in groups.items():
  modes=['all_finite','accepted']+(['original','selected','selected_group'] if key[0]=='PR119' else [])
  for mode in modes:
   choose=lambda r:mode=='all_finite' or (r['accepted']=='True' if mode=='accepted' else r[mode]=='True')
   byseed=collections.defaultdict(list)
   for r in rr:byseed[r['seed']].append(r)
   for seed,allr in byseed.items():
    sel=[r for r in allr if choose(r)];row={k:rr[0][k] for k in ['batch','condition','method','geometry','perturbation_m','sigma','offset_m']};row.update(mode=mode,seed=seed,planned_candidates=len(allr),subset_candidates=len(sel),available_candidates=len(sel),accepted_candidates=sum(r['accepted']=='True' for r in allr))
    for metric in metrics:
     vals=[num(r.get(metric)) for r in sel];vals=[x for x in vals if x is not None];row[metric]=np.mean(vals) if vals else None
    seedrows.append(row)
 table(out/'DECOMPOSITION_SEEDS.csv',seedrows)
 sums=[];gg=collections.defaultdict(list)
 for r in seedrows:gg[r['batch'],r['condition'],r['method'],r['mode']].append(r)
 for _,rr in gg.items():
  base={k:rr[0][k] for k in ['batch','condition','method','geometry','perturbation_m','sigma','offset_m','mode']};base.update(planned_seeds=len(rr),planned_candidates=sum(r['planned_candidates'] for r in rr),subset_candidates=sum(r['subset_candidates'] for r in rr),available_candidates=sum(r['available_candidates'] for r in rr))
  for metric in metrics:sums.append(dict(**base,metric=metric,**desc([r[metric] for r in rr])))
 table(out/'DECOMPOSITION_SUMMARY.csv',sums)
 # Per-seed associations are separate by batch/condition/method/mode; not causal contribution estimates.
 ass=[]
 for key,rr in gg.items():
  for car in [1,2]:
   for xfield in ['difference_position_rms','remainder_position_rms','jacobian_position_rms','gradient_position_rms','position_cancellation','accepted_groups']:
    for yfield in [f'old_coverage95_car{car}',f'old_area95_car{car}']:
     pairs=[(r[xfield],r[yfield]) for r in rr if r.get(xfield) is not None and r.get(yfield) is not None];a=np.array(pairs);valid=len(a)>2 and np.std(a[:,0])>1e-14 and np.std(a[:,1])>1e-14
     ass.append(dict(batch=key[0],condition=key[1],method=key[2],mode=key[3],car=car,x=xfield,y=yfield,seeds=len(pairs),pearson=float(np.corrcoef(a.T)[0,1]) if valid else None,reason='DESCRIPTIVE' if valid else 'CONSTANT_OR_INSUFFICIENT'))
 table(out/'ASSOCIATIONS.csv',ass)
 # Point tables grouped before aggregation; all twelve positions are one seed cluster.
 groups=collections.defaultdict(list)
 for p in points:groups[tuple(p[k] for k in ['id','model','scope','kind','rho'])].append(p)
 per=[]
 for key,pp in groups.items():
  assert len(pp)==12
  for car in [0,1,2]:
   ps=[p for p in pp if car==0 or int(p['car'])==car];available=[p for p in ps if p['reason']=='AVAILABLE'];hit=sum(p['covered']=='True' for p in available);base={k:ps[0][k] for k in ['id','condition','seed','geometry','sigma','offset_m','method','model','scope','kind','rho','in_set','accepted','category']}
   per.append(dict(**base,car=car,planned_points=len(ps),available_points=len(available),unavailable_points=len(ps)-len(available),covered_points=hit,coverage_available=hit/len(available) if available else None,coverage_planned=hit/len(ps),all_available=len(available)==len(ps),all_covered=len(available)==len(ps) and hit==len(ps),radius_mean=np.mean([float(p['radius']) for p in available]) if available else None,area_mean=np.mean([float(p['area']) for p in available]) if available else None,unavailable_reasons=';'.join(sorted({p['reason'] for p in ps if p['reason']!='AVAILABLE'}))))
 table(out/'REGION_SEEDS.csv.gz',per);sg=collections.defaultdict(list)
 for r in per:sg[tuple(r[k] for k in ['condition','model','scope','kind','rho','car'])].append(r)
 sums=[]
 for key,rr in sg.items():
  for subset in ['all','accepted']:
   sel=[r for r in rr if subset=='all' or r['accepted']=='True'];av=sum(r['available_points'] for r in sel);hit=sum(r['covered_points'] for r in sel);plan=sum(r['planned_points'] for r in rr);nsub=sum(r['planned_points'] for r in sel)
   z={k:rr[0][k] for k in ['condition','geometry','sigma','offset_m','method','model','scope','kind','rho','car']};z.update(subset=subset,planned_seeds=len(rr),subset_seeds=len(sel),planned_points=plan,subset_points=nsub,available_points=av,unavailable_points=nsub-av,covered_points=hit,in_set_seeds=sum(r['in_set']=='True' for r in sel),coverage_available=hit/av if av else None,coverage_full_plan=hit/plan,coverage_subset=hit/nsub if nsub else None,fully_available_seeds=sum(r['all_available'] for r in sel),all_covered_seeds=sum(r['all_covered'] for r in sel),all_covered_full_plan=sum(r['all_covered'] for r in sel)/len(rr),all_covered_subset=sum(r['all_covered'] for r in sel)/len(sel) if sel else None,radius_mean=np.mean([r['radius_mean'] for r in sel]) if sel else None,area_mean=np.mean([r['area_mean'] for r in sel]) if sel else None,unavailable_reasons=';'.join(sorted({r['unavailable_reasons'] for r in sel if r['unavailable_reasons']})))
   # Empirical spread of seed point averages, NOT a confidence interval.
   ds=desc([r['coverage_planned'] for r in sel]);z.update(seed_coverage_p025=ds['p025'],seed_coverage_p975=ds['p975']);sums.append(z)
 table(out/'REGION_SUMMARY.csv',sums)
 # Epoch and car marginals preserve plan, support rank and numerical status.
 eg=collections.defaultdict(list)
 for p in points:eg[tuple(p[k] for k in ['condition','model','scope','kind','rho','epoch','car'])].append(p)
 er=[]
 for key,pp in eg.items():
  z={k:pp[0][k] for k in ['condition','geometry','sigma','offset_m','model','scope','kind','rho','epoch','car','rank']};av=[p for p in pp if p['reason']=='AVAILABLE'];hit=sum(p['covered']=='True' for p in av);z.update(planned=len(pp),available=len(av),unavailable=len(pp)-len(av),covered=hit,coverage_available=hit/len(av) if av else None,coverage_planned=hit/len(pp),radius_mean=np.mean([float(p['radius']) for p in av]) if av else None);er.append(z)
 table(out/'EPOCH_SUMMARY.csv',er)
 failures=collections.Counter((r['batch'],r['category']) for r in rs);table(out/'FAILURES.csv',[dict(batch=b,category=c,count=n,planned=1200 if b=='PR119' else 600) for (b,c),n in failures.items()])
 save(out/'COUNTS.json',dict(decomposition_endpoints=len(rs),decomposition_seed_rows=len(seedrows),region_rows=len(points),region_seed_rows=len(per),region_summary_rows=len(sums),optimizer_calls=0));print('summary complete')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();protect();main(a.input,a.out)
