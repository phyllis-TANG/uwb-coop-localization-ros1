"""Per-car, paired-run metrics from saved outputs; no optimizer imports."""
import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import statistics
import numpy as np
from scipy.stats import t as student_t, spearmanr
from support import CARS, METHODS, dump, lines, new_output, protocol, sha, write_lines


def ant(p, model):
    lx, ly = model['base_to_antenna_body_xy_m']
    return np.array([p[0]+math.cos(p[2])*lx-math.sin(p[2])*ly,
                     p[1]+math.sin(p[2])*lx+math.cos(p[2])*ly])


def longest(values):
    best = current = 0
    for value in values:
        current = current+1 if value else 0
        best = max(best, current)
    return best


def interval(values):
    values = [float(v) for v in values if v is not None and math.isfinite(v)]
    n = len(values)
    if not n:
        return dict(n=0,mean=None,lo95=None,hi95=None,minimum=None,maximum=None)
    mean = statistics.mean(values)
    half = float(student_t.ppf(.975,n-1))*statistics.stdev(values)/math.sqrt(n) if n>=2 else None
    return dict(n=n,mean=mean,lo95=None if half is None else mean-half,hi95=None if half is None else mean+half,
                minimum=min(values),maximum=max(values))


def csvwrite(path, rows):
    rows = list(rows)
    if not rows:
        raise ValueError('Empty table')
    with path.open('x',newline='') as f:
        writer = csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)


def reduced(row):
    return {k:row[k] for k in ('state_time_s','availability_cutoff_s','availability_cutoff_epoch_ns',
        'availability_prefix_max_record_index','pose','estimate_valid','status','accepted_graph','bins','monitor','prior','snapshot')
        if k in row and k!='snapshot'} | dict(active_times=row['snapshot']['times_s'])


def load_case(root, tag):
    inp = root/'inputs'/tag
    manifest = json.loads((inp/'manifest.json').read_text())
    for name,digest in manifest['files'].items():
        if sha(inp/name)!=digest:raise ValueError('Input SHA '+tag+'/'+name)
    cfg=json.loads((inp/'config.json').read_text())
    labels=json.loads((inp/'labels.json').read_text())
    truth={r['time_s']:r for r in lines(inp/'truth.jsonl.gz')}
    rows={}
    for method in METHODS:
        run=root/'runs'/tag/method
        meta=json.loads((run/'run.json').read_text())
        if meta['status']!='DONE' or meta['input_sha256']!=sha(inp/'events.jsonl.gz') or meta['config_sha256']!=sha(inp/'config.json'):
            raise ValueError('Run binding '+tag+'/'+method)
        for name,digest in meta['outputs'].items():
            if sha(run/name)!=digest:raise ValueError('Output SHA '+name)
        sequence=list(lines(run/'updates.jsonl.gz'))
        if len(set(r['state_time_s'] for r in sequence))!=len(sequence):raise ValueError('Duplicate output')
        rows[method]={r['state_time_s']:reduced(r) for r in sequence}
    for method in METHODS[1:]:
        if list(rows[method])!=list(rows['M2']):raise ValueError('Method publication times differ')
        for t,row in rows[method].items():
            if row['bins']!=rows['M2'][t]['bins'] or row['monitor']['B1']['raw_local']!=rows['M2'][t]['monitor']['B1']['raw_local']:
                raise ValueError('Methods consume different bins or raw B1')
    return dict(input=inp,config=cfg,labels=labels,truth=truth,rows=rows,manifest=manifest)


