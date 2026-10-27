"""B's independent serialized-input/factor reader; never imports A graph or audit.

Checks outputs, not a second estimator. Finite differences differentiate this
reader's residuals only. Shared B frontend checks use the separately frozen
legacy view, whose bag decoder was independently verified in stage 1.
"""
import argparse
import bisect
from collections import Counter
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import numpy as np
from meta import HERE,LEGACY,ROOT,finish,save,sha,start
from verify_baseline import check_frontend,compare_publications


def loadlines(path):
    with gzip.open(path,'rt') as f:return [json.loads(line) for line in f]


def angle(value):return math.atan2(math.sin(value),math.cos(value))


def require(ok,message):
    if not ok:raise ValueError(message)


def residual(snapshot,states,config):
    """Documented cost, expressed without calling any production factor."""
    states=np.asarray(states,float);n,d=states.shape;p=config['model']['graph_parameters'];model=config['model']
    prior=snapshot['prior'];diff=states[0]-np.asarray(prior['point']);diff[2]=angle(diff[2])
    chunks=[np.asarray(prior['matrix']).reshape(-1,d)@diff+prior['offset']]
    local=np.asarray(snapshot['local_odom'])
    for i in range(n-1):
        dt=snapshot['times_s'][i+1]-snapshot['times_s'][i]
        def body(yaw,v):
            u=complex(float(v[0]),float(v[1]))*complex(math.cos(yaw),-math.sin(yaw));return np.array([u.real,u.imag])
        measured=body(local[i,2],local[i+1,:2]-local[i,:2]);predicted=body(states[i,2],states[i+1,:2]-states[i,:2])
        chunks.append((predicted-measured)/(p['odom_translation_sigma_m']*math.sqrt(dt)))
        if config['arm']=='F0':chunks.append(np.array([angle(states[i+1,2]-states[i,2]-angle(local[i+1,2]-local[i,2]))/(math.radians(p['odom_yaw_sigma_deg'])*math.sqrt(dt))]))
        else:
            edge=snapshot['intervals'][i];qg=config['angular']['angle_noise_density_rad_sqrt_s']['value']**2;qb=config['angular']['bias_random_walk_rad_s_sqrt_s']['value']**2
            if edge['valid']:
                e=angle(states[i+1,2]-states[i,2]-edge['raw_angle_rad']+(states[i,3]*dt if d==4 else 0))
                if d==3:chunks.append(np.array([e/math.sqrt(qg*dt)]))
                else:
                    covariance=np.array([[qg*dt+qb*dt**3/3,-qb*dt**2/2],[-qb*dt**2/2,qb*dt]])
                    chunks.append(np.linalg.solve(np.linalg.cholesky(covariance),[e,states[i+1,3]-states[i,3]]))
            elif d==4:chunks.append(np.array([(states[i+1,3]-states[i,3])/math.sqrt(qb*dt)]))
    for state,observations in zip(states,snapshot['observations']):
        arm=complex(*model['base_to_antenna_body_xy_m'])*complex(math.cos(state[2]),math.sin(state[2]));xyz=np.array([state[0]+arm.real,state[1]+arm.imag,model['antenna_height_m']])
        for key,raw in sorted(observations.items()):
            error=(np.linalg.norm(xyz-model['anchors_xyz_m'][key])-(raw-model['range_bias_m'][key]))/p['range_sigma_m']
            chunks.append(np.array([error*math.sqrt(2/(math.hypot(1,error)+1))]))
    return np.concatenate(chunks)


def marginal_check(item,config):
    snap=item['linearization_input'];x=np.asarray(snap['states'],float);flat=x.ravel();d=x.shape[1];r=residual(snap,x,config);columns=[]
    for col in range(flat.size):
        step=np.zeros_like(flat);step[col]=1e-6
        columns.append((residual(snap,(flat+step).reshape(x.shape),config)-residual(snap,(flat-step).reshape(x.shape),config))/(2e-6))
    j=np.column_stack(columns);left,right=j[:,:d],j[:,d:]
    # SVD least squares handles a semidefinite old block; no fabricated diagonal.
    j_cond=right-left@np.linalg.lstsq(left,right,rcond=None)[0];r_cond=r-left@np.linalg.lstsq(left,r,rcond=None)[0]
    after=item['prior_after'];a=np.asarray(after['matrix']).reshape(-1,d);c=np.asarray(after['offset']);expected_h=j_cond.T@j_cond;expected_g=j_cond.T@r_cond
    h=a.T@a;g=a.T@c
    require(np.allclose(h,expected_h,rtol=1e-5,atol=.03),'independent marginal information/cross terms')
    require(np.allclose(g,expected_g,rtol=1e-5,atol=.001),'independent marginal affine gradient')
    constant=abs(float(r_cond@r_cond-c@c)-item['eliminated_constant']);require(constant<.001,'marginal discarded constant')
    require(np.allclose(after['point'],x[1],rtol=0,atol=1e-12),'marginal boundary linearization point')
    return dict(information_abs=float(np.max(np.abs(h-expected_h))),gradient_abs=float(np.max(np.abs(g-expected_g))),constant_abs=constant,
        offdiagonal_information_abs=float(np.max(np.abs(h-np.diag(np.diag(h))))),bias_cross_information_abs=float(np.max(np.abs(h[:3,3]))) if d==4 else None)


