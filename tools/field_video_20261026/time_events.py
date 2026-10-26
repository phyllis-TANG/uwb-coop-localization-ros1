"""Read original odometry/command timing and fit explicitly qualified event mappings."""
import argparse
import csv
import json
from pathlib import Path
import sys
import numpy as np
import common
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'field_20261024_25'))
from bag_decoder import load_bag,Decoder


def yaw(q):
    return float(np.arctan2(2*(q['w']*q['z']+q['x']*q['y']),1-2*(q['y']**2+q['z']**2)))


def intervals(times,active,min_duration=0.5,bridge_gap=0.5):
    """Intervals bracketed by neighbouring samples; never inferred from theoretical sleep."""
    t=np.asarray(times,float);a=np.asarray(active,bool)
    if len(t)!=len(a):raise ValueError('length mismatch')
    runs=[]
    for i in np.flatnonzero(a):
        if not runs or t[i]-t[runs[-1][-1]]>bridge_gap:runs.append([i])
        else:runs[-1].append(i)
    result=[]
    for run in runs:
        first,last=run[0],run[-1]
        if t[last]-t[first]<min_duration:continue
        result.append(dict(start_s=float(t[first]),end_s=float(t[last]),
            start_bracket_s=[float(t[max(0,first-1)]),float(t[first])],
            end_bracket_s=[float(t[last]),float(t[min(len(t)-1,last+1)])]))
    return result


def fit_events(video_s,ros_relative_s,sigma_s):
    x=np.asarray(video_s,float);y=np.asarray(ros_relative_s,float);sigma=np.asarray(sigma_s,float)
    if len(x)<3 or len(x)!=len(y) or len(x)!=len(sigma):
        raise ValueError('At least three independently identified paired events are required')
    if not(np.isfinite(x).all() and np.isfinite(y).all() and np.all(sigma>0)):
        raise ValueError('invalid event input')
    if np.ptp(x)<10:raise ValueError('Insufficient event time span')
    X=np.c_[x,np.ones(len(x))];w=1/sigma**2
    beta=np.linalg.lstsq(X*np.sqrt(w[:,None]),y*np.sqrt(w),rcond=None)[0]
    residual=y-X@beta
    covariance=np.linalg.inv(X.T@(w[:,None]*X))
    return dict(a=float(beta[0]),b_relative_s=float(beta[1]),residual_s=residual.tolist(),
        rms_s=float(np.sqrt(np.mean(residual**2))),max_abs_residual_s=float(abs(residual).max()),
        formal_parameter_covariance=covariance.tolist(),
        qualification='Event-based candidate; uncertainty excludes unmeasured camera/host latency unless separately bounded')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',required=True,type=Path);p.add_argument('--manifest',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    manifest=json.loads(a.manifest.read_text(encoding='utf-8'));summaries=[]
    for item in manifest['formal_bags']:
        path=a.data_root/'extracted'/'bags'/item['relative_path']
        if common.sha256(path)!=item['sha256']:raise ValueError('Bag identity mismatch')
        connections,messages=load_bag(path);decoders={}
        origin=min(t for _,t,_ in messages);vehicles={v:dict(odom=[],commands=[]) for v in ['car1','car2']}
        for record_index,(cid,t,raw) in enumerate(messages):
            connection=connections[cid];topic=connection['topic']
            if not any(topic==f'/{v}/{kind}' for v in vehicles for kind in ['odom','cmd_vel']):continue
            if cid not in decoders:decoders[cid]=Decoder(connection['type'],connection['definition'])
            msg=decoders[cid].decode(raw,connection['type']);v=topic.split('/')[1]
            row=dict(record_index=record_index,receive_epoch_ns=str(t),receive_relative_s=(t-origin)/1e9)
            if topic.endswith('/odom'):
                stamp=msg['header']['stamp'];pose=msg['pose']['pose'];position=pose['position']
                row.update(header_epoch_ns=str(stamp['secs']*10**9+stamp['nsecs']),
                    x_m=position['x'],y_m=position['y'],yaw_rad=yaw(pose['orientation']),
                    frame_id=msg['header']['frame_id'],child_frame_id=msg['child_frame_id'])
                vehicles[v]['odom'].append(row)
            else:
                row.update(linear_x=msg['linear']['x'],angular_z=msg['angular']['z'])
                vehicles[v]['commands'].append(row)
        summary=dict(experiment_id=item['id'],bag_sha256=item['sha256'],
            receive_origin_epoch_ns=str(origin),clock='bag_receive_ROS_record_clock',vehicles={})
        for v,data in vehicles.items():
            rows=data['odom'];t=np.array([x['receive_relative_s'] for x in rows]);xy=np.array([[x['x_m'],x['y_m']] for x in rows]);ang=np.unwrap([x['yaw_rad'] for x in rows])
            # Robust 0.25s displacement suppresses quantization; endpoints stay in observed arrival clock.
            index=np.searchsorted(t,t-0.25);index=np.minimum(index,np.arange(len(t)))
            delta=t-t[index];speed=np.divide(np.linalg.norm(xy-xy[index],axis=1),delta,out=np.zeros(len(t)),where=delta>0)
            turn=np.divide(abs(ang-ang[index]),delta,out=np.zeros(len(t)),where=delta>0)
            c=data['commands'];ct=[x['receive_relative_s'] for x in c]
            summary['vehicles'][v]=dict(odom_samples=len(rows),command_samples=len(c),
                translational_intervals=intervals(t,speed>0.005),turning_intervals=intervals(t,turn>0.03),
                nonzero_linear_command_intervals=intervals(ct,[abs(x['linear_x'])>1e-6 for x in c]),
                nonzero_angular_command_intervals=intervals(ct,[abs(x['angular_z'])>1e-6 for x in c]),
                maximum_speed_m_s=float(speed.max()),maximum_abs_yaw_rate_rad_s=float(turn.max()))
            for kind,records in data.items():
                if not records:continue
                with (a.output/(item['id']+'_'+v+'_'+kind+'.csv')).open('x',newline='',encoding='utf-8') as f:
                    w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
        summaries.append(summary)
    common.write_json(a.output/'odom_events.json',dict(schema_version=1,
        configuration=dict(displacement_window_s=0.25,speed_threshold_m_s=0.005,yaw_rate_threshold_rad_s=0.03,
            interval_min_duration_s=0.5,interval_bridge_gap_s=0.5),experiments=summaries,
        limitations=['Odom is used only for timing; never for fitting visual room coordinates',
            'Receive and measurement timestamps are not proven simultaneous',
            'No video mapping is accepted until events are independently matched']))


if __name__=='__main__':main()
