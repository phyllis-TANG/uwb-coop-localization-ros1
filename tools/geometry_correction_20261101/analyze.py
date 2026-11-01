"""Fixed factorial interaction, all12-configuration common accepted mask."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics
import numpy as np
from scipy.stats import t as student_t
from local_support import CARS,EPOCH,METHODS,dump,gitstate,lines,new,protocol,sha,sources,write

def table(path,rows):
    with path.open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def interval(vals):
    n=len(vals)
    if n!=4:return dict(n=n,mean=None,minimum=None,maximum=None,lo95=None,hi95=None,pass_primary=False,same_sign=False,reason='not_all_four_seeds_evaluable')
    mean=statistics.mean(vals);half=float(student_t.ppf(.975,3))*statistics.stdev(vals)/2
    same=all(x>0 for x in vals) or all(x<0 for x in vals)
    nonzero=mean-half>0 or mean+half<0
    passed=same and nonzero and abs(mean)>=.001
    return dict(n=4,mean=mean,minimum=min(vals),maximum=max(vals),lo95=mean-half,hi95=mean+half,pass_primary=passed,same_sign=same,CI_excludes_zero=nonzero,absolute_mean_at_least_0_001=abs(mean)>=.001)

def evaluate(root,output):
    root=Path(root);out=new(output);p=protocol();idx=json.loads((root/'RUN_INDEX.json').read_text())
    if idx['status']!='DONE' or len(idx['cells'])!=48:raise ValueError('Incomplete48-cell experiment')
    for name,h in idx['files'].items():
        if sha(root/name)!=h:raise ValueError('Changed evidence '+name)
    per_config=[];contrasts=[];masks=[];failures=[];full_frames=[]
    for seed in p['seeds']:
        data={};truth={}
        for cell in [x for x in idx['cells'] if x['seed']==seed]:
            key=(cell['geometry'],cell['processing'],cell['method']);inp=root/cell['input'];cfg=json.loads((inp/'config.json').read_text())
            refs={x['time_s']:x for x in lines(inp/'truth.jsonl.gz')};truth[cell['geometry']]=refs
            meta=json.loads((root/cell['run']/'run.json').read_text())
            if meta['status']!='DONE' or meta['input_sha256']!=sha(inp/'events.jsonl.gz'):raise ValueError('Run binding')
            rows={}
            for r in lines(root/cell['run']/'updates.jsonl.gz'):
                ns=r['state_epoch_ns']-EPOCH
                if ns%10**9:raise ValueError('Noninteger state time')
                time=ns//10**9
                for ci,car in enumerate(CARS):
                    pose=None if r['pose'] is None else r['pose'][4*ci:4*ci+4];error=None
                    if pose is not None:
                        lx,ly=cfg['models'][car]['base_to_antenna_body_xy_m'];a=pose[2]
                        xy=[pose[0]+math.cos(a)*lx-math.sin(a)*ly,pose[1]+math.sin(a)*lx+math.cos(a)*ly]
                        error=math.dist(xy,refs[time]['cars'][car]['antenna_xyz_m'][:2])**2
                    row=dict(seed=seed,geometry=key[0],processing=key[1],method=key[2],car=car,time_s=time,
                        accepted=bool(r['accepted_graph']),valid=bool(r['estimate_valid'][car]),squared_error_m2=error,status=r['status'],
                        failed='failed' in r['status'] or 'error' in r['status'])
                    rows.setdefault(car,{})[time]=row;full_frames.append(row)
                if 'failed' in r['status'] or 'error' in r['status']:failures.append(dict(seed=seed,geometry=key[0],processing=key[1],method=key[2],time_s=time,status=r['status'],optimizer=r['optimizer']))
            data[key]=rows
        for car in CARS:
            common=[t for t in range(6,96) if all(t in d[car] and d[car][t]['accepted'] and d[car][t]['valid'] and d[car][t]['squared_error_m2'] is not None for d in data.values())]
            assessable=len(common)>=72
            masks.append(dict(seed=seed,car=car,scheduled=90,common_count=len(common),common_coverage=len(common)/90,evaluable=assessable,times_s=common))
            mse={}
            for key,d in data.items():
                seq=[d[car].get(t) for t in range(6,96)];finite=[r['squared_error_m2'] for r in seq if r is not None and r['squared_error_m2'] is not None]
                mse[key]=statistics.mean([d[car][t]['squared_error_m2'] for t in common]) if common else None
                per_config.append(dict(seed=seed,car=car,geometry=key[0],processing=key[1],method=key[2],common_count=len(common),primary_evaluable=assessable,
                    MSE_common_m2=mse[key],MSE_all_finite_m2=statistics.mean(finite) if finite else None,finite_count=len(finite),
                    accepted_count=sum(r is not None and r['accepted'] and r['valid'] for r in seq),failed_count=sum(r is not None and r['failed'] for r in seq),unknown_or_not_accepted_count=sum(r is None or not(r['accepted'] and r['valid']) for r in seq)))
            for method in METHODS[1:]:
                v={}
                for g in ('G1','G2'):
                    v[f'D_{g}_raw']=mse[(g,'raw',method)]-mse[(g,'raw','M2')] if common else None
                    v[f'D_{g}_historical']=mse[(g,'historical',method)]-mse[(g,'historical','M2')] if common else None
                    v[f'C_{g}']=v[f'D_{g}_historical']-v[f'D_{g}_raw'] if common else None
                    v[f'correction_M2_{g}']=mse[(g,'historical','M2')]-mse[(g,'raw','M2')] if common else None
                    v[f'correction_method_{g}']=mse[(g,'historical',method)]-mse[(g,'raw',method)] if common else None
                value=v['C_G2']-v['C_G1'] if common else None
                if common:
                    reconstructed=(v['correction_method_G2']-v['correction_method_G1'])-(v['correction_M2_G2']-v['correction_M2_G1'])
                    if abs(value-reconstructed)>1e-12:raise ValueError('Interaction decomposition')
                contrasts.append(dict(seed=seed,car=car,method=method,common_count=len(common),primary_evaluable=assessable,
                    **v,T_m2=value if assessable else None,descriptive_T_low_coverage_m2=value if not assessable else None,
                    interaction_correction_M2_m2=v['correction_M2_G2']-v['correction_M2_G1'] if common else None,
                    interaction_correction_method_m2=v['correction_method_G2']-v['correction_method_G1'] if common else None))
    summary=[]
    for car in CARS:
        for method in METHODS[1:]:
            vals=[x['T_m2'] for x in contrasts if x['car']==car and x['method']==method and x['T_m2'] is not None]
            summary.append(dict(car=car,method=method,**interval(vals),primary_eligible=method=='M3'))
    primary={x['car']:x for x in summary if x['method']=='M3'}
    decision=dict(placement_alone_support=any(x['pass_primary'] for x in primary.values()),
        field_direction_support=all(x['pass_primary'] for x in primary.values()) and primary['car1']['mean']>0 and primary['car2']['mean']<0,
        primary_method='M3',rule=p['decision'],no_rerun_or_tuning=True,public_upload_authorized=False)
    table(out/'PER_CONFIGURATION.csv',per_config);table(out/'PER_SEED_INTERACTIONS.csv',contrasts)
    dump(out/'COMMON_MASKS.json',masks);dump(out/'INTERACTION_SUMMARY.json',summary);dump(out/'DECISION.json',decision);dump(out/'FAILURES.json',failures)
    write(out/'ALL_FINITE_AND_UNKNOWN.jsonl.gz',full_frames)
    dump(out/'ANALYSIS_INDEX.json',dict(status='DONE',**gitstate(),source_sha256=sources(),protocol_sha256=idx['protocol_sha256'],matrix_index_sha256=sha(root/'RUN_INDEX.json'),files={q.name:sha(q) for q in out.iterdir()}))
    return decision

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(json.dumps(evaluate(a.matrix,a.output)))
