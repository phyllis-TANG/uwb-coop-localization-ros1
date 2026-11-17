"""Paired scale contrasts and conditional selected-group diagnostics, all seed clustered."""
from common import *
from model import CFG
from summarize import interval,mean,THRESHOLDS
import argparse

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False);d=cached_npz(a.input/'POINTS.npz');rows=list(csv.DictReader((a.input/'ENDPOINT_METRICS.csv').open()));selections=read(a.input/'SELECTION.json');weak={int(z['index']):z for z in csv.DictReader((a.input/'WEAK_CURVATURE.csv').open())};seedrows=[];groupcounts=[]
    for s in selections:
        first=rows[s['original_index']];base=dict(id=s['id'],geometry=first['geometry'],perturbation_m=float(first['perturbation_m']),method=s['method'],seed=s['seed']);selected=s['selected_index'];group=s['selected_group_indices']
        for car in range(2):
            keys=np.arange(car,12,2);r=dict(**base,car=car+1,multiple_groups=float(s['accepted_groups']>1),group_diagnosable=float(s['accepted_candidates']>=2),accepted_fraction=s['accepted_candidates']/5,selected_available=float(selected is not None),weak_relative_norm=None if selected is None else float(weak[selected]['weak_relative_norm']),overall_relative_norm=None if selected is None else float(weak[selected]['overall_relative_frobenius']))
            for mode,ii in [('original',[s['original_index']]),('selected',[] if selected is None else [selected]),('selected_group',group),('all_finite',[s['original_index']+i for i in range(5) if rows[s['original_index']+i]['cost']!='']),('all_accepted',[s['original_index']+i for i in range(5) if rows[s['original_index']+i]['accepted']=='True'])]:
                r[mode+'_rmse']=mean([np.sqrt(np.mean(np.sum(d['error'][i,keys]**2,axis=1))) for i in ii]);r[mode+'_area95']=mean([np.mean(d['area95'][i,0,keys]) for i in ii]);r[mode+'_sqrt_trace']=mean([np.mean(np.sqrt(d['trace'][i,0,keys])) for i in ii])
                for level in [.95,.99]:
                    tag=str(int(level*100));q=d['q'][ii,0][:,keys] if ii else np.full((1,6),np.nan);available=np.isfinite(q);hit=available&(q<=THRESHOLDS[level]);r[mode+'_point'+tag]=float(np.mean(hit));r[mode+'_available'+tag]=float(np.mean(available));r[mode+'_trajectory'+tag]=float(np.mean(hit.all(axis=1)));r[mode+'_valid_point'+tag]=float(hit.sum()/available.sum()) if available.any() else None
                    if True:groupcounts.append(dict(**base,mode=mode,car=car+1,level=level,members=len(ii),available_point_fraction=r[mode+'_available'+tag],covered_point_fraction=r[mode+'_point'+tag],all_epoch_available_fraction=float(np.mean(available.all(axis=1))),all_epoch_covered_fraction=r[mode+'_trajectory'+tag]))
            seedrows.append(r)
    csvsave(out/'SEED_METRICS.csv',seedrows);csvsave(out/'GROUP_SEEDS.csv',groupcounts);contrasts=[];weaksumm=[]
    lookup={(z['geometry'],z['method'],z['perturbation_m'],z['seed'],z['car']):z for z in seedrows}
    metrics=['multiple_groups','group_diagnosable','accepted_fraction','selected_available','selected_group_point95','selected_group_available95','selected_group_valid_point95','selected_group_point99','selected_group_trajectory95','selected_group_trajectory99','original_point95','selected_point95','selected_rmse','original_rmse','selected_sqrt_trace','selected_area95','selected_group_rmse','selected_group_sqrt_trace','selected_group_area95','all_finite_point95','all_accepted_point95','weak_relative_norm','overall_relative_norm']
    for g in CFG['geometries']:
      for m in CFG['methods']:
       for car in [1,2]:
        for scale in [.1,.5]:
         for metric in metrics:
            delta=[]
            for seed in CFG['seeds']:
                x=lookup[g,m,scale,seed,car][metric];y=lookup[g,m,0.,seed,car][metric];delta.append(np.nan if x is None or y is None else x-y)
            lo,hi,status=interval(delta,40);contrasts.append(dict(geometry=g,method=m,car=car,contrast=f'{scale}-minus-0',metric=metric,planned_seeds=40,paired_valid=int(np.isfinite(delta).sum()),difference=mean(delta),ci_low=lo,ci_high=hi,ci_status=status,primary=g=='weak' and m=='B2' and scale==.5 and metric in ['multiple_groups','selected_group_point95']))
        for scale in CFG['perturbations_m']:
            subset=[lookup[g,m,scale,seed,car] for seed in CFG['seeds']]
            for metric in ['weak_relative_norm','overall_relative_norm']:
                vals=[np.nan if z[metric] is None else z[metric] for z in subset];lo,hi,status=interval(vals,40);weaksumm.append(dict(geometry=g,method=m,car=car,perturbation_m=scale,metric=metric,planned_seeds=40,available=int(np.isfinite(vals).sum()),mean=mean(vals),ci_low=lo,ci_high=hi,ci_status=status))
    csvsave(out/'GEOMETRY_CONTRASTS.csv',contrasts);csvsave(out/'WEAK_SUMMARY.csv',weaksumm)
if __name__=='__main__':main()