def faults_and_crn(normal, faulty):
    cfg=faulty['config'];labels=faulty['labels'];fault=labels['fault'];car=fault['vehicle_id']
    if cfg!=normal['config'] or faulty['truth']!=normal['truth']:raise ValueError('CRN initial/truth mismatch')
    pairs=zip(lines(normal['input']/'events.jsonl.gz'),lines(faulty['input']/'events.jsonl.gz'),strict=True)
    origin=labels['epoch_ns'];changed=0;support=[]
    for a,b in pairs:
        for key in ('record_index','source_observation_id','kind','vehicle_id','header_epoch_ns','receive_epoch_ns','case_id'):
            if a[key]!=b[key]:raise ValueError('CRN identity/order mismatch '+key)
        stamp=(b['header_epoch_ns']-origin)/1e9
        target=b['kind']=='uwb' and b['vehicle_id']==car and fault['interval_s'][0]<=stamp<fault['interval_s'][1]
        for key,value in a['value'].items():
            expected=value+.30 if target and key in cfg['models'][car]['anchors_xyz_m'] else value
            if b['value'][key]!=expected:raise ValueError('CRN measurement mismatch')
            if expected!=value:changed+=1
        if target:support.append(b)
    if changed!=1120:raise ValueError('Unexpected number of changed scalars')
    polluted=[]
    for t,row in faulty['rows']['M2'].items():
        if any(abs((e['header_epoch_ns']-origin)/1e9-t)<=.4000000001
               and e['receive_epoch_ns']<=row['availability_cutoff_epoch_ns']
               and e['record_index']<=row['availability_prefix_max_record_index'] for e in support):
            if not row['bins'][car]['observations']:raise ValueError('No actual affected wall factor')
            polluted.append(t)
    if not polluted:raise ValueError('No fault support reached factors')
    exits={}
    for method,rows in faulty['rows'].items():
        exits[method]=next((t for t,r in rows.items() if t>max(polluted) and not set(r['active_times']).intersection(polluted)),None)
        if exits[method] is None or labels['duration_s']-exits[method]<20:
            raise ValueError('Insufficient actual post-factor-exit observation')
    return dict(changed_wall_scalars=changed,first_polluted_bin=min(polluted),last_polluted_bin=max(polluted),
                polluted_bins=polluted,first_no_polluted_active_factor_state_s=exits,
                physical_fault_end_s=fault['interval_s'][1],prior_history_cleared=False)


def error(row, car, ci, target, cfg):
    if row is None or row['pose'] is None or not all(math.isfinite(v) for v in row['pose']):return None
    return ant(row['pose'][4*ci:4*ci+4],cfg['models'][car])-np.array(target['cars'][car]['antenna_xyz_m'][:2])


def summarize_frames(frames, start, end, epsilon):
    rows=[r for r in frames if start<=r['time_s']<end]
    finite=[r for r in rows if r['squared_error_m2'] is not None]
    valid=[r for r in rows if r['valid']]
    paired=[r for r in rows if r['paired_valid']]
    delta=[r['delta_squared_error_vs_M2_m2'] for r in paired]
    harmonic=[r['paired_valid'] and r['delta_squared_error_vs_M2_m2']>epsilon for r in rows]
    mse=lambda rs:statistics.mean([r['squared_error_m2'] for r in rs]) if rs else None
    raw=[r['four_wall_statistic'] for r in paired if r['four_wall_statistic'] is not None]
    correlation=None
    if len(raw)==len(delta) and len(raw)>=3 and np.ptp(raw)>1e-12 and np.ptp(delta)>epsilon:
        correlation=float(spearmanr(raw,delta).statistic)
    return dict(window_s=end-start,finite_s=len(finite),valid_s=len(valid),paired_valid_s=len(paired),
        coverage_fraction=len(valid)/(end-start),paired_coverage_fraction=len(paired)/(end-start),
        unknown_or_invalid_s=sum(not r['valid'] for r in rows),no_publication_s=sum(not r['published'] for r in rows),
        failed_s=sum(r['failed'] for r in rows),mse_all_finite_m2=mse(finite),mse_valid_m2=mse(valid),
        rmse_all_finite_m=None if not finite else math.sqrt(mse(finite)),rmse_valid_m=None if not valid else math.sqrt(mse(valid)),
        delta_mse_vs_M2_m2=statistics.mean(delta) if delta else None,
        harm_duration_s=sum(harmonic),longest_harm_duration_s=longest(harmonic),
        four_wall_raw_mean=None if not raw else statistics.mean(raw),
        raw_stat_delta_SE_spearman_descriptive=correlation,
        unchanged_local_stat_but_changed_error_s=sum(r['unchanged_stat_error_changed'] for r in rows),
        unchanged_local_stat_but_worse_error_s=sum(r['unchanged_stat_error_worse'] for r in rows),
        posterior_wall_rms_mean_m=statistics.mean([r['posterior_wall_rms_m'] for r in finite]) if finite else None)


