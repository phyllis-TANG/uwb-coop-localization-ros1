"""Independent CSV/truth scalar metric and recovery readback; no analyzer imports."""
import argparse
import csv
import json
import math
from pathlib import Path
from scipy.stats import t as student_t
from support import CARS, METHODS, dump, lines, protocol, sha


def csvrows(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))


def num(value):return None if value in ('',None) else float(value)
def yes(value):return str(value).lower()=='true'


def close(actual, expected, message):
    actual=num(actual)
    if (actual is None)!=(expected is None) or (actual is not None and abs(actual-expected)>1e-11*max(1.,abs(expected))):
        raise ValueError(message+': '+str((actual,expected)))


def longest(flags):
    count=best=0
    for flag in flags:
        count=count+1 if flag else 0
        best=max(best,count)
    return best


def read(matrix, analysis, protocol_path):
    root,out=Path(matrix),Path(analysis);p=protocol(protocol_path)
    index=json.loads((root/'RUN_INDEX.json').read_text());ai=json.loads((out/'ANALYSIS_INDEX.json').read_text())
    if ai['source_matrix_index_sha256']!=sha(root/'RUN_INDEX.json') or ai['protocol_sha256']!=sha(protocol_path):raise ValueError('Metric binding')
    for name,digest in ai['files'].items():
        if sha(out/name)!=digest:raise ValueError('Analysis hash '+name)
    support={(x['seed'],x['motion'],x['condition']):x for x in json.loads((out/'FACTOR_SUPPORT.json').read_text())}
    cache={};n_csv=n_identity=0
    for cell in index['cells']:
        key=(cell['seed'],cell['motion'],cell['condition'],cell['method'])
        inp=root/cell['input'];run=root/cell['run'];cfg=json.loads((run/'config.json').read_text())
        truth={r['time_s']:r for r in lines(inp/'truth.jsonl.gz')}
        journal={r['state_time_s']:r for r in lines(run/'updates.jsonl.gz')}
        data={car:{} for car in CARS}
        for r in csvrows(run/'published.csv'):
            car=r['vehicle_id'];t=float(r['state_time_s']);ci=CARS.index(car);jr=journal[t]
            pose=jr['pose']
            valid=yes(r['valid'])
            if valid!=jr['estimate_valid'][car]:raise ValueError('CSV validity differs')
            if pose is None:
                data[car][t]=dict(valid=False,error=None,xy=None,status=r['status'])
                continue
            x,y,yaw=(float(r[k]) for k in ('base_x_m','base_y_m','yaw_rad'))
            for a,b in zip((x,y,yaw),pose[4*ci:4*ci+3]):close(a,b,'CSV/journal pose')
            lx,ly=cfg['models'][car]['base_to_antenna_body_xy_m']
            xy=(x+math.cos(yaw)*lx-math.sin(yaw)*ly,y+math.sin(yaw)*lx+math.cos(yaw)*ly)
            close(r['antenna_x_m'],xy[0],'antenna CSV x');close(r['antenna_y_m'],xy[1],'antenna CSV y')
            target=truth[t]['cars'][car]['antenna_xyz_m']
            err=(xy[0]-target[0],xy[1]-target[1]);sq=err[0]**2+err[1]**2
            data[car][t]=dict(valid=valid,error=sq,xy=xy,vector=err,status=r['status'])
            n_csv+=1
        cache[key]=data
    per=csvrows(out/'PER_SEED.csv')
    checked=0
    for r in per:
        seed=int(r['seed']);key=(seed,r['motion'],r['condition'],r['method']);car=r['car']
        data=cache[key][car];ref=cache[(*key[:3],'M2')][car]
        if r['phase'].startswith('recovery_'):
            exit=support[key[:3]]['first_no_polluted_active_factor_state_s'][key[3]]
            start,end=(38,exit) if r['phase']=='recovery_pre_exit' else (exit,96)
        else:start,end=p['phase_windows'][r['phase']]
        stamps=list(range(int(start),int(end)))
        finite=[data[t]['error'] for t in stamps if t in data and data[t]['error'] is not None]
        valid=[data[t]['error'] for t in stamps if t in data and data[t]['valid']]
        paired=[t for t in stamps if t in data and t in ref and data[t]['valid'] and ref[t]['valid']]
        delta=[data[t]['error']-ref[t]['error'] for t in paired]
        for t,d in zip(paired,delta):
            e=ref[t]['vector'];v=(data[t]['xy'][0]-ref[t]['xy'][0],data[t]['xy'][1]-ref[t]['xy'][1])
            close(d,2*(e[0]*v[0]+e[1]*v[1])+v[0]**2+v[1]**2,'paired square identity');n_identity+=1
        flags=[t in paired and data[t]['error']-ref[t]['error']>p['harm_epsilon_m2'] for t in stamps]
        expected=dict(window_s=end-start,finite_s=len(finite),valid_s=len(valid),paired_valid_s=len(paired),
            coverage_fraction=len(valid)/(end-start),paired_coverage_fraction=len(paired)/(end-start),
            no_publication_s=sum(t not in data for t in stamps),unknown_or_invalid_s=sum(t not in data or not data[t]['valid'] for t in stamps),
            failed_s=sum(t in data and ('failed' in data[t]['status'] or 'error' in data[t]['status']) for t in stamps),
            mse_all_finite_m2=sum(finite)/len(finite) if finite else None,mse_valid_m2=sum(valid)/len(valid) if valid else None,
            rmse_all_finite_m=math.sqrt(sum(finite)/len(finite)) if finite else None,
            rmse_valid_m=math.sqrt(sum(valid)/len(valid)) if valid else None,
            delta_mse_vs_M2_m2=sum(delta)/len(delta) if delta else None,harm_duration_s=sum(flags),longest_harm_duration_s=longest(flags))
        for metric,value in expected.items():close(r[metric],value,'metric '+metric);checked+=1
    intervals=csvrows(out/'RUN_LEVEL_INTERVALS.csv');icount=0
    keys=('motion','condition','method','car','phase')
    for r in intervals:
        vals=[num(a[r['metric']]) for a in per if all(a[k]==r[k] for k in keys)]
        vals=[a for a in vals if a is not None];n=len(vals)
        if not vals:continue
        mean=sum(vals)/n
        half=float(student_t.ppf(.975,n-1))*math.sqrt(sum((a-mean)**2 for a in vals)/(n-1)/n) if n>1 else None
        for k,v in dict(n=n,mean=mean,minimum=min(vals),maximum=max(vals),lo95=None if half is None else mean-half,hi95=None if half is None else mean+half).items():
            close(r[k],v,'run-level interval '+k);icount+=1
    rcount=0
    recovery_path=out/'RECOVERY_PER_SEED.csv'
    if recovery_path.exists():
        for r in csvrows(recovery_path):
            key=(int(r['seed']),r['motion'],r['condition'],r['method']);car=r['car']
            data=cache[key][car];nom=cache[(key[0],key[1],'nominal',key[3])][car]
            threshold=p['recovery']['paired_nominal_displacement_m'];dwell=p['recovery']['consecutive_valid_hold_s']
            def ok(t):return t in data and t in nom and data[t]['valid'] and nom[t]['valid'] and math.dist(data[t]['xy'],nom[t]['xy'])<=threshold
            def first(after):return next((t for t in range(int(after),96-dwell+1) if all(ok(k) for k in range(t,t+dwell))),None)
            found=first(38);ex=support[key[:3]]['first_no_polluted_active_factor_state_s'][key[3]]
            expected=dict(first_recovery_start_s=found,first_recovery_confirm_state_s=None if found is None else found+dwell-1,
                first_recovery_confirm_receipt_cutoff_s=None if found is None else found+dwell,
                first_recovery_after_factor_exit_start_s=first(ex),reexcursion_or_invalid_s=None if found is None else sum(not ok(t) for t in range(found+dwell,96)),
                terminal_paired_nominal_displacement_m=math.dist(data[95]['xy'],nom[95]['xy']))
            for metric,value in expected.items():close(r[metric],value,'recovery '+metric);rcount+=1
            if yes(r['right_censored'])!=(found is None):raise ValueError('Recovery censoring')
    return dict(status='PASS',partition=index['partition'],csv_vehicle_publications=n_csv,paired_square_identities=n_identity,
        per_seed_scalar_metrics=checked,run_level_interval_scalars=icount,recovery_scalars=rcount,
        inputs='published.csv + independently reconstructed antenna geometry + separate truth; journal for CSV identity',
        optimizer_or_analyzer_imported=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--matrix',required=True,type=Path);p.add_argument('--analysis',required=True,type=Path);p.add_argument('--protocol',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args()
    if a.output.exists():raise ValueError('Refuse overwrite')
    r=read(a.matrix,a.analysis,a.protocol);dump(a.output,r);print(json.dumps(r))
