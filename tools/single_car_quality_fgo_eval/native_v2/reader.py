"""Independent native log reader. Never imports A qpolicy/graph/J/qaudit."""
import argparse
import bisect
from collections import Counter,defaultdict
import copy
import csv
import json
import math
from pathlib import Path
import statistics
import numpy as np
from .common import ROOT,begin,finish,lines,require,sha,write,digest
from .policy_math import initial,step,score_gate,antenna_xyz,check_policy
from .numerics import weighted_residual,marginal,prior_mean,prediction
from verify_fgo import check_edge as B_PR59_check_edge

IDENTITY=('source_file_sha256','record_index','topic','header_epoch_ns','receive_epoch_ns')


def near(a,b,reason,tolerance=1e-10):require(np.allclose(a,b,atol=tolerance,rtol=0,equal_nan=False),reason)


def key(row):return (row['source_file_sha256'],row['record_index'],row['topic'])


def sensors(events,base):
    origin=events[0]['receive_epoch_ns'];odom=[];uwb=[];last=None
    for r in events:
        for k in ('receive_epoch_ns','record_index'):require(type(r[k]) is int,'integer original identity')
        if r['kind'] in ('odom','uwb','imu'):require(type(r['header_epoch_ns']) is int,'integer original header')
        if r['kind']=='odom':
            x=list(r['value']['pose']);x[2]=x[2] if last is None else last+math.atan2(math.sin(x[2]-last),math.cos(x[2]-last));last=x[2];odom.append(((r['header_epoch_ns']-origin)/1e9,r['receive_epoch_ns'],x,r))
        elif r['kind']=='uwb':uwb.append(r)
    return origin,odom,uwb


def support_for(epoch,cutoff,origin,odom,uwb,base):
    t=(epoch-origin)/1e9;available=[o for o in odom if o[1]<=cutoff];stamps=[o[0] for o in available];idx=bisect.bisect_left(stamps,t);ends=[];local=None
    if idx<len(stamps) and stamps[idx]==t:local=available[idx][2];ends=[available[idx][3]]
    elif 0<idx<len(stamps):
        a,b=available[idx-1],available[idx];f=(t-a[0])/(b[0]-a[0]);local=[x+f*(y-x) for x,y in zip(a[2],b[2])];ends=[a[3],b[3]]
    support=defaultdict(list);model=base['model']
    for r in uwb:
        if r['receive_epoch_ns']>cutoff or abs((r['header_epoch_ns']-origin)/1e9-t)>.4:continue
        for target,raw in r['value'].items():
            if target in model['anchors_xyz_m'] and math.isfinite(raw) and raw>0 and raw-model['range_bias_m'][target]>0:support[target].append((r,raw))
    medians={k:statistics.median(v for _,v in rows) for k,rows in support.items() if len(rows)>=5}
    return dict(local=local,odom=ends,support=dict(support),medians=medians)


def check_identity(actual,original,cutoff):
    for name in IDENTITY:require(actual[name]==original[name],'dependency original identity mismatch '+name)
    for name in ('header_epoch_ns','receive_epoch_ns','record_index'):require(type(actual[name]) is int,'float original ns/index')
    require(actual['mapped_header_epoch_ns']==original['header_epoch_ns'],'PR59 identity clock mapping changed');require(actual['receive_epoch_ns']<=cutoff,'future dependency')


def prefix_hashes(events,targets):
    hashes={role:['0'*64] for role in ['main']+targets}
    for event in events:
        for role in hashes:
            row=copy.deepcopy(event)
            if role!='main' and row['kind']=='uwb':row['value'].pop(role,None)
            hashes[role].append(digest(dict(previous=hashes[role][-1],event=row)))
    return hashes