def recovery(frames, start, end, threshold, dwell, exit_time):
    by_t={r['time_s']:r for r in frames}
    def inside(t):
        r=by_t[t]
        return r['paired_nominal_valid'] and r['paired_nominal_displacement_m']<=threshold
    def first(after):
        return next((t for t in range(int(after),int(end)-dwell+1) if all(inside(k) for k in range(t,t+dwell))),None)
    first_start=first(start);after_exit=first(exit_time)
    last=by_t[end-1]
    result=dict(physical_fault_end_s=start,last_polluted_active_factor_exit_s=exit_time,
        first_recovery_start_s=first_start,first_recovery_confirm_state_s=None if first_start is None else first_start+dwell-1,
        first_recovery_confirm_receipt_cutoff_s=None if first_start is None else by_t[first_start+dwell-1]['availability_cutoff_s'],
        first_recovery_after_factor_exit_start_s=after_exit,right_censored=first_start is None,
        reexcursion_or_invalid_s=None if first_start is None else sum(not inside(t) for t in range(first_start+dwell,int(end))),
        terminal_paired_nominal_displacement_m=last['paired_nominal_displacement_m'],
        terminal_paired_nominal_valid=last['paired_nominal_valid'],threshold_m=threshold,dwell_s=dwell,
        final_prior_cross_information_norm=last['prior_cross_information_norm'],
        final_prior_affine_norm=last['prior_affine_norm'])
    return result


