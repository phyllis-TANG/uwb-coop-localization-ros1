"""Independent published CSV/truth interaction calculation, no estimator import."""
import argparse
import csv
import json
import math
from pathlib import Path
from scipy.stats import t as student_t
from local_support import CARS,EPOCH,dump,lines,protocol,sha

def csvread(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def close(x,y,key):
    if x is None or y is None:
        if x!=y:raise ValueError(key)
    elif abs(float(x)-float(y))>1e-11*max(1.,abs(float(y))):raise ValueError(key+str((x,y)))
def number(x):return None if x in ('',None) else float(x)

def read(root,analysis):
    root=Path(root);analysis=Path(analysis);p=protocol();idx=json.loads((root/'RUN_INDEX.json').read_text());data={}
    ai=json.loads((analysis/'ANALYSIS_INDEX.json').read_text())
    for name,h in ai['files'].items():
        if sha(analysis/name)!=h:raise ValueError('Analysis SHA')
    count=0
    for cell in idx['cells']:
        cfg=json.loads((root/cell['input']/'config.json').read_text());truth={r['time_s']:r for r in lines(root/cell['input']/'truth.jsonl.gz')}
        key=(cell['seed'],cell['geometry'],cell['processing'],cell['method']);rows={c:{} for c in CARS}
        jr={(r['state_epoch_ns']-EPOCH)//10**9:r for r in lines(root/cell['run']/'updates.jsonl.gz')}
        for r in csvread(root/cell['run']/'published.csv'):
            t=(int(r['state_epoch_ns'])-EPOCH)//10**9;car=r['vehicle_id'];ci=CARS.index(car);valid=r['accepted_graph']=='True' and r['valid']=='True'
            if valid!=(jr[t]['accepted_graph'] and jr[t]['estimate_valid'][car]):raise ValueError('CSV accepted mask')
            if r['finite_output']!='True':rows[car][t]=(valid,None);continue
            x,y,a=(float(r[k]) for k in ('base_x_m','base_y_m','yaw_rad'));lx,ly=cfg['models'][car]['base_to_antenna_body_xy_m']
            xy=[x+math.cos(a)*lx-math.sin(a)*ly,y+math.sin(a)*lx+math.cos(a)*ly]
            close(xy[0],float(r['antenna_x_m']),'CSV antenna');close(xy[1],float(r['antenna_y_m']),'CSV antenna')
            for v,w in zip([x,y,a],jr[t]['pose'][4*ci:4*ci+3]):close(v,w,'CSV journal')
            ref=truth[t]['cars'][car]['antenna_xyz_m'];sq=(xy[0]-ref[0])**2+(xy[1]-ref[1])**2
            rows[car][t]=(valid,sq);count+=1
        data[key]=rows
    report=csvread(analysis/'PER_CONFIGURATION.csv');contrasts=csvread(analysis/'PER_SEED_INTERACTIONS.csv');masks=json.loads((analysis/'COMMON_MASKS.json').read_text());checked=0;Ts={}
    for seed in p['seeds']:
        for car in CARS:
            keys=[k for k in data if k[0]==seed]
            common=sorted(set.intersection(*[{t for t,(valid,e) in data[k][car].items() if 6<=t<=95 and valid and e is not None} for k in keys]))
            original=next(x for x in masks if x['seed']==seed and x['car']==car)
            if common!=original['times_s']:raise ValueError('All12 common mask')
            ms={}
            for k in keys:
                ms[k[1:]]=sum(data[k][car][t][1] for t in common)/len(common) if common else None
                r=next(x for x in report if (int(x['seed']),x['geometry'],x['processing'],x['method'],x['car'])==(*k,car))
                close(number(r['MSE_common_m2']),ms[k[1:]],'common MSE');checked+=1
                full=[v[1] for t,v in data[k][car].items() if 6<=t<=95 and v[1] is not None]
                close(number(r['MSE_all_finite_m2']),sum(full)/len(full),'full MSE');checked+=1
            for method in ('M3','M3W025'):
                r=next(x for x in contrasts if int(x['seed'])==seed and x['car']==car and x['method']==method)
                values={}
                for g in ('G1','G2'):
                    for proc in ('raw','historical'):
                        values[f'D_{g}_{proc}']=ms[(g,proc,method)]-ms[(g,proc,'M2')] if common else None
                    values['C_'+g]=values[f'D_{g}_historical']-values[f'D_{g}_raw'] if common else None
                    values['correction_M2_'+g]=ms[(g,'historical','M2')]-ms[(g,'raw','M2')] if common else None
                    values['correction_method_'+g]=ms[(g,'historical',method)]-ms[(g,'raw',method)] if common else None
                val=values['C_G2']-values['C_G1'] if common and len(common)>=72 else None
                values['T_m2']=val
                for k,v in values.items():close(number(r[k]),v,'contrast '+k);checked+=1
                if val is not None:Ts.setdefault((car,method),[]).append(val)
    summaries=json.loads((analysis/'INTERACTION_SUMMARY.json').read_text());passed={}
    for s in summaries:
        vals=Ts.get((s['car'],s['method']),[])
        if len(vals)!=4:
            if s['pass_primary']:raise ValueError('Missing seed accepted')
            continue
        mu=sum(vals)/4;sd=math.sqrt(sum((x-mu)**2 for x in vals)/3);radius=float(student_t.ppf(.975,3))*sd/2
        for k,v in dict(mean=mu,minimum=min(vals),maximum=max(vals),lo95=mu-radius,hi95=mu+radius).items():close(s[k],v,k);checked+=1
        ok=(all(x>0 for x in vals) or all(x<0 for x in vals)) and (mu-radius>0 or mu+radius<0) and abs(mu)>=.001
        if bool(s['pass_primary'])!=ok:raise ValueError('Prespecified threshold decision')
        if s['method']=='M3':passed[s['car']]=(ok,mu)
    d=json.loads((analysis/'DECISION.json').read_text())
    if d['placement_alone_support']!=any(v[0] for v in passed.values()):raise ValueError('Global primary decision')
    direction=len(passed)==2 and passed['car1'][0] and passed['car2'][0] and passed['car1'][1]>0 and passed['car2'][1]<0
    if d['field_direction_support']!=direction:raise ValueError('Directional decision')
    return dict(status='PASS',vehicle_CSV_publications=count,independent_scalar_checks=checked,common_masks=8,optimizer_or_analyzer_imported=False)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',required=True,type=Path);p.add_argument('--analysis',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError('No overwrite')
    r=read(a.matrix,a.analysis);dump(a.output,r);print(json.dumps(r))
