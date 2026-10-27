"""Independent source/numerical readback of serialized evidence, not live objects.

The verifier reimplements integration/H/Joseph checks rather than calling filter
transition/range_geometry. It checks all provenance, samples numerical matrices
at a predeclared stride to bound cost, and never feeds truth back to replay.
"""
import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path
import numpy as np
from io_utils import dump, read_jsonl, sha


def circular(a): return math.atan2(math.sin(a),math.cos(a))


def integrate(x,v,r,dt,estimate):
    out=np.array(x,dtype=float); rate=r-x[3] if estimate else r; h=x[2]; phi=rate*dt
    # Stable independent midpoint/sinc form, also used at zero rate.
    scale=float(np.sinc(phi/(2*math.pi)))
    c,s=math.cos(h+phi/2),math.sin(h+phi/2)
    out[0]+=dt*scale*(c*v[0]-s*v[1]); out[1]+=dt*scale*(s*v[0]+c*v[1]); out[2]=circular(h+phi)
    if not estimate: out[3]=0.
    return out


def predicted_range(x,config,car,target):
    def point(name):
        i=0 if name=='car1' else 4; theta=x[i+2]; cc=config['vehicles'][name]
        arm=cc.get('antenna_body_xyz_m',{}).get('value')
        lever=cc.get('antenna_body_xy_m',{}).get('value',arm[:2] if arm else None)
        height=cc.get('antenna_height_m',{}).get('value',cc['base_height_m'].get('value',0)+(arm[2] if arm else 0))
        return np.array([x[i]+math.cos(theta)*lever[0]-math.sin(theta)*lever[1],x[i+1]+math.sin(theta)*lever[0]+math.cos(theta)*lever[1],height])
    own=point(car)
    other=point('car2' if car=='car1' else 'car1') if target in ('node_0','node_1') else config['anchors_xyz_m']['value'][target]
    return float(np.linalg.norm(own-other))


