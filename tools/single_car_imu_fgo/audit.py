"""Independent serialized FGO evidence reader. No online factor/Jacobian imports."""
import argparse
import bisect
from collections import Counter
import csv
import json
import math
from pathlib import Path
import numpy as np
from io_utils import dump,read_jsonl,sha


def wrap(v):return math.atan2(math.sin(v),math.cos(v))


def residual(snapshot,states,config,arm):
    x=np.asarray(states); n,d=x.shape; times=np.array(snapshot['times_s']); local=np.array(snapshot['local_odom']); prior=snapshot['prior']
    delta=x[0]-prior['point'];delta[2]=wrap(delta[2]); M=np.array(prior['matrix']).reshape(-1,d); pieces=list(M@delta+np.asarray(prior['offset']))
    model=config['model']; p=model['graph_parameters']
    for i,dt in enumerate(np.diff(times)):
        a=local[i,2]; source=local[i+1,:2]-local[i,:2]; observed=np.array([math.cos(a)*source[0]+math.sin(a)*source[1],-math.sin(a)*source[0]+math.cos(a)*source[1]])
        theta=x[i,2]; change=x[i+1,:2]-x[i,:2]; predicted=np.array([math.cos(theta)*change[0]+math.sin(theta)*change[1],-math.sin(theta)*change[0]+math.cos(theta)*change[1]])
        pieces.extend((predicted-observed)/(p['odom_translation_sigma_m']*math.sqrt(dt)))
        if arm=='F0':pieces.append(wrap(x[i+1,2]-x[i,2]-wrap(local[i+1,2]-local[i,2]))/(math.radians(p['odom_yaw_sigma_deg'])*math.sqrt(dt)))
    for i,observations in enumerate(snapshot['observations']):
        theta=x[i,2];lx,ly=model['base_to_antenna_body_xy_m'];point=np.array([x[i,0]+math.cos(theta)*lx-math.sin(theta)*ly,x[i,1]+math.sin(theta)*lx+math.cos(theta)*ly,model['antenna_height_m']])
        for key,raw in sorted(observations.items()):
            distance=float(np.linalg.norm(point-np.array(model['anchors_xyz_m'][key]))); z=(distance-(raw-model['range_bias_m'][key]))/p['range_sigma_m']
            pieces.append(z*math.sqrt(2/(math.sqrt(1+z*z)+1)))
    if arm!='F0':
        g=config['angular']['angle_noise_density_rad_sqrt_s']['value']; b=config['angular']['bias_random_walk_rad_s_sqrt_s']['value']
        for i,(dt,edge) in enumerate(zip(np.diff(times),snapshot['intervals'])):
            if edge['valid']:
                e=wrap(x[i+1,2]-x[i,2]-edge['raw_angle_rad']+(x[i,3]*dt if d==4 else 0.))
                if d==4:
                    s00=g*g*dt+b*b*dt**3/3;s01=-b*b*dt**2/2;s11=b*b*dt
                    l00=math.sqrt(s00);l10=s01/l00;l11=math.sqrt(s11-l10*l10);z=e/l00;pieces.extend([z,(x[i+1,3]-x[i,3]-l10*z)/l11])
                else:pieces.append(e/(g*math.sqrt(dt)))
            elif d==4:pieces.append((x[i+1,3]-x[i,3])/(b*math.sqrt(dt)))
    return np.asarray(pieces)


def numeric_jac(snapshot,states,config,arm):
    x=np.asarray(states,dtype=float);flat=x.ravel(); columns=[]
    for j in range(len(flat)):
        delta=np.eye(len(flat))[j]*1e-6
        columns.append((residual(snapshot,(flat+delta).reshape(x.shape),config,arm)-residual(snapshot,(flat-delta).reshape(x.shape),config,arm))/2e-6)
    return np.column_stack(columns)