def expected_segments(controls,start_ns,end_ns,cutoff,hold):
    eligible=[x for x in controls if x['receive_epoch_ns']<=cutoff];stamps=[x['header_epoch_ns'] for x in eligible];cursor=start_ns;pieces=[]
    while cursor<end_ns:
        left=bisect.bisect_right(stamps,cursor)-1
        next_source=stamps[left+1] if left+1<len(stamps) else end_ns
        limit=min(end_ns,next_source)
        if left<0 or cursor>=stamps[left]+hold:
            pieces.append(('gap',cursor,limit,None));cursor=limit
        else:
            limit=min(limit,stamps[left]+hold);pieces.append(('segment',cursor,limit,eligible[left]));cursor=limit
    return pieces


def check_edge(edge,controls,cutoff,hold):
    expected=expected_segments(controls,edge['start_epoch_ns'],edge['end_epoch_ns'],cutoff,hold)
    actual=sorted([('segment',s['start_epoch_ns'],s['end_epoch_ns'],s) for s in edge['segments']]+[('gap',s['start_epoch_ns'],s['end_epoch_ns'],s) for s in edge['gaps']],key=lambda x:x[1])
    require(len(expected)==len(actual),'angular partition size')
    integral=0.
    for want,got in zip(expected,actual):
        kind,a,b,source=want;k2,a2,b2,row=got
        require((kind,a,b)==(k2,a2,b2),'angular gap/segment boundary')
        if kind=='segment':
            require(all(row['dependency'][k]==source[k] for k in ('record_index','source_file_sha256','topic','header_epoch_ns','receive_epoch_ns')),'angular dependency raw identity')
            require(row['dependency']['mapped_header_epoch_ns']==source['header_epoch_ns'],'identity hypothesis violated')
            require(abs(row['rate_rad_s']-source['rate'])<1e-12,'angular sign/rate/units')
            value=source['rate']*(b-a)/1e9;integral+=value
            require(abs(row['angle_rad']-value)<1e-12,'segment integration')
    valid=all(x[0]=='segment' for x in expected)
    require(valid==edge['valid'],'angular validity/coverage')
    require(abs(integral-edge['partial_angle_rad'])<1e-10,'partial angular integral')
    require(abs(integral-edge['raw_angle_rad'])<1e-10 if valid else edge['raw_angle_rad'] is None,'complete angular integral')
    return len(edge['segments']),len(edge['gaps'])


def raw_adapter_check(rich,flat):
    require(len(rich)==len(flat),'adapted message coverage')
    for r,f in zip(rich,flat):
        for key in ('kind','case_id','record_index','source_file_sha256','topic','header_epoch_ns','receive_epoch_ns','raw_message_sha256'):require(r[key]==f[key],'adapter identity '+key)
        require(type(f['record_index']) is int and type(f['receive_epoch_ns']) is int,'integer flat identity')
        m=r['message'];kind=r['kind']
        if kind=='imu':
            expected={'angular_velocity_rad_s':[m['angular_velocity'][k] for k in 'xyz'],'frame_id':m['header']['frame_id'],'units':'rad/s'}
            require(f['value']==expected,'real gyro vector/frame changed')
        elif kind=='odom':
            q=m['pose']['pose']['orientation'];v=np.array([q[k] for k in ('x','y','z','w')]);v/=np.linalg.norm(v);x,y,z,w=v;p=m['pose']['pose']['position']
            expected=[p['x'],p['y'],math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))]
            require(np.allclose(f['value']['pose'],expected,rtol=0,atol=1e-15),'Odom pose conversion')
            require(f['value']['angular_z_rad_s']==m['twist']['twist']['angular']['z'],'Odom angular rate changed')
        elif kind=='uwb':
            counts=Counter(x['anchor_id'] for x in m['ranges']);expected={x['anchor_id']:x['range'] for x in m['ranges'] if counts[x['anchor_id']]==1}
            require(f['value']==expected,'raw UWB duplicate/P1 policy')
    return len(flat)


