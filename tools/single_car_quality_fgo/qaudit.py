#!/usr/bin/env python3
"""Independent quality/weight/causality reader. No online policy or graph imports."""
import argparse
import bisect
from collections import Counter
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import numpy as np
from qio import digest,dump,read_jsonl,sha,clean

# Reuse only PR58's already independent offline factor formula, never its live J.
OLD=Path(__file__).resolve().parents[2]/'tools/single_car_imu_fgo'
if str(OLD) not in sys.path:sys.path.append(str(OLD))
spec=importlib.util.spec_from_file_location('quality_frozen_offline_formula',OLD/'audit.py');offline=importlib.util.module_from_spec(spec);spec.loader.exec_module(offline)


def semantic(v):
    if isinstance(v,dict):return {k:semantic(x) for k,x in v.items() if not(k.endswith('_wall_s') or k.startswith(('estimated_worker_','host_','processing_')))}
    if isinstance(v,list):return [semantic(x) for x in v]
    return v


def weighted_residual(snapshot,states,config):
    arm=config['base']['arm'];r=offline.residual(snapshot,states,config['base'],arm);n=len(states);first=3*n if arm=='F0' else len(snapshot['prior']['offset'])+2*(n-1);position=first
    weights=snapshot.get('quality_weights',[{k:1. for k in o} for o in snapshot['observations']])
    for i,o in enumerate(snapshot['observations']):
        for key in sorted(o):r[position]*=math.sqrt(weights[i][key]);position+=1
    return r


def finite_jac(snapshot,states,config):
    x=np.asarray(states,dtype=float);flat=x.ravel();result=[]
    for j in range(len(flat)):
        delta=np.eye(len(flat))[j]*1e-6;result.append((weighted_residual(snapshot,(flat+delta).reshape(x.shape),config)-weighted_residual(snapshot,(flat-delta).reshape(x.shape),config))/2e-6)
    return np.column_stack(result)


def policy_expected(memory,score,p):
    mode,g,w,s,c,r=memory
    if score is None:return (mode,g,0,0,0,0),'unknown',g
    w=w+1 if score>=p['warn_score'] else 0;s=s+1 if score>=p['disable_score'] else 0;c=c+1 if score<=p['clear_score'] else 0
    if mode=='normal':
        if s>=p['disable_count']:mode,g='disabled',0.
        elif w>=p['warn_count']:mode,g='downweighted',p['lowered_information']
    elif mode in ('downweighted','disabled'):
        if s>=p['disable_count']:mode,g='disabled',0.
        elif c>=p['clear_count']:mode,g,r='recovering',p['recovery_information'],0
    elif score>=p['disable_score']:mode,g,r='disabled',0.,0
    elif score>=p['warn_score']:mode,g,r='downweighted',p['lowered_information'],0
    elif score<=p['clear_score']:
        r+=1
        if r>=p['recover_count']:mode,g='normal',1.
    else:r=0
    return (mode,g,w,s,c,r),mode,g


def predicted(pose,model,target):
    lx,ly=model['base_to_antenna_body_xy_m'];theta=pose[2];tag=np.array([pose[0]+math.cos(theta)*lx-math.sin(theta)*ly,pose[1]+math.sin(theta)*lx+math.cos(theta)*ly,model['antenna_height_m']]);d=tag-np.array(model['anchors_xyz_m'][target]);return float(np.linalg.norm(d)),tag