def audit(run_dir,input_path=None,stride=13):
    root=Path(run_dir);meta=json.loads((root/'run.json').read_text());c=json.loads((root/'config.json').read_text());arm=meta['arm']; errors=[];counts=Counter(); maximum=Counter()
    def check(ok,text):
        if not ok and len(errors)<40:errors.append(text)
    for f in meta['outputs']:check((root/f['relative_path']).is_file() and sha(root/f['relative_path'])==f['sha256'],'output SHA '+f['relative_path'])
    if input_path:check(sha(input_path)==meta['input']['sha256'],'actual input SHA')
    identity={};angular=[];odom_all=[];uwb_all=[]
    for e in read_jsonl(root/'input_decisions.jsonl.gz'):
        row=e['input'];key=(row['source_file_sha256'],row['record_index'],row['topic']) if 'source_file_sha256' in row else None
        if key:identity[key]=row
        for k in ('receive_epoch_ns','record_index'):check(type(row[k]) is int,'noninteger input')
        if row['kind'] in ('odom','uwb'):
            clock=c['clock_maps'][row['kind']]['value'];v=(row['header_epoch_ns']-clock['source_origin_ns'])*clock['rate_numerator'];source=clock['destination_origin_ns']+(1 if v>=0 else -1)*((abs(v)+clock['rate_denominator']//2)//clock['rate_denominator'])
            check(source==e['mapped_identity']['mapped_header_epoch_ns'],'original input mapped identity differs')
            if row['kind']=='odom':
                value=np.array(row['value']['pose'],dtype=float)
                if odom_all:value[2]=odom_all[-1][2][2]+wrap(value[2]-odom_all[-1][2][2])
                odom_all.append((source,row['receive_epoch_ns'],value))
            else:uwb_all.append((source,row['receive_epoch_ns'],row['value']))
        if e['angular_status']=='angular_control_accepted':angular.append((e['mapped_identity']['mapped_header_epoch_ns'],row['receive_epoch_ns'],key))
    previous=None;previous_bias=0.;previous_local=None;previous_epoch=None
    for index,row in enumerate(read_jsonl(root/'updates.jsonl.gz')):
        counts['publications']+=1;state=row['state_epoch_ns'];cutoff=row['availability_cutoff_epoch_ns']
        check(type(state) is int and cutoff-state==1_000_000_000,'exact1s wait');check(row['graph_states']<=21,'window >21 frames')
        check(row.get('dependency_receipt_max_s') is None or row['dependency_receipt_max_s']<=row['availability_cutoff_s']+1e-12,'future original dependency')
        eligible_odom=[r for r in odom_all if r[1]<=cutoff];stamps=[r[0] for r in eligible_odom];bracket=bisect.bisect_left(stamps,state);local=None;receipt=None
        if bracket<len(stamps) and stamps[bracket]==state:local=eligible_odom[bracket][2];receipt=eligible_odom[bracket][1]
        elif 0<bracket<len(stamps):
            left,right=eligible_odom[bracket-1],eligible_odom[bracket];fraction=(state-left[0])/(right[0]-left[0]);local=left[2]+fraction*(right[2]-left[2]);receipt=max(left[1],right[1])
        if local is None:check(row['pose'] is None and row['status']=='missing_odom_bracket','missing bracket silently extrapolated')
        else:
            counts['original_frontend_checks']+=1;check(np.max(np.abs(local-row['local_odom']))<1e-10,'common Odom interpolation differs')
            grouped={};receipts=[receipt];model=c['model'];origin=meta['epoch_origin_ns']
            for source,received,values in uwb_all:
                if received>cutoff or abs((source-origin)/1e9-row['state_time_s'])>c['replay']['range_bin_half_width_s']:continue
                valid={k:float(v) for k,v in values.items() if k in model['anchors_xyz_m'] and math.isfinite(v) and v>0 and v-model['range_bias_m'][k]>0}
                for key,value in valid.items():grouped.setdefault(key,[]).append(value)
                if valid:receipts.append(received)
            medians={k:float(np.median(v)) for k,v in grouped.items() if len(v)>=c['replay']['minimum_samples_per_link']}
            check(medians==row['range_medians_m'],'raw range median/P1 input differs');check({k:len(grouped.get(k,[])) for k in model['anchors_xyz_m']}==row['range_sample_counts'],'range support counts differ')
            recorded=origin+round(row['dependency_receipt_max_s']*1e9);check(max(receipts)<=recorded<=cutoff,'Odom/UWB exact receive dependency not available')
        edge=row.get('angular_interval')
        if edge:
            counts['angular_intervals']+=1; total=0;cursor=edge['start_epoch_ns'];pieces=sorted([(s['start_epoch_ns'],s['end_epoch_ns'],'segment',s) for s in edge['segments']]+[(g['start_epoch_ns'],g['end_epoch_ns'],'gap',g) for g in edge['gaps']])
            check(edge['end_epoch_ns']==state,'integration end/state mismatch');check(edge['dt_ns']==edge['end_epoch_ns']-edge['start_epoch_ns'],'dt mismatch')
            for a,b,kind,s in pieces:
                check(a==cursor and b>a,'hole/overlap in partition');cursor=b
                if kind=='gap':counts['gaps']+=1;continue
                counts['segments']+=1;dep=s['dependency'];key=(dep['source_file_sha256'],dep['record_index'],dep['topic']);check(key in identity,'dependency absent from serialized input')
                check(dep['receive_epoch_ns']<=cutoff,'angular dependency arrived after cutoff');check(dep['mapped_header_epoch_ns']<=a,'future endpoint used backwards')
                check(b-dep['mapped_header_epoch_ns']<=c['angular']['max_hold_ns']['value'],'unbounded angular hold')
                original=identity.get(key)
                if original:
                    check(all(original[k]==dep[k] for k in ('header_epoch_ns','receive_epoch_ns')),'dependency raw identity differs')
                    clock=c['clock_maps']['odom' if arm=='F1' else 'imu']['value'];v=(original['header_epoch_ns']-clock['source_origin_ns'])*clock['rate_numerator'];mapped=clock['destination_origin_ns']+(1 if v>=0 else -1)*((abs(v)+clock['rate_denominator']//2)//clock['rate_denominator'])
                    check(mapped==dep['mapped_header_epoch_ns'],'mapped ns mismatch')
                    rate=float(original['value']['angular_z_rad_s']) if arm=='F1' else float(np.asarray(original['value']['angular_velocity_rad_s'])@c['angular']['body_z_in_imu_frame']['value'])
                    check(abs(rate-s['rate_rad_s'])<1e-12,'axis/rate mismatch')
                    eligible=[item for item in angular if item[0]<=a and item[1]<=cutoff]
                    check(bool(eligible) and max(eligible,key=lambda v:v[0])[2]==key,'latest eligible source not used')
                total+=s['rate_rad_s']*(b-a)/1e9;check(abs(s['angle_rad']-s['rate_rad_s']*(b-a)/1e9)<1e-12,'angle segment arithmetic')
            check(cursor==edge['end_epoch_ns'],'partition incomplete');check(edge['valid']==(not edge['gaps']),'invalid coverage flag');check(abs(total-edge['partial_angle_rad'])<1e-10,'partial integral mismatch')
            if edge['valid']:check(abs(total-edge['raw_angle_rad'])<1e-10,'complete integral mismatch')
            else:check(edge['raw_angle_rad'] is None and not row['estimate_valid'],'gap represented as valid angle')
        if arm!='F0' and row['pose'] is not None:
            check(not row['odom_yaw_fallback'],'unexpected odom yaw fallback')
            if previous is None:expected=math.radians(c['model']['initial_heading_deg'])
            else:expected=previous[2]+(edge['raw_angle_rad']-previous_bias*edge['dt_ns']/1e9 if edge['valid'] else 0.)
            check(abs(wrap(row['prediction_pose'][2]-expected))<1e-10,'prediction/start/fallback has hidden yaw dependency')
            if not row['accepted_graph']:check(np.max(np.abs(np.array(row['pose'])-row['prediction_pose']))<1e-12,'failed solver accepted candidate')
            previous=row['pose'];previous_bias=row['bias_rad_s'];previous_local=row['local_odom'];previous_epoch=state
            snapshot=row['objective_snapshot'];x=snapshot['candidate_states'] if snapshot['candidate_states'] is not None else snapshot['states'];r=residual(snapshot,x,c,arm)
            check(len(x)*len(x[0])==row['scalar_variables'],'scalar count incorrect')
            if row['optimizer'].get('optimizer_cost') is not None:
                counts['objective_cost_checks']+=1;err=abs(float(r@r/2)-row['optimizer']['optimizer_cost']);maximum['objective_cost_abs']=max(maximum['objective_cost_abs'],err);check(err<1e-7,'independent objective cost mismatch')
            for marginal in row['marginalization_details']:
                counts['marginalizations']+=1;check(not marginal['includes_retained_UWB'],'retained factors double-counted')
                if counts['marginalizations']%stride!=0:continue
                counts['sampled_marginalizations']+=1;snap=marginal['linearization_input'];x=np.array(snap['states']);r0=residual(snap,x,c,arm);J=numeric_jac(snap,x,c,arm);d=x.shape[1];old=J[:,:d];boundary=J[:,d:]
                proj=boundary-old@np.linalg.lstsq(old,boundary,rcond=None)[0];rr=r0-old@np.linalg.lstsq(old,r0,rcond=None)[0]
                prior=marginal['prior_after'];M=np.array(prior['matrix']).reshape(-1,d);off=np.array(prior['offset']);h_err=float(np.max(np.abs(M.T@M-proj.T@proj)));g_err=float(np.max(np.abs(M.T@off-proj.T@rr)))
                maximum['marginal_information_abs']=max(maximum['marginal_information_abs'],h_err);maximum['marginal_gradient_abs']=max(maximum['marginal_gradient_abs'],g_err)
                check(np.allclose(M.T@M,proj.T@proj,atol=.03,rtol=1e-5),'marginal information finite-difference mismatch')
                check(np.allclose(M.T@off,proj.T@rr,atol=.001,rtol=1e-5),'marginal affine gradient mismatch')
                check(abs(float(rr@rr-off@off)-marginal['eliminated_constant'])<.001,'marginal constant mismatch')
    final=json.loads((root/'final_active_graph.json').read_text());summary=json.loads((root/'summary.json').read_text())
    check(summary['peak_transient_keyframes']<=22 and summary['peak_solve_scalar_variables']<=(84 if arm=='F3' else 63),'bounded graph violation')
    check(max(summary['sensor_buffer_peaks'].values())<=c['frontend']['max_sensor_samples_per_stream'],'buffer budget')
    if arm=='F0' and final['states']:
        rows=list(read_jsonl(root/'updates.jsonl.gz'));last=rows[-1]
        if last['accepted_graph']:
            snap=dict(times_s=final['times_s'],local_odom=final['local_odom'],observations=final['observations'],prior=dict(point=final['prior_point'],matrix=final['prior_matrix'],offset=final['prior_offset']))
            r=residual(snap,final['states'],c,arm);err=abs(float(r@r/2)-last['optimizer']['optimizer_cost']);maximum['final_F0_cost_abs']=err;check(err<1e-7,'independent F0 final objective mismatch');counts['objective_cost_checks']+=1
    return dict(status='PASS' if not errors else 'FAIL',counts=dict(counts),maximum_absolute_errors=dict(maximum),errors=errors,
                marginalization_sampling_stride=stride,online_optimizer_imported=False,field_accuracy_evaluated=False,
                limitations=['cost and finite-difference marginalized system agreement are numerical checks, not sensor calibration','F0 independent cost only at final accepted graph; F0 full regression is separate'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--input',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=audit(a.run,a.input);dump(a.output,r);print(json.dumps(r));raise SystemExit(0 if r['status']=='PASS' else 1)