def inspect_run(directory,flat,legacy_events,legacy,execution,config_hash):
    meta=json.loads((directory/'run.json').read_text());config=json.loads((directory/'config.json').read_text());arm=config['arm'];counts=Counter();maximum=Counter();marginals=[]
    require(meta['status']=='DONE' and not meta['worktree_dirty'],'completed clean frozen execution')
    require(meta['config_sha256']==config_hash,'run config SHA')
    for item in meta['outputs']:require(sha(directory/item['relative_path'])==item['sha256'],'output SHA '+item['relative_path'])
    for name,digest in meta['source_sha256'].items():require(sha(execution/name)==digest,'execution source changed '+name)
    decisions=loadlines(directory/'input_decisions.jsonl.gz');require(len(decisions)==len(flat),'input decision coverage')
    controls=[];last_control=None;kind='odom' if arm=='F1' else 'imu';axis=config['angular']['body_z_in_imu_frame']['value'];rejections=Counter()
    for f,d in zip(flat,decisions):
        require(d['input']==f,'serialized estimator input changed')
        if f['kind'] in ('odom','uwb','imu'):require(d['mapped_identity']['mapped_header_epoch_ns']==f['header_epoch_ns'],'uncorrected clock hypothesis changed')
        if arm!='F0' and f['kind']==kind:
            status='angular_control_accepted'
            if f['header_epoch_ns']>f['receive_epoch_ns']:status='angular_source_after_receipt'
            elif last_control is not None and f['header_epoch_ns']<=last_control:status='duplicate_or_out_of_order_angular_source'
            require(d['angular_status']==status,'angular acceptance decision')
            rejections[status]+=1
            if status=='angular_control_accepted':
                value=dict(f);value['rate']=f['value']['angular_z_rad_s'] if kind=='odom' else sum(a*b for a,b in zip(axis,f['value']['angular_velocity_rad_s']));controls.append(value);last_control=f['header_epoch_ns']
    rows=loadlines(directory/'updates.jsonl.gz');csvrows=list(csv.DictReader((directory/'published.csv').open()));require(len(rows)==len(csvrows),'published/journal coverage')
    frontend=check_frontend(legacy_events,rows,legacy);previous=None;history={};seen_old=set();carried=None;last_marginals=0
    for i,(r,csvrow) in enumerate(zip(rows,csvrows)):
        counts['publications']+=1
        state=r['state_epoch_ns'];deadline=r['availability_cutoff_epoch_ns'];require(type(state) is int and type(deadline) is int and deadline-state==10**9,'integer 1s wait')
        require(csvrow['state_epoch_ns']==str(state) and csvrow['status']==r['status'],'CSV/journal identity')
        require(np.allclose([float(csvrow[k]) for k in ('base_x_m','base_y_m','yaw_rad')],r['pose'],rtol=0,atol=1e-14),'CSV/journal published pose')
        if previous:require(state-previous['state_epoch_ns']==10**9,'full unfiltered grid')
        require(r['graph_states']<=21 and r['scalar_variables']==r['graph_states']*(4 if arm=='F3' else 3),'state/scalar budget')
        if arm!='F0':
            counts['angular_intervals']+=int(r['angular_interval'] is not None)
            if r['angular_interval']:
                edge=r['angular_interval'];require(edge['start_epoch_ns']==previous['state_epoch_ns'] and edge['end_epoch_ns']==state,'angular keyframe binding')
                n,g=check_edge(edge,controls,deadline,config['angular']['max_hold_ns']['value']);counts['segments']+=n;counts['gaps']+=g
            expected=math.radians(config['model']['initial_heading_deg']) if previous is None else previous['pose'][2]+((r['angular_interval']['raw_angle_rad']-previous['bias_rad_s']*(state-previous['state_epoch_ns'])/1e9) if r['angular_interval']['valid'] else 0.)
            require(abs(angle(r['prediction_pose'][2]-expected))<1e-10,'hidden Odom yaw in startup/keyframe/initial guess/fallback')
            require(r['odom_yaw_fallback'] is False,'Odom fallback must be separately reviewed')
            expected_source='declared_external_initial_heading' if previous is None else 'integrated_angular_minus_bias' if r['angular_interval']['valid'] else 'held_yaw_initial_guess_missing_angular'
            require(r['prediction_yaw_source']==expected_source,'yaw provenance label')
            if not r['accepted_graph']:require(np.allclose(r['pose'],r['prediction_pose'],rtol=0,atol=1e-12),'failed solve used candidate or different yaw')
            snap=r['objective_snapshot'];history[r['state_time_s']]=r
            for t,obs,lo in zip(snap['times_s'],snap['observations'],snap['local_odom']):
                require(obs==history[t]['range_medians_m'] and lo==history[t]['local_odom'],'factor input history changed')
            for m in r['marginalization_details']:
                counts['marginalizations']+=1;small=m['linearization_input'];old,next_time=small['times_s']
                require(old not in seen_old,'old factors eliminated twice');seen_old.add(old)
                require(small['observations']==[history[old]['range_medians_m'],{}] and not m['includes_retained_UWB'],'retained UWB double counted')
                require(small['local_odom']==[history[old]['local_odom'],history[next_time]['local_odom']],'old translation changed')
                require(small['intervals']==[history[next_time]['angular_interval']],'old angular/bias factor changed')
                if carried is not None:require(small['prior']==carried,'marginal prior chain lost or repeated')
                carried=m['prior_after'];errors=marginal_check(m,config);marginals.append(dict(state_time_s=r['state_time_s'],old_time_s=old,**errors))
                for key,val in errors.items():
                    if val is not None:maximum[key]=max(maximum[key],val)
            if carried is not None:require(snap['prior']==carried,'current prior differs from carried boundary')
            require(r['marginalizations']==len(seen_old),'marginal count or omitted elimination')
            states=snap['candidate_states'] if snap['candidate_states'] is not None else snap['states'];v=residual(snap,states,config);cost=r['optimizer'].get('optimizer_cost')
            if cost is not None:
                diff=abs(float(v@v/2)-cost);require(diff<1e-7,'independent objective cost');counts['objective_costs']+=1;maximum['objective_cost_abs']=max(maximum['objective_cost_abs'],diff)
            expected_valid=bool(r['accepted_graph'] and r['angular_valid'] and r['numerical_full_rank']);require(expected_valid==r['estimate_valid'],'valid flag hides failures or gaps')
        previous=r
    summary=json.loads((directory/'summary.json').read_text());require(summary['peak_transient_keyframes']<=22,'transient frame bound');require(max(summary['sensor_buffer_peaks'].values())<=512,'sensor buffer budget')
    if arm=='F0':
        final=json.loads((directory/'final_active_graph.json').read_text());snap=dict(times_s=final['times_s'],local_odom=final['local_odom'],observations=final['observations'],prior=dict(point=final['prior_point'],matrix=final['prior_matrix'],offset=final['prior_offset']))
        v=residual(snap,final['states'],config);diff=abs(float(v@v/2)-rows[-1]['optimizer']['optimizer_cost']);require(diff<1e-7,'F0 independent final objective');maximum['objective_cost_abs']=diff;counts['objective_costs']=1
    return dict(arm=arm,status='PASS',counts=dict(counts),maximum_absolute_errors=dict(maximum),independent_frontend=frontend,angular_decisions=dict(rejections),marginal_details=marginals,
        online_graph_Jacobian_or_A_auditor_imported=False,all_marginalizations_checked=arm!='F0',limitations=['F0 marginal algebra not rechecked here: exact archived full publication regression and original prefix test cover F0','B finite differences verify serialized incident factor algebra; they are not a second trajectory solve or calibration','full optimizer warmstart vector is established by frozen-source inspection; latest prediction and actual fallback are checked numerically at every publication'])


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--adapted',type=Path,required=True);p.add_argument('--matrix',type=Path,required=True);p.add_argument('--execution-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();run=start(a.output,'B_independent_A_FGO_readback')
    try:
        protocol=json.loads((HERE/'field_protocol.json').read_text());legacy=json.loads(LEGACY.read_text());index=json.loads((a.adapted/'index.json').read_text());results=[]
        # Prove every A source file is the pinned Git blob, not a drifting branch.
        names=subprocess.check_output(['git','ls-tree','-r','--name-only',protocol['A_commit'],'tools/single_car_imu_fgo'],cwd=a.execution_checkout,text=True).splitlines()
        for name in names:
            blob=subprocess.check_output(['git','show',protocol['A_commit']+':'+name],cwd=a.execution_checkout)
            require(hashlib.sha256(blob).hexdigest()==sha(a.execution_checkout/name),'A frozen Git blob mismatch')
        for entry in index['cases']:
            case=entry['case_id'];flat=loadlines(a.adapted/case/'events.jsonl.gz');rich=loadlines(a.packets/case/'events.jsonl.gz');checked=raw_adapter_check(rich,flat)
            configs=[json.loads((a.adapted/case/(arm+'.json')).read_text()) for arm in protocol['arms']]
            for c in configs:c.pop('arm')
            require(all(c==configs[0] for c in configs),'unmatched parameters between arms')
            for arm in protocol['arms']:
                require(sha(a.adapted/case/'events.jsonl.gz')==entry['A_events_sha256'],'input stream SHA')
                result=inspect_run(a.matrix/(case+'_'+arm),flat,loadlines(a.packets/case/'legacy_events.jsonl.gz'),legacy,a.execution_checkout,entry['config_sha256'][arm])
                result.update(case_id=case,adapted_records_checked=checked);results.append(result)
        save(a.output/'verification.json',dict(status='PASS',checks=results,A_commit=protocol['A_commit'],physical_clock_error_bound_ns=None,strict_physical_branch='BLOCKED',field_accuracy_evaluated=False))
        finish(a.output,run,'DONE');return 0
    except Exception as e:finish(a.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