def audit(root,sample_every=7,events_path=None):
    root=Path(root);meta=json.loads((root/'run.json').read_text());config=json.loads((root/'config.json').read_text());base=config['base'];p={k:v['value'] for k,v in config['controller'].items()};errors=[];counts=Counter();maxima=Counter()
    def check(ok,message):
        if not ok and len(errors)<50:errors.append(message)
    for f in meta['outputs']:check((root/f['relative_path']).is_file() and sha(root/f['relative_path'])==f['sha256'],'storage SHA '+f['relative_path'])
    input_rows=list(read_jsonl(root/'input_decisions.jsonl.gz'));events=[r['input'] for r in input_rows];receives=[e['receive_epoch_ns'] for e in events];by_id={(e.get('source_file_sha256'),e['record_index'],e.get('topic')):e for e in events};origin=meta['origin_receive_epoch_ns']
    for e in events:
        check(type(e['receive_epoch_ns']) is int and type(e['record_index']) is int,'noninteger original identity')
        if e['kind'] in ('odom','imu','uwb'):check(type(e['header_epoch_ns']) is int,'noninteger header')
    records=list(read_jsonl(root/'graphs.jsonl.gz'));by_ref={r['record_id']:r for r in records};by_epoch={(r['role'],r['state_epoch_ns']):r for r in records};pubs={r['publication_id']:r for r in read_jsonl(root/'publications.jsonl.gz')};availability={r['publication_id']:r for r in read_jsonl(root/'availability.jsonl.gz')};ledger=list(read_jsonl(root/'quality_ledger.jsonl.gz'));by_factor={r['factor_id']:r for r in ledger}
    check(len(by_ref)==len(records),'duplicate graph id');check(len(by_factor)==len(ledger),'factor ledger overwritten/duplicated')
    if events_path is not None:
        check(sha(events_path)==meta['input_sha256'],'original input file SHA');actual=[clean(e) for e in read_jsonl(events_path)];check(actual==events,'input log differs from original file')
    needed={r['input_prefix_count'] for r in records};roots={'main':'0'*64};roles={r['role'] for r in records if r['role']!='main'};roots.update({k:'0'*64 for k in roles});prefixes={}
    if 0 in needed:prefixes.update({(k,0):v for k,v in roots.items()})
    for index,event in enumerate(events,1):
        roots['main']=digest(dict(previous=roots['main'],event=event))
        for role in roles:
            filtered=copy.deepcopy(event)
            if event['kind']=='uwb':filtered['value']={k:v for k,v in event['value'].items() if k!=role}
            roots[role]=digest(dict(previous=roots[role],event=filtered))
        if index in needed:prefixes.update({(k,index):v for k,v in roots.items()})
    previous={};weights_seen={};prior_last={};consumed=set();marg_count=Counter()
    def restore(snapshot,role):
        snapshot=copy.deepcopy(snapshot)
        if 'quality_weights' not in snapshot:
            if config['quality_enabled'] or role!='main':raise ValueError('adaptive graph missing frozen quality weights')
            snapshot['quality_weights']=[{k:1. for k in o} for o in snapshot['observations']]
        if base['arm']=='F3' and 'intervals' not in snapshot:
            snapshot['intervals']=[by_epoch[role,epoch]['row']['angular_interval'] for epoch in snapshot['interval_end_epochs_ns']]
        return snapshot
    for record in records:
        role=record['role'];row=record['row'];epoch=record['state_epoch_ns'];cutoff=record['availability_cutoff_epoch_ns'];counts['graph_publications']+=1
        body={k:v for k,v in record.items() if k!='record_id'};check(record['record_id']==digest(semantic(body)),'graph semantic identity')
        check(record['previous_record_id']==previous.get(role),'independent history parent chain');previous[role]=record['record_id'];check(cutoff-epoch==10**9,'1s cutoff changed')
        check(record['input_prefix_count']==bisect.bisect_right(receives,cutoff),'input prefix future/missing');check(record['input_prefix_digest']==prefixes.get((role,record['input_prefix_count'])),'complete filtered input dependency DAG differs')
        snapshot=restore(row['objective_snapshot'],role);n=len(snapshot['times_s']);check(n<=21,'window bound')
        if role not in prior_last:
            h=math.radians(base['model']['initial_heading_deg']);lx,ly=base['model']['base_to_antenna_body_xy_m'];start=base['model']['start_antenna_xyz_m'];point=[start[0]-math.cos(h)*lx+math.sin(h)*ly,start[1]-math.sin(h)*lx-math.cos(h)*ly,h]
            params=base['model']['graph_parameters'];sigma=[params['prior_position_sigma_m']]*2+[math.radians(params['prior_heading_sigma_deg'])]
            if base['arm']=='F3':point.append(base['angular']['bias_initial_rad_s']['value']);sigma.append(base['angular']['bias_initial_sigma_rad_s']['value'])
            check(np.allclose(snapshot['prior']['point'],point,atol=1e-12,rtol=0) and np.allclose(snapshot['prior']['matrix'],np.diag(1/np.array(sigma)),atol=1e-12,rtol=0) and np.linalg.norm(snapshot['prior']['offset'])==0,'initial prior not independently from declared initialization')
        if role!='main':
            check(record['excluded_target']==role,'wrong shadow exclusion');check(record['shadow_weights_adaptive'] is False,'adaptive shadow recursion')
            check(all(role not in o for o in snapshot['observations']),'excluded link in shadow active factors')
            check(role not in record['support_new']['range_medians'] and role not in record['support_new']['range_support'],'excluded link leaked through shadow dependencies')
        for identity in record['support_new']['odom_endpoints']:
            check(identity['receive_epoch_ns']<=cutoff,'late Odom endpoint');check((identity['source_file_sha256'],identity['record_index'],identity['topic']) in by_id,'Odom source missing')
        for target,support in record['support_new']['range_support'].items():
            for sample in support:
                dep=sample['identity'];key=(dep['source_file_sha256'],dep['record_index'],dep['topic']);check(key in by_id,'range dependency absent');check(dep['receive_epoch_ns']<=cutoff,'range dependency in future')
                if key in by_id:check(by_id[key]['value'][target]==sample['raw_range_m'],'raw range dependency differs')
        if row.get('angular_interval'):
            for segment in row['angular_interval']['segments']:
                dep=segment['dependency'];check(dep['receive_epoch_ns']<=cutoff and dep['mapped_header_epoch_ns']<=segment['start_epoch_ns'],'angular causal dependency')
        for i,(t,obs,weights) in enumerate(zip(snapshot['times_s'],snapshot['observations'],snapshot['quality_weights'])):
            t_ns=origin+round(t*1e9)
            for key in obs:
                gain=weights[key];counts['factor_visits']+=1;identity=(role,t_ns,key)
                if identity in weights_seen:check(weights_seen[identity]==gain,'old multiplier changed after first graph entry')
                weights_seen[identity]=gain
                if role!='main':check(gain==1.,'shadow used adaptive multiplier')
                else:
                    lid=f"{config['group']}|{t_ns}|{key}";check(lid in by_factor,'factor absent from immutable ledger')
                    if lid in by_factor:check(gain==by_factor[lid]['actual_information_multiplier'],'objective multiplier differs from ledger')
        states=snapshot.get('candidate_states')
        if states is None and row['accepted_graph']:states=snapshot['states']
        if states is not None and row.get('optimizer',{}).get('optimizer_cost') is not None:
            counts['objective_cost_checks']+=1;r=weighted_residual(snapshot,states,config);err=abs(float(r@r/2)-row['optimizer']['optimizer_cost']);maxima['objective_cost_abs']=max(maxima['objective_cost_abs'],err);check(err<1e-7,'weighted objective cost/information multiplier')
        for m in row.get('marginalization_details',[]):
            counts['marginalizations']+=1;marg_count[role]+=1;check(not m['includes_retained_UWB'],'retained factor double count')
            lin=m['linearization_input'];check(role=='main' or all(role not in o for o in lin['observations']),'excluded link in shadow marginalized history')
            if 'prior_before_digest' in m:
                check(m['prior_before_digest']==digest(lin['prior']),'prior before hash');check(m['prior_after_digest']==digest(m['prior_after']),'prior after hash')
                expected_prefix=config['group'] if role=='main' else config['group']+':shadow:'+role
                old_epoch=origin+round(lin['times_s'][0]*1e9);expected_ids={f'{expected_prefix}|{old_epoch}|{k}' for k in lin['observations'][0]}
                check(set(m['consumed_quality_factor_ids'])==expected_ids,'marginalized factors are not exactly oldest incident UWB')
                for fid in m['consumed_quality_factor_ids']:check((role,fid) not in consumed,'factor marginalized twice');consumed.add((role,fid))
                check(not m['retained_quality_factor_ids'],'retained factor declared consumed')
            if role in prior_last:check(lin['prior']==prior_last[role],'prior chain lost/replaced cross information')
            prior_last[role]=m['prior_after']
            if marg_count[role]%sample_every:continue
            counts['sampled_marginalizations']+=1;x=np.array(lin['states']);r=weighted_residual(lin,x,config);J=finite_jac(lin,x,config);d=x.shape[1];A=J[:,:d];B=J[:,d:]-A@np.linalg.lstsq(A,J[:,d:],rcond=None)[0];rr=r-A@np.linalg.lstsq(A,r,rcond=None)[0];M=np.array(m['prior_after']['matrix']).reshape(-1,d);off=np.array(m['prior_after']['offset']);h=float(np.max(np.abs(M.T@M-B.T@B)));g=float(np.max(np.abs(M.T@off-B.T@rr)));maxima['marginal_information_abs']=max(maxima['marginal_information_abs'],h);maxima['marginal_affine_abs']=max(maxima['marginal_affine_abs'],g)
            check(np.allclose(M.T@M,B.T@B,atol=.03,rtol=1e-5),'weighted marginal cross-information');check(np.allclose(M.T@off,B.T@rr,atol=.001,rtol=1e-5),'weighted marginal affine');check(abs(float(rr@rr-off@off)-m['eliminated_constant'])<.001,'weighted marginal constant')
        if row.get('marginalization_details'):check(snapshot['prior']==prior_last[role],'current prior does not match last marginal')
        elif role not in prior_last:prior_last[role]=snapshot['prior']
    memory={k:('normal',1.,0,0,0,0) for k in base['model']['anchors_xyz_m']}
    for entry in ledger:
        counts['quality_decisions']+=1;target=entry['target'];epoch=entry['state_epoch_ns'];cutoff=entry['availability_cutoff_epoch_ns'];aggregate=entry['raw_aggregate_m'];pid=entry['publication_id'];expected_score=None
        check(entry['frozen_before_main_solve'] and entry['no_history_rollback'],'freeze/history contract');check(entry['original_link_quality'] is None,'manufactured original quality')
        if config['quality_enabled']:
            reference=by_ref.get(entry['reference_record_id']);valid=aggregate is not None and reference is not None and bool(reference['row']['accepted_graph']) and reference['row'].get('numerical_full_rank',False)
            if valid and base['arm']=='F3':valid=reference['row']['angular_valid']
            if reference:
                check(reference['role']==target and reference['excluded_target']==target,'circular/wrong reference');check(reference['state_epoch_ns']==epoch and reference['availability_cutoff_epoch_ns']==cutoff,'future/stale shadow')
            if valid:
                obs=reference['row']['objective_snapshot']['observations'][-1];other=sorted(k for k in obs if k!=target);valid=len(other)>=p['min_other_links']
                if valid:
                    distance,point=predicted(reference['row']['pose'],base['model'],target);H=[]
                    for k in other:
                        delta=point-np.array(base['model']['anchors_xyz_m'][k]);H.append(delta[:2]/np.linalg.norm(delta))
                    singular=np.linalg.svd(H,compute_uv=False);valid=singular[-1]/singular[0]>=p['min_xy_singular_ratio']
                if valid:
                    signed=aggregate-base['model']['range_bias_m'][target]-distance;expected_score=abs(signed)/p['score_scale_m'];check(abs(entry['raw_signed_consistency_residual_m']-signed)<1e-10,'raw signed consistency residual')
            if not entry['target_dependencies'] and aggregate is not None:check(False,'aggregate without supporting inputs')
            if aggregate is not None:check(abs(aggregate-float(np.median([r['raw_range_m'] for r in entry['target_dependencies']])))<1e-12,'target raw median')
            check((entry['engineering_score'] is None)==(expected_score is None),'unknown forced healthy or circular score')
            if expected_score is not None:check(abs(entry['engineering_score']-expected_score)<1e-10,'engineering score differs from excluded reference')
            memory[target],state,gain=policy_expected(memory[target],expected_score,p);check(entry['policy']['state']==state,'persistence/recovery/unknown state');check(entry['policy']['information_multiplier']==gain,'hysteresis multiplier')
        else:gain=1.;check(entry['policy']['state']=='unmonitored' and entry['engineering_score'] is None,'baseline monitor invented')
        check(entry['actual_information_multiplier']==(gain if aggregate is not None else None),'missing measurement treated as zero or wrong gain');check(entry['information_admitted']==bool(aggregate is not None and gain>0),'information admission')
        if aggregate is not None:
            check(abs(entry['actual_residual_sqrt_multiplier']**2-gain)<1e-12,'gain applied twice or not sqrt');check(abs(entry['actual_nominal_information_per_m2']-gain/base['model']['graph_parameters']['range_sigma_m']**2)<1e-12,'actual information scale')
        check(pid in pubs and pid in availability,'ledger publication join missing')
        if pid in pubs:
            pub=pubs[pid];check(entry['frozen_host_monotonic_ns']<=pub['main_solve_start_monotonic_ns']<=pub['main_solve_finish_monotonic_ns'],'decision after main solve')
    for pub in pubs.values():
        diag=pub.get('motion_conflict_diagnostic')
        if diag:
            check(diag['not_used_for_quality'] and diag['comparison_is_not_truth'],'motion conflict used as truth/control')
            gyro,odom=diag['gyro_interval'],diag['odom_rate_interval']
            if gyro and odom and gyro['valid'] and odom['valid']:check(abs(diag['raw_odom_rate_minus_gyro_rad']-(odom['raw_angle_rad']-gyro['raw_angle_rad']))<1e-12,'conflict diagnostic arithmetic')
    for pid,a in availability.items():
        counts['availability_records']+=1;check(a['available_receive_epoch_ns']>=a['availability_cutoff_epoch_ns'],'alarm available before1s cutoff')
        if config['timing']['paced']:
            check(a['timing_mode']=='paced_actual_host_monotonic_mapping','validation timing not paced');check(a['available_receive_epoch_ns']==origin+a['data_flushed_host_monotonic_ns']-a['host_anchor_monotonic_ns'],'actual host clock mapping')
        if pid in pubs:check(a['data_flushed_host_monotonic_ns']>=pubs[pid]['main_solve_finish_monotonic_ns'],'publication precedes main finish')
    return dict(status='PASS' if not errors else 'FAIL',errors=errors,counts=dict(counts),maximum_absolute_errors=dict(maxima),marginalization_sampling_stride=sample_every,online_formula_or_J_used=False,online_module_names_already_in_process=[k for k in ['bridge','qgraph','qpolicy','graph','single_car_fixed_lag'] if k in sys.modules],
                shared_offline_formula='read-only PR58 independent audit.residual, not live Objective/Jacobian',F0_native_marginalization_detail='unmodified native F0 has no per-marginal record; covered by closing regression and existing PR58/59, not counted as new numerical audit')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--events-jsonl',type=Path);a=p.parse_args();r=audit(a.run,events_path=a.events_jsonl);dump(a.output,r);print(json.dumps(r));raise SystemExit(0 if r['status']=='PASS' else 1)