def audit(run_dir, input_path=None, stride=113):
    root=Path(run_dir); metadata=json.loads((root/'run.json').read_text()); config=json.loads((root/'config.json').read_text())
    errors=[]; counts=Counter(); maximums=Counter(); input_identity={}
    if input_path:
        if sha(input_path)!=metadata['inputs'][0]['sha256']: errors.append('input SHA mismatch')
        for event in read_jsonl(input_path):
            r=event['row']; key=(event['kind'],r['vehicle_id'],r['source_file_sha256'],r['record_index'],r.get('link_index',0)); input_identity[key]=r
    for entry in metadata['outputs']:
        p=root/entry['relative_path']
        if not p.is_file() or sha(p)!=entry['sha256']: errors.append('output SHA '+str(p))
    estimate=config.get('imu_prototype',{}).get('motion_mode')=='body_imu_bias'
    def check(ok,text):
        if not ok and len(errors)<30: errors.append(text)
    for record in read_jsonl(root/'decisions.jsonl.gz'):
        counts[record['record_type']]+=1
        if record['record_type']=='event_decision':
            row=record['input']['row']; detail=record['decision']; cutoff=record['admitted_at_publication_ns']
            check(type(row['header_epoch_ns']) is int and type(row['receive_epoch_ns']) is int,'noninteger input epoch')
            check(row['receive_epoch_ns']<=cutoff,'input beyond publication cutoff')
            for segment in detail.get('propagations',[]):
                counts['segments']+=1; start=segment['from_epoch_ns']; end=segment['to_epoch_ns']; dt=(end-start)/1e9
                check(dt>=0 and end<=row['receive_epoch_ns'],'future/negative propagation')
                for control,key_kind in [('velocity','odom'),('angular',segment['rate_source'] if segment['rate_source']=='imu' else 'odom')]:
                    identity=segment[control]; check(identity['sample_epoch_ns']<=start,'future control used backwards')
                    check(identity['receive_epoch_ns']<=row['receive_epoch_ns'],'not-yet-arrived control')
                    if input_path:
                        key=(key_kind,identity['vehicle_id'],identity['source_file_sha256'],identity['record_index'],0)
                        check(key in input_identity,'used control missing from input')
                        if key in input_identity:
                            original=input_identity[key]
                            check(all(original[k]==identity[k] for k in ('header_epoch_ns','receive_epoch_ns')),'used control identity differs')
                got=integrate(segment['state_before_4d'],segment['body_velocity_m_s'],segment['observed_rate_rad_s'],dt,estimate)
                diff=got-np.array(segment['state_after_4d']); diff[2]=circular(diff[2]); maximums['mean_abs']=max(maximums['mean_abs'],float(np.max(np.abs(diff))))
                check(np.max(np.abs(diff))<1e-9,'independent mean readback')
                if counts['segments']%stride==0:
                    counts['sampled_F_Q']+=1; x=np.array(segment['state_before_4d']); F=np.array(segment['jacobian_4x4']); num=np.zeros((4,4))
                    for j in range(4):
                        d=np.eye(4)[j]*1e-6; delta=integrate(x+d,segment['body_velocity_m_s'],segment['observed_rate_rad_s'],dt,estimate)-integrate(x-d,segment['body_velocity_m_s'],segment['observed_rate_rad_s'],dt,estimate); delta[2]=circular(delta[2]); num[:,j]=delta/2e-6
                    err=float(np.max(np.abs(F-num))); maximums['F_abs']=max(maximums['F_abs'],err); check(err<5e-7,'independent F finite difference')
                    Q=np.array(segment['Q_4x4']); check(np.linalg.eigvalsh(Q).min()>=-1e-12,'Q not PSD')
                    p=config['imu_prototype']['parameters']; q=p['bias_random_walk']['value']**2 if estimate else 0.
                    check(abs(Q[3,3]-q*dt)<1e-13 and abs(Q[2,3]+q*dt**2/2)<1e-13,'bias Q units/cross term')
            for gap in detail.get('gap_reanchors',[]):
                counts['gap_reanchors']+=1; check(gap['missing_motion_not_integrated'] and gap['pose_mean_held'],'silent gap integration')
                check(gap['to_epoch_ns']<=row['receive_epoch_ns'] and gap['unknown_duration_ns']>0,'invalid recovery interval')
            update=detail.get('range_update')
            if update:
                counts['range_updates']+=1
                if counts['range_updates']%stride==0:
                    counts['sampled_H_Joseph']+=1; x=np.array(update['prior_state_8d']); P=np.array(update['prior_covariance_8x8']); H=np.array(update['H_8d']); K=np.array(update['gain_8d']); R=update['variance_m2']
                    car=row['vehicle_id']; target=row['target_id']; expected=predicted_range(x,config,car,target)
                    check(abs(expected-update['expected_range_m'])<1e-9,'range projection mismatch')
                    num=[]
                    for j in range(8):
                        d=np.eye(8)[j]*1e-6; num.append((predicted_range(x+d,config,car,target)-predicted_range(x-d,config,car,target))/2e-6)
                    check(np.max(np.abs(H-num))<5e-7,'independent H finite difference')
                    trueK=P@H/(H@P@H+R); check(np.max(np.abs(K-trueK))<1e-10,'range gain mismatch')
                    J=np.eye(8)-np.outer(K,H); posterior=J@P@J.T+np.outer(K,K)*R
                    check(np.max(np.abs(posterior-update['posterior_covariance_8x8']))<1e-10,'Joseph covariance mismatch')
        else:
            cutoff=record['publish_receive_epoch_ns']
            for method,details in record['methods'].items():
                state=details['filter_state']; P=state.get('augmented_covariance_8x8')
                if P is not None:
                    P=np.array(P); check(np.linalg.eigvalsh(P).min()>=-1e-9,'posterior not PSD')
                    if method=='independent': check(np.max(np.abs(P[:4,4:]))<1e-14,'independent cross contamination')
                for car,snapshot in details['vehicles'].items():
                    for field in ('last_imu','last_velocity'):
                        item=snapshot.get(field)
                        if item: check(item['receive_epoch_ns']<=cutoff and item['sample_epoch_ns']<=snapshot['state_epoch_ns'],'publication provenance future')
    with (root/'estimate.csv').open() as stream:
        for row in csv.DictReader(stream):
            counts['estimate_rows']+=1
            if row['state_epoch_ns']: check(int(row['state_epoch_ns'])<=int(row['publish_receive_epoch_ns']),'CSV state in future')
            if row['pose_covariance']: check(np.shape(json.loads(row['pose_covariance']))==(3,3),'pose marginal not3x3')
    return dict(status='PASS' if not errors else 'FAIL', counts=dict(counts), maximum_absolute_errors=dict(maximums), errors=errors,
                numerical_stride=stride, independent_of_live_filter=True, scope='serialized source/numerical readback, no field accuracy or statistical calibration')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--run',type=Path,required=True); p.add_argument('--input',type=Path); p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); result=audit(a.run,a.input); dump(a.output,result); print(json.dumps(result)); raise SystemExit(0 if result['status']=='PASS' else 1)