def evaluate(matrix_path, protocol_path, output):
    root=Path(matrix_path);p=protocol(protocol_path);out=new_output(output)
    index=json.loads((root/'RUN_INDEX.json').read_text())
    if index['status']!='DONE' or index['protocol_sha256']!=sha(protocol_path):raise ValueError('Unbound/incomplete matrix')
    for name,digest in index['files'].items():
        if sha(root/name)!=digest:raise ValueError('Matrix file hash mismatch '+name)
    partition=index['partition'];metrics=[];recoveries=[];support_receipts=[];allframes=[]
    epsilon=p['harm_epsilon_m2']
    for seed in p['partitions'][partition]['seeds']:
        for motion in ('static_moving','both_moving'):
            normal=load_case(root,f'{seed}-{motion}-nominal')
            for condition in p['partitions'][partition]['conditions']:
                case=normal if condition=='nominal' else load_case(root,f'{seed}-{motion}-{condition}')
                cfg,labels=case['config'],case['labels'];horizon=labels['duration_s']
                sup=None if condition=='nominal' else faults_and_crn(normal,case)
                if sup:support_receipts.append(dict(seed=seed,motion=motion,condition=condition,**sup))
                for method in METHODS:
                    for ci,car in enumerate(CARS):
                        frames=[]
                        for t in range(horizon):
                            row=case['rows'][method].get(t);ref=case['rows']['M2'].get(t);nom=normal['rows'][method].get(t)
                            target=case['truth'][t]
                            e=error(row,car,ci,target,cfg);er=error(ref,car,ci,target,cfg);en=error(nom,car,ci,target,cfg)
                            valid=e is not None and row['estimate_valid'][car]
                            paired=valid and er is not None and ref['estimate_valid'][car]
                            nom_valid=valid and en is not None and nom['estimate_valid'][car]
                            statistic=None if row is None else row['monitor']['B1']['raw_local'][car]['statistic']
                            unchanged=False if row is None or nom is None else row['monitor']['B1']['raw_local'][car]==nom['monitor']['B1']['raw_local'][car]
                            nerr=None if not nom_valid else float(e@e-en@en)
                            posterior=None
                            if e is not None:
                                xy=ant(row['pose'][4*ci:4*ci+4],cfg['models'][car]);m=cfg['models'][car]
                                residuals=[math.dist([*xy,m['antenna_height_m']],m['anchors_xyz_m'][k])-(z-m['range_bias_m'][k]) for k,z in row['bins'][car]['observations'].items()]
                                posterior=math.sqrt(statistics.mean([v*v for v in residuals])) if residuals else None
                            prior=None if row is None else np.array(row['prior']['matrix'])
                            f=dict(partition=partition,seed=seed,motion=motion,condition=condition,method=method,car=car,time_s=t,
                                published=row is not None,valid=bool(valid),paired_valid=bool(paired),
                                failed=row is not None and ('failed' in row['status'] or 'error' in row['status']),
                                status='no_publication' if row is None else row['status'],
                                availability_cutoff_s=None if row is None else row['availability_cutoff_s'],
                                squared_error_m2=None if e is None else float(e@e),
                                delta_squared_error_vs_M2_m2=None if e is None or er is None else float(e@e-er@er),
                                four_wall_statistic=statistic,posterior_wall_rms_m=posterior,
                                paired_nominal_valid=bool(nom_valid),paired_nominal_displacement_m=None if e is None or en is None else float(np.linalg.norm(e-en)),
                                paired_nominal_delta_squared_error_m2=nerr,raw_stat_unchanged_from_nominal=unchanged,
                                unchanged_stat_error_changed=bool(nom_valid and unchanged and abs(nerr)>epsilon),
                                unchanged_stat_error_worse=bool(nom_valid and unchanged and nerr>epsilon),
                                prior_cross_information_norm=None if prior is None else float(np.linalg.norm((prior.T@prior)[:4,4:])),
                                prior_affine_norm=None if row is None else float(np.linalg.norm(row['prior']['offset'])),
                                sim_four_wall_declaration='unknown',sim_source_exclusion_declaration='unknown')
                            frames.append(f)
                        phases=dict(p['phase_windows'])
                        if sup:
                            ex=sup['first_no_polluted_active_factor_state_s'][method]
                            phases.update(recovery_pre_exit=[38,ex],recovery_post_exit=[ex,horizon])
                            recoveries.append(dict(partition=partition,seed=seed,motion=motion,condition=condition,method=method,car=car,
                                **recovery(frames,38,horizon,p['recovery']['paired_nominal_displacement_m'],p['recovery']['consecutive_valid_hold_s'],ex)))
                        for phase,(a,b) in phases.items():
                            metrics.append(dict(partition=partition,seed=seed,motion=motion,condition=condition,method=method,car=car,phase=phase,
                                **summarize_frames(frames,a,b,epsilon)))
                        allframes.extend(frames)
    csvwrite(out/'PER_SEED.csv',metrics)
    if recoveries:csvwrite(out/'RECOVERY_PER_SEED.csv',recoveries)
    write_lines(out/'FRAMES.jsonl.gz',allframes)
    dump(out/'FACTOR_SUPPORT.json',support_receipts)
    grouped=[]
    keys=('motion','condition','method','car','phase')
    for values in sorted({tuple(r[k] for k in keys) for r in metrics}):
        group=[r for r in metrics if tuple(r[k] for k in keys)==values]
        for metric in ('rmse_all_finite_m','rmse_valid_m','delta_mse_vs_M2_m2','harm_duration_s','longest_harm_duration_s',
                       'coverage_fraction','paired_coverage_fraction','failed_s','unknown_or_invalid_s',
                       'unchanged_local_stat_but_changed_error_s','unchanged_local_stat_but_worse_error_s'):
            grouped.append(dict(partition=partition,**dict(zip(keys,values)),metric=metric,**interval([r[metric] for r in group])))
    csvwrite(out/'RUN_LEVEL_INTERVALS.csv',grouped)
    # M2 partner invariance is numerical, not an asynchronous failure contract.
    controls=[]
    for seed in p['partitions'][partition]['seeds']:
        for motion in ('static_moving','both_moving'):
            for condition in p['partitions'][partition]['conditions']:
                if condition=='nominal':continue
                partner='car2' if condition.startswith('car1') else 'car1'
                fs=[r for r in allframes if r['seed']==seed and r['motion']==motion and r['condition']==condition and r['car']==partner]
                m2=[r for r in fs if r['method']=='M2' and r['paired_nominal_valid']]
                maximum=max(r['paired_nominal_displacement_m'] for r in m2)
                if not all(r['raw_stat_unchanged_from_nominal'] for r in fs if r['published']):raise ValueError('Unchanged partner raw B1 differs')
                controls.append(dict(seed=seed,motion=motion,condition=condition,partner=partner,M2_max_displacement_m=maximum,
                    successful_publication_invariance='PASS' if maximum<=1e-8 else 'EXCEEDS_TOLERANCE_REVIEW_FAILURE_TRANSACTIONS'))
    dump(out/'ANALYSIS_CHECKS.json',dict(status='PASS',partition=partition,cells=len(index['cells']),
        paired_input_CRN='all changed scalars exactly frozen wall fault; peer/Odom/gyro unchanged',
        exact_shared_method_bins=True,lossless_readback='separate per-cell READBACK receipts',M2_partner_controls=controls,
        no_alarm_threshold_fitted=True,sim_source_exclusion='unknown',frame_correlations='descriptive only; no independent frame trials'))
    dump(out/'ANALYSIS_INDEX.json',dict(status='DONE',partition=partition,protocol_sha256=sha(protocol_path),
        source_matrix_index_sha256=sha(root/'RUN_INDEX.json'),per_seed_rows=len(metrics),frame_rows=len(allframes),
        files={q.name:sha(q) for q in out.iterdir()}))
    return metrics


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--matrix',required=True,type=Path);p.add_argument('--protocol',required=True,type=Path);p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();rows=evaluate(a.matrix,a.protocol,a.output)
    print(json.dumps(dict(status='DONE',per_seed_rows=len(rows))))
