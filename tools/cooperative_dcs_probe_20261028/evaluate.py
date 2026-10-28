#!/usr/bin/env python3
"""Artifact-only evaluation: two distinct paired contrasts, independent readback."""
import argparse,csv,gzip,json,math,sys
from collections import Counter
from pathlib import Path
import numpy as np
from common import SCENARIOS,SEEDS,METHODS,sha,dump,read
import independent as ind
PERIODS={'all':lambda t:True,'pre':lambda t:3<=t<24,'fault':lambda t:24<=t<38,'recovery':lambda t:38<=t<48,'late':lambda t:48<=t<=63}
CARS=('car1','car2')
METRICS=('car1_base_xy_m','car1_antenna_xy_m','car1_yaw_rad','car2_base_xy_m','car2_antenna_xy_m','car2_yaw_rad','relative_xy_m','distance_m')

def csv_write(p,rows):
    with Path(p).open('x',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def rms(values):
    values=[x for x in values if x is not None];return float(np.sqrt(np.mean(np.square(values)))) if values else None


def peer_at(pose,measured,c,method,actual):
    if pose is None or measured is None:return dict(residual_m=None,e=None,chi_square=None,s=None,information_weight=None,influence=None,gradient_weight=None)
    distance=np.linalg.norm(ind.audit.ant(pose[:3],c['models']['car1'])-ind.audit.ant(pose[3:],c['models']['car2']))
    e=float((distance-measured)/c['peer']['sigma_m']);t=e*e
    if not actual:s,w,g=0.,0.,0.
    elif method=='D3':w,_=ind.weights(e);w=float(w);s=math.sqrt(w);g=w
    else:
        # Exact original signed pseudo-Huber residual Jacobian curvature.
        h=math.hypot(1,e);w=(h+1)/(2*h*h);s=math.sqrt(w);g=1/h
    return dict(residual_m=e*c['peer']['sigma_m'],e=e,chi_square=t,s=s,information_weight=w,influence=g*e,gradient_weight=g)


def inspect_run(rows,config,events,method):
    checks=Counter();margin=[];streams=ind.audit.input_streams(events);origin=events[0]['receive_epoch_ns'];previous={};consumed={};known={};constants={}
    ind.audit.residuals.peer_sigma=config['peer']['sigma_m']
    assert len(rows)==63 and [r['state_time_s'] for r in rows]==list(range(1,64))
    for row in rows:
        assert row['state_epoch_ns']==origin+round(row['state_time_s']*1e9) and row['availability_cutoff_epoch_ns']-row['state_epoch_ns']==10**9
        ind.audit.check_bins(row,config,streams,origin);checks['bins']+=1
        for role,obj in [('main',row),('auxiliary',row.get('auxiliary'))]:
            if obj is None:continue
            s=obj['snapshot'];assert len(s['times_s'])<=21;seen=consumed.setdefault(role,set());identities=known.setdefault(role,{})
            for md in obj['marginalization_details']:
                if role in previous:assert md['before']==previous[role]
                previous[role]=md['after'];old_epoch=origin+round(md['times_s'][0]*1e9);factor='peer|'+str(old_epoch)
                if s['peer_enabled'] and md['old_peer_m'] is not None:
                    assert factor not in seen;seen.add(factor);assert identities[factor]==md['old_peer_m']
                constants[role]=constants.get(role,0.)+md['constant']
                if method=='D3' and role=='main':margin.append(ind.marginal(md,config));checks['DCS_all_FD_Schur']+=1
                else:ind.audit.marginal_check(md,config,s['peer_enabled']);checks['baseline_all_FD_Schur']+=1
            if role in previous:assert s['prior']==previous[role]
            previous[role]=s['prior'];assert abs(s['eliminated_constant']-constants.get(role,0.))<1e-9
            active=[]
            for t,z in zip(s['times_s'],s['peers_m']):
                if not s['peer_enabled'] or z is None:continue
                factor='peer|'+str(origin+round(t*1e9));active.append(factor)
                if factor in identities:assert identities[factor]==z
                identities[factor]=z
            assert not set(active)&seen
            assert set(obj['provenance']['window_peer_factor_ids'])==set(active) and set(obj['provenance']['prior_peer_factor_ids'])==seen
            checks['prior_chain']+=1
            if obj['accepted_graph']:
                if method=='D3' and role=='main':value=ind.cost(s,np.asarray(s['states']).ravel(),config)
                else:
                    r=ind.audit.residuals(np.asarray(s['states']).ravel(),s['times_s'],s['local'],s['observations'],s['peers_m'],config['models'],s['prior'],s['peer_enabled']);value=float(r@r/2)
                assert abs(value-obj['optimizer']['cost'])<1e-7;checks['full_accepted_objectives']+=1
        if method=='D3':
            previous_cost=None;s=row['snapshot'];times=s['times_s']
            for q in row.get('dcs_linearizations',[]):
                x=np.array(q['states']);v=ind.cost(s,x.ravel(),config);assert abs(v-q['true_cost'])<1e-7
                if previous_cost is not None:assert v<=previous_cost+1e-9
                previous_cost=v;checks['DCS_linearizations']+=1
                expected=[(k,z) for k,z in enumerate(s['peers_m']) if z is not None]
                assert len(expected)==len(q['peers'])
                for (k,z),p in zip(expected,q['peers']):
                    a=peer_at(x[k],z,config,'D3',True)
                    for key,want in [('nominal_e',a['e']),('chi_square',a['chi_square']),('s',a['s']),('information_weight',a['information_weight']),('influence',a['influence'])]:assert abs(p[key]-want)<1e-10
                    assert p['state_time_s']==times[k] and p['measurement_m']==z;checks['DCS_weight_updates']+=1
            for q in row.get('dcs_trials',[]):assert abs(ind.cost(s,np.array(q['states']).ravel(),config)-q['true_cost'])<1e-7;checks['DCS_trial_costs']+=1
            for p in row.get('dcs_final_peers',[]):
                k=times.index(p['state_time_s']);a=peer_at(s['states'][k],p['measurement_m'],config,'D3',True)
                assert abs(p['information_weight']-a['information_weight'])<1e-12
            if row['candidate_states'] is not None:assert abs(ind.cost(s,np.array(row['candidate_states']).ravel(),config)-row['optimizer']['cost'])<1e-7;checks['candidate_objectives']+=1
    return dict(checks=dict(checks),DCS_marginal_max={k:max((v[k] for v in margin),default=0.) for k in ('h_abs','g_abs','constant_abs')})


def evaluate(root,out):
    root=Path(root);out=Path(out);out.mkdir(exist_ok=False);index=json.loads((root/'RUN_INDEX.json').read_text())
    expected={f'{s}_seed{k}__{m}' for s in SCENARIOS for k in SEEDS for m in METHODS}
    assert index['status']=='DONE' and len(index['cells'])==36 and {c['run_id'] for c in index['cells']}==expected
    assert {p.name for p in (root/'new-runs').iterdir()}=={c['run_id'] for c in index['cells'] if c['method']=='D3'}
    assert {p.name for p in (root/'inputs').iterdir()}=={f'{s}_seed{k}' for s in SCENARIOS for k in SEEDS}
    for p,s in index['source_sha256'].items():assert sha(root/'source'/p)==s
    data={};costs=[];audits=[];timeline=[];config_cache={};input_cache={}
    for cell in index['cells']:
        m=cell['method'];assert cell['status']==('DONE' if m=='D3' else 'REUSED_VERIFIED');run=root/cell['run_path'];inp=root/'inputs'/cell['case']
        meta=json.loads((run/'run.json').read_text());assert sha(run/'run.json')==cell['run_sha256'] and meta['status']=='DONE'
        outputs=meta['outputs'];outputs=[dict(path=k,**v) for k,v in outputs.items()] if isinstance(outputs,dict) else outputs
        for f in outputs:assert sha(run/f['path'])==f['sha256'] and (run/f['path']).stat().st_size==f['size_bytes']
        if m=='D3':assert meta['source_sha256']==index['source_sha256'] and meta['code_commit']==index['code_commit'] and not meta['dirty']
        for name,field in [('config.json','config_sha256'),('events.jsonl.gz','events_sha256'),('truth.jsonl','truth_sha256'),('labels.json','labels_sha256')]:assert sha(inp/name)==cell[field]
        c=json.loads((inp/'config.json').read_text());events=read(inp/'events.jsonl.gz');truth={r['state_epoch_ns']:r for r in read(inp/'truth.jsonl')};rows=read(run/'updates.jsonl.gz')
        config_cache[cell['case']]=c;input_cache[cell['case']]=events
        receipt=inspect_run(rows,c,events,m);receipt.update(run_id=cell['run_id'],status='PASS');audits.append(receipt);print('AUDIT',cell['run_id'],'PASS',flush=True)
        evaluated={}
        for r in rows:
            ep=r['state_epoch_ns'];pose=r['pose'];finite=pose is not None and bool(np.isfinite(pose).all());tr=truth[ep]
            v=dict(scenario=cell['scenario'],seed=cell['seed'],method=m,state_epoch_ns=ep,t_s=r['state_time_s'],cutoff_epoch_ns=r['availability_cutoff_epoch_ns'],
                finite_pair=finite,accepted=r['accepted_graph'],status=r['status'],peer_available=r['peer_median_m'] is not None,peer_factor_used=r['peer_factor_used'],
                gate_state=r.get('gate',{}).get('state','not_applicable'),unknown=(r.get('gate',{}).get('state')=='unknown' if m=='D2' else (r['peer_median_m'] is not None and not finite)),
                main_update_wall_s=r['main_update_wall_s'],auxiliary_update_wall_s=r['auxiliary_update_wall_s'],
                window_peer_n=len(r['provenance']['window_peer_factor_ids']),prior_peer_n=len(r['provenance']['prior_peer_factor_ids']),
                prior_cross_norm=float(np.linalg.norm((np.array(r['snapshot']['prior']['matrix']).T@np.array(r['snapshot']['prior']['matrix']))[:3,3:])))
            ants=[];trueants=[]
            for i,car in enumerate(CARS):
                p=None if pose is None else pose[3*i:3*i+3];finitecar=p is not None and bool(np.isfinite(p).all());t=tr['cars'][car];ant=None if not finitecar else ind.audit.ant(p,c['models'][car]);ants.append(ant);trueants.append(np.array(t['antenna_xyz_m']))
                v.update({car+'_finite':finitecar,car+'_base_xy_m':None if not finitecar else float(np.linalg.norm(np.array(p[:2])-t['pose'][:2])),
                    car+'_antenna_xy_m':None if not finitecar else float(np.linalg.norm(ant[:2]-t['antenna_xyz_m'][:2])),car+'_yaw_rad':None if not finitecar else ind.audit.wrap(p[2]-t['pose'][2])})
            v.update(relative_xy_m=None if not finite else float(np.linalg.norm((ants[0]-ants[1])[:2]-(trueants[0]-trueants[1])[:2])),
                distance_m=None if not finite else float(np.linalg.norm(ants[0]-ants[1])-np.linalg.norm(trueants[0]-trueants[1])))
            v.update(peer_at(pose,r['peer_median_m'],c,m,r['peer_factor_used']))
            evaluated[ep]=v;timeline.append(v)
        data[cell['scenario'],cell['seed'],m]=evaluated
        costs.append(dict(scenario=cell['scenario'],seed=cell['seed'],method=m,reused=m!='D3',timing_origin=meta.get('timing_origin','current_DCS_virtual_replay'),
            publications=len(rows),finite=sum(v['finite_pair'] for v in evaluated.values()),car1_finite=sum(v['car1_finite'] for v in evaluated.values()),car2_finite=sum(v['car2_finite'] for v in evaluated.values()),
            accepted=sum(r['accepted_graph'] for r in rows),warmup=sum('warmup' in r['status'] for r in rows),failures=sum('failed' in r['status'] or 'error' in r['status'] for r in rows),
            unknown=sum(v['unknown'] for v in evaluated.values()),missing_peer=sum(r['peer_median_m'] is None for r in rows),missing_odom=sum(r['status']=='missing_odom_bracket' for r in rows),
            main_update_total_s=sum(r['main_update_wall_s'] for r in rows),auxiliary_total_s=sum(r['auxiliary_update_wall_s'] for r in rows),
            update_p95_s=float(np.percentile([r['update_wall_s'] for r in rows],95)),replay_IO_wall_s=meta.get('original_runtime_s',meta['elapsed_with_current_IO_s']),
            current_export_or_replay_s=meta['elapsed_with_current_IO_s'],peak_main_scalars=max(r['scalar_variables'] for r in rows),
            peak_aux_scalars=max([6*r['auxiliary']['graph_states'] for r in rows if r.get('auxiliary') is not None],default=0),
            linearizations=sum(len(r.get('dcs_linearizations',[])) for r in rows)))
    common={}
    for s in SCENARIOS:
        for k in SEEDS:common[s,k]=set.intersection(*[{ep for ep,v in data[s,k,m].items() if v['accepted'] and v['finite_pair']} for m in METHODS])
    metrics=[];contrasts=[];weightstats=[]
    for (s,k,m),values in data.items():
        for scope in ('all_finite','per_vehicle_accepted','joint_common_accepted'):
            for period,predicate in PERIODS.items():
                total=[v for v in values.values() if predicate(v['t_s'])]
                for metric in METRICS:
                    car=metric[:4] if metric.startswith(('car1','car2')) else None
                    selected=[v for v in total if (v[car+'_finite'] if car else v['finite_pair']) and (scope=='all_finite' or (scope=='per_vehicle_accepted' and v['accepted']) or (scope=='joint_common_accepted' and v['state_epoch_ns'] in common[s,k]))]
                    metrics.append(dict(scenario=s,seed=k,method=m,scope=scope,period=period,metric=metric,denominator=len(total),n=len(selected),rmse=rms([v[metric] for v in selected])))
        for scope in ('all_finite','joint_common_accepted'):
            for period,predicate in PERIODS.items():
                keys={ep for ep,v in values.items() if predicate(v['t_s']) and v['finite_pair'] and (scope=='all_finite' or ep in common[s,k])}
                controls=[('same_fault_input_vs_D0',data[s,k,'D0'])]
                if s!='nominal':controls.append(('same_method_fault_vs_nominal',data['nominal',k,m]))
                for name,other in controls:
                    other_case='nominal' if name=='same_method_fault_vs_nominal' else s
                    matched=keys&{ep for ep,v in other.items() if v['finite_pair'] and (scope=='all_finite' or ep in common[other_case,k])}
                    for metric in METRICS:
                        target=rms([values[ep][metric] for ep in matched]);control=rms([other[ep][metric] for ep in matched])
                        contrasts.append(dict(scenario=s,seed=k,method=m,scope=scope,period=period,contrast=name,metric=metric,n=len(matched),target_rmse=target,reference_rmse=control,delta_rmse=None if target is None else target-control))
        for period,predicate in PERIODS.items():
            vs=[v for v in values.values() if predicate(v['t_s'])];known=[v for v in vs if v['information_weight'] is not None]
            weightstats.append(dict(scenario=s,seed=k,method=m,period=period,publications=len(vs),known=len(known),unknown=sum(v['unknown'] for v in vs),
                missing=sum(not v['peer_available'] for v in vs),factor_entered=sum(v['peer_factor_used'] for v in vs),
                min_information_weight=min((v['information_weight'] for v in known),default=None),mean_information_weight=None if not known else float(np.mean([v['information_weight'] for v in known])),
                max_abs_nominal_residual_m=max((abs(v['residual_m']) for v in known),default=None),max_abs_influence=max((abs(v['influence']) for v in known),default=None)))
    # True pairing check for the sole shared-wall adapter: no generator rerun.
    for seed in SEEDS:
        nominal=input_cache[f'nominal_seed{seed}'];fault=input_cache[f'car1_common_wall_bias_seed{seed}'];assert len(nominal)==len(fault);count=0;origin=nominal[0]['receive_epoch_ns']
        for x,y in zip(nominal,fault):
            assert {k:v for k,v in x.items() if k!='value'}=={k:v for k,v in y.items() if k!='value'}
            for k,v in x['value'].items():
                hit=x['kind']=='uwb' and x.get('vehicle_id')=='car1' and k in ('node_2','node_3','node_8','node_10') and 24*10**9<=x['header_epoch_ns']-origin<38*10**9
                assert abs(y['value'][k]-v-.3)<1e-15 if hit else y['value'][k]==v
                count+=int(hit)
        assert count==1120
    for name,rows in [('metrics.csv',metrics),('paired_contrasts.csv',contrasts),('weights.csv',weightstats),('costs.csv',costs)]:csv_write(out/name,rows)
    with gzip.open(out/'timeline.csv.gz','xt',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(timeline[0]));w.writeheader();w.writerows(timeline)
    counts=Counter()
    for a in audits:counts.update(a['checks'])
    dump(out/'audits.json',dict(status='PASS',runs=audits,counts=dict(counts),every_recorded_marginalization_checked=True))
    assert not {'kernel','bindings','probe','pinned','graph','frontend','legacy','scipy.optimize'}&set(sys.modules)
    dump(out/'receipt.json',dict(status='PASS',logical_cells=36,reused=27,new_runs=9,joint_publications=len(timeline),
        counts={k:sum(r[k] for r in costs) for k in ('finite','car1_finite','car2_finite','accepted','warmup','failures','unknown','missing_peer','missing_odom')},
        common_accepted={f'{s}_seed{k}':len(v) for (s,k),v in common.items()},independent_counts=dict(counts),
        reader_sha256=sha(Path(__file__)),independent_equations_sha256=sha(Path(ind.__file__)),estimator_imports=[],
        limitations=['already exposed three seeds, no independent validation','D0-D2 historical timing is not contemporaneous with D3','D3 loss cost is an IRLS-consistent scalar adaptation, not reproduction of all paper experiments','virtual availability is not ROS latency']))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--matrix',type=Path,required=True);p.add_argument('--output',type=Path,required=True);v=p.parse_args();evaluate(v.matrix,v.output)