def check_run(directory,ready,expected_config_sha,expected_input_sha):
    meta=json.loads((directory/'run.json').read_text());config=json.loads((directory/'config.json').read_text());base=config['base'];group=config['group'];enabled=config['quality_enabled'];p={k:x['value'] for k,x in config['controller'].items()};stats=Counter();maximum=Counter()
    require(meta['status']=='DONE' and not meta['worktree_dirty'],'completed clean execution');require(meta['config_sha256']==expected_config_sha and meta['input_sha256']==expected_input_sha,'run frozen input/config binding')
    for f in meta['outputs']:require(sha(directory/f['relative_path'])==f['sha256'],'run output SHA '+f['relative_path'])
    events=lines(ready/'events.jsonl.gz');require(sha(ready/'events.jsonl.gz')==expected_input_sha,'actual input SHA');decisions=lines(directory/'input_decisions.jsonl.gz');require([r['input'] for r in decisions]==events,'actual estimator input content/order changed')
    source={key(r):r for r in events if r['kind'] in ('uwb','odom','imu')};require(len(source)==sum(r['kind'] in ('uwb','odom','imu') for r in events),'duplicate original message identity')
    catalog=json.loads(__import__('gzip').open(ready/'scalar_catalog.json.gz','rt').read());components=defaultdict(list)
    for item in catalog.values():
        if item['kind']=='uwb_component':components[key(item),item['link_id']].append(item)
    for event in events:
        if event['kind']!='uwb':continue
        for target,value in event['value'].items():
            raw=components[key(event),target];require(len(raw)==1 and not raw[0]['ambiguous_link_in_frame'],'scalar component ambiguity');require(raw[0]['component_value']==value and raw[0]['raw_message_sha256']==event['raw_message_sha256'],'original scalar/message-SHA sidecar changed');stats['original_scalar_bindings']+=1
    controls=[];last_control=None
    for raw in events:
        if raw['kind']!='imu':continue
        if raw['header_epoch_ns']>raw['receive_epoch_ns'] or last_control is not None and raw['header_epoch_ns']<=last_control:continue
        vector=raw['value'];require(vector['frame_id']==base['angular']['imu_frame_id']['value'] and vector['units']=='rad/s','gyro frame/units changed');rate=sum(a*b for a,b in zip(vector['angular_velocity_rad_s'],base['angular']['body_z_in_imu_frame']['value']));require(math.isfinite(rate),'nonfinite angular source');controls.append(dict(raw,rate=rate));last_control=raw['header_epoch_ns']
    origin,odom,uwb=sensors(events,base);targets=sorted(base['model']['anchors_xyz_m']);prefix=prefix_hashes(events,targets if enabled else []);receives=[r['receive_epoch_ns'] for r in events];support={};histories=defaultdict(dict);roles={};by_id={};edges={};carried={};consumed=defaultdict(set);graphrows=lines(directory/'graphs.jsonl.gz');graph_by_state=defaultdict(dict)
    for graph in graphrows:
        role=graph['role'];row=graph['row'];epoch=graph['state_epoch_ns'];cutoff=graph['availability_cutoff_epoch_ns'];require(type(epoch) is int and type(cutoff) is int and cutoff-epoch==10**9,'integer original one-second wait');require(role in ['main']+(targets if enabled else []),'unexpected graph role')
        require(graph['previous_record_id']==roles.get(role),'broken own shadow/history chain');roles[role]=graph['record_id'];require(graph['record_id'] not in by_id,'duplicate graph identity');by_id[graph['record_id']]=graph;graph_by_state[epoch][role]=graph;stats['graph_publications']+=1
        count=bisect.bisect_right(receives,cutoff);require(graph['input_prefix_count']==count,'future or incomplete arrived input prefix');require(graph['input_prefix_digest']==prefix[role][count],'shadow input filtering/prefix digest mismatch')
        if epoch not in support:support[epoch]=support_for(epoch,cutoff,origin,odom,uwb,base)
        original=support[epoch];s=graph['support_new'];require(s['state_epoch_ns']==epoch and s['availability_cutoff_epoch_ns']==cutoff,'support state/cutoff')
        require(len(s['odom_endpoints'])==len(original['odom']),'Odom bracket support');
        for actual,raw in zip(s['odom_endpoints'],original['odom']):check_identity(actual,raw,cutoff)
        for target in targets:
            wanted=[] if role==target else original['support'].get(target,[]);actual=s['range_support'].get(target,[]);require(len(actual)==len(wanted),'complete original range support mismatch')
            for dep,(raw,value) in zip(actual,wanted):check_identity(dep['identity'],raw,cutoff);require(dep['raw_range_m']==value,'range value changed')
        medians={k:v for k,v in original['medians'].items() if k!=role};require(s['range_medians']==medians and row['range_medians_m']==medians,'original aggregation or excluded link changed');near(row['local_odom'],original['local'],'Odom interpolation changed')
        require(row['dependency_receipt_max_s']<=row['availability_cutoff_s']+1e-12,'future recorded dependency maximum');snap=copy.deepcopy(row['objective_snapshot']);history=histories[role];previous=history[max(history)] if history else None;history[row['state_time_s']]=row
        if row.get('angular_interval') is not None:
            edges[role,epoch]=row['angular_interval'];nsegments,ngaps=B_PR59_check_edge(row['angular_interval'],controls,cutoff,base['angular']['max_hold_ns']['value']);stats['independent_gyro_segments']+=nsegments;stats['gyro_gaps']+=ngaps
        if base['arm']=='F3':snap['intervals']=[edges[role,e] for e in snap.get('interval_end_epochs_ns',[])]
        else:snap['intervals']=None
        row['objective_snapshot']=snap
        require(len(snap['states'])<=21 and row['graph_states']==len(snap['states']),'21-keyframe budget')
        for time,obs,local,w in zip(snap['times_s'],snap['observations'],snap['local_odom'],snap['quality_weights']):
            require(obs==history[time]['range_medians_m'] and local==history[time]['local_odom'],'historical observations/translation altered');require(set(w)==set(obs),'weight/constraint set mismatch')
            if role!='main':require(role not in obs and all(v==1 for v in w.values()),'excluded link or adaptive weight in shadow history')
        guess=row.get('optimizer_initial_guess')
        if previous is None:
            expected_prior=prior_mean(base);near(snap['states'][0],expected_prior['point'],'external initialization changed');near(snap['prior']['matrix'],expected_prior['matrix'],'external initial prior changed');carried[role]=snap['prior']
        else:
            predicted=prediction(previous,row['local_odom'],row.get('angular_interval'),base)
            if base['arm']=='F3':near(row['prediction_pose'],predicted[:3],'hidden odom yaw in new prediction');require(not row['odom_yaw_fallback'],'unexpected angular fallback')
            if guess is not None:
                prev={t:x for t,x in zip(previous['objective_snapshot']['times_s'],previous['objective_snapshot']['states'])};expected=[prev[t] if t in prev else predicted.tolist() for t in snap['times_s']];near(guess,expected,'optimization initial guess absorbed main/target/other history');stats['full_optimizer_initial_guesses']+=1
        for m in row.get('marginalization_details',[]):
            small=m['linearization_input'];old,next_time=small['times_s'];require(small['observations']==[history[old]['range_medians_m'],{}],'retained UWB duplicated in marginalization');require(not m.get('includes_retained_UWB',False),'retained factors double counted')
            if role!='main':require(all(role not in obs for obs in small['observations']),'excluded link in carried prior incident factors')
            require(small['prior']==carried[role],'carried prior chain crosses graph role/history');result=marginal(m,base);carried[role]=m['prior_after'];stats['marginalizations']+=1
            for k,x in result.items():
                if x is not None:maximum[k]=max(maximum[k],x)
            ids=m.get('consumed_quality_factor_ids',[]);require(len(ids)==len(set(ids)) and not consumed[role].intersection(ids),'factor eliminated twice');consumed[role].update(ids)
        if group!='Q0':require(snap['prior']==carried[role],'current prior differs from own carried chain')
        if group=='Q0' and row['marginalizations']>0:stats['legacy_Q0_marginals_without_new_incident_detail']=row['marginalizations']
        states=snap['candidate_states'] if snap.get('candidate_states') is not None else snap['states'];cost=row['optimizer'].get('optimizer_cost')
        if cost is not None and (row['accepted_graph'] or snap.get('candidate_states') is not None):
            r=weighted_residual(snap,states,base);err=abs(float(r@r/2)-cost);require(err<1e-7,'independent weighted objective cost mismatch');maximum['objective_cost_abs']=max(maximum['objective_cost_abs'],err);stats['objective_costs']+=1
    ledger=lines(directory/'quality_ledger.jsonl.gz');require(len(ledger)==4*len(histories['main']),'every publication every link ledger coverage');states={k:initial() for k in targets};by_factor={}
    for item in ledger:
        target=item['target'];epoch=item['state_epoch_ns'];cutoff=item['availability_cutoff_epoch_ns'];require(item['factor_id']==group+'|'+str(epoch)+'|'+target and item['factor_id'] not in by_factor,'factor identity/duplicate');by_factor[item['factor_id']]=item;stats['quality_decisions']+=1;raw=support[epoch];aggregate=raw['medians'].get(target);require(item['raw_aggregate_m']==aggregate,'quality uses another median')
        deps=raw['support'].get(target,[]);require(len(item['target_dependencies'])==len(deps),'quality target support omitted')
        for dep,(event,value) in zip(item['target_dependencies'],deps):check_identity(dep['identity'],event,cutoff);require(dep['raw_range_m']==value,'quality scalar changed')
        require(item['P1_subtracted_m']==base['model']['range_bias_m'][target],'P1 source changed');require(item['corrected_aggregate_m']==(aggregate-item['P1_subtracted_m'] if aggregate is not None else None),'P1 not applied once');require(item['original_link_quality'] is None,'unknown original quality fabricated')
        if enabled:
            shadow=by_id.get(item['reference_record_id']);require(shadow is not None and shadow['role']==target and shadow['state_epoch_ns']==epoch and shadow['availability_cutoff_epoch_ns']==cutoff,'stale/future/main shadow reference')
            score,reason,geometry,signed,pred=score_gate(item,shadow,base,p,bool(raw['odom']));require(item['engineering_score'] is None if score is None else item['engineering_score'] is not None and abs(item['engineering_score']-score)<1e-10,'native consistency score mismatch')
            require(item['raw_signed_consistency_residual_m'] is None if signed is None else abs(item['raw_signed_consistency_residual_m']-signed)<1e-10,'postfit main residual substituted for shadow score')
            if geometry is None:require(item['reference_geometry'] is None,'geometry gate fabricated')
            else:near(item['reference_geometry']['singular_values'],geometry['singular_values'],'XY singular geometry changed');require(abs(item['reference_geometry']['ratio']-geometry['ratio'])<1e-10,'XY geometry ratio')
            states[target],expected=step(states[target],score,reason,p)
            check_policy(item['policy'],expected)
        else:require(item['policy']['state']=='unmonitored' and item['policy']['information_multiplier']==1. and item['engineering_score'] is None,'baseline quality is not off')
        require(item['original_sigma_m']==base['model']['graph_parameters']['range_sigma_m'],'original range sigma changed');require(abs(item['base_nominal_information_per_m2']-1/item['original_sigma_m']**2)<1e-10,'old nominal information changed')
        gain=item['policy']['information_multiplier'];actual=None if aggregate is None else gain;require(item['actual_information_multiplier']==actual,'actual factor information gain/null differs');require(item['actual_residual_sqrt_multiplier']==(math.sqrt(gain) if aggregate is not None else None),'actual sqrt(g) differs');require(item['information_admitted']==bool(aggregate is not None and gain>0),'positive information/admission mismatch')
        expected_action='absent_no_factor' if aggregate is None else 'zero_information_row' if gain==0 else 'weighted_pseudo_huber_row';require(item['factor_action']==expected_action,'missing/disabled factor distinction')
    for graph in graphrows:
        if graph['role']!='main':continue
        snap=graph['row']['objective_snapshot'];ids=snap.get('quality_factor_ids')
        for i,(t,obs,weights) in enumerate(zip(snap['times_s'],snap['observations'],snap['quality_weights'])):
            epoch=origin+round(t*1e9)
            for target in obs:
                factor=by_factor[group+'|'+str(epoch)+'|'+target];require(weights[target]==factor['actual_information_multiplier'],'ledger gain not truly applied or historical gain rewritten')
                if ids is not None:require(ids[i][target]==factor['factor_id'],'graph factor ID lacks ledger provenance')
    publications=lines(directory/'publications.jsonl.gz');availability=lines(directory/'availability.jsonl.gz');require(len(publications)==len(availability)==len(histories['main']),'availability/reference publication coverage');available={x['publication_id']:x for x in availability};require(len(available)==len(availability),'duplicate actual availability')
    for output in publications:
        epoch=output['state_epoch_ns'];a=available[output['publication_id']];require(output['actual_available_receive_epoch_ns'] is None,'premature pre-flush available time');require(a['timing_mode']=='paced_actual_host_monotonic_mapping','actual vs virtual timing mixed');require(a['available_receive_epoch_ns']==origin+a['data_flushed_host_monotonic_ns']-meta['host_anchor_monotonic_ns'],'actual host elapsed mapping mismatch')
        require(a['data_flushed_host_monotonic_ns']>=output['main_solve_finish_monotonic_ns']>=output['main_solve_start_monotonic_ns']>=output['processing_cycle_start_monotonic_ns'],'processing/flush order')
        require(a['available_receive_epoch_ns']>=epoch+10**9 and abs(a['actual_release_delay_s']-(a['available_receive_epoch_ns']-epoch)/1e9)<1e-12,'actual wait/delay arithmetic')
        for target in targets:
            entry=by_factor[group+'|'+str(epoch)+'|'+target];require(entry['frozen_host_monotonic_ns']<=output['main_solve_start_monotonic_ns'],'quality decision not frozen before main update')
        for diag in output['postfit_factor_diagnostics']:
            entry=by_factor[diag['factor_id']];point=antenna_xyz(output['row']['pose'],base['model']);res=(np.linalg.norm(point-base['model']['anchors_xyz_m'][entry['target']])-entry['corrected_aggregate_m'])/entry['original_sigma_m'];original=res*math.sqrt(2/(math.hypot(1,res)+1));weighted=math.sqrt(entry['actual_information_multiplier'])*original
            require(abs(diag['actual_weighted_residual']-weighted)<1e-10 and diag['not_used_for_quality'],'sqrt(g) not realized in post-fit objective diagnostic');stats['weighted_factor_diagnostics']+=1
    return dict(status='PASS',group=group,case_id=meta['input_case_id'],counts=dict(stats),maximum_absolute_errors=dict(maximum),A_online_policy_graph_Jacobian_or_qaudit_imported=False,
      shared_formula_scope='B PR59 independent scalar residuals plus B native quality formula; original JSON parsing/hash only shared',limitations=['Q0 old F0 supplies no per-step incident-factor detail; all publication regression plus fixed source and original PR59 marginal evidence retained','dependency completeness also requires fixed-source inspection and executed cache/target intervention, reported separately','physical axes/clock/geometry are inherited conditional assumptions, not calibrated by this audit'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--performance',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=begin(a.output,'B_independent_native_historical_readback')
    try:
        binding=json.loads((a.prepared/'binding.json').read_text());checks=[]
        for item in binding['matrix']:
            result=check_run(a.performance/(item['case_id']+'_'+item['group']),a.prepared/'stage1/ready_for_A_001'/item['case_id'],item['config_sha256'],item['input_sha256']);checks.append(result);print(item['case_id'],item['group'],'PASS',flush=True)
        write(a.output/'verification.json',dict(status='PASS',checks=checks,performance_matrix_sha256=sha(a.performance/'matrix.json'),A_execution_commit=binding['A_execution_commit']));finish(a.output,run);return 0
    except Exception as e:finish(a.output,run,e);raise


if __name__=='__main__':raise SystemExit(main())
