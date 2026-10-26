"""Qualify video/ROS timing using image motion and original odom events only."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment
import common
import time_events


def merge_intervals(items,gap=1.0,min_duration=1.5):
    result=[]
    for item in items:
        start,end=item['start_s'],item['end_s']
        if result and start-result[-1]['end_s']<=gap:result[-1]['end_s']=end
        else:result.append(dict(start_s=start,end_s=end))
    return [x for x in result if x['end_s']-x['start_s']>=min_duration]


def boundaries(intervals,vehicle):
    return [dict(vehicle_id=vehicle,kind=kind,time_s=item[key])
        for item in intervals for kind,key in [('motion_start','start_s'),('motion_end','end_s')]]


def image_motion(rows):
    t=np.array([float(r['video_time_s']) for r in rows]);xy=np.full((len(rows),2),np.nan)
    for i,r in enumerate(rows):
        if r['observation_status'] in ('decoded','tracked'):
            q=np.array([[float(r[f'corner{k}_x_px']),float(r[f'corner{k}_y_px'])] for k in range(4)])
            xy[i]=q.mean(axis=0)
    speed=np.full(len(t),np.nan)
    if len(t)>1:
        dt=np.diff(t);valid=np.isfinite(xy[:-1]).all(axis=1)&np.isfinite(xy[1:]).all(axis=1)&(dt>0)&(dt<0.8)
        indices=np.flatnonzero(valid)+1
        speed[indices]=np.linalg.norm(np.diff(xy,axis=0)[valid],axis=1)/dt[valid]
    finite=speed[np.isfinite(speed)]
    if not len(finite):return dict(valid_fraction=0.,threshold_px_s=None,intervals=[],events=[])
    low=np.sort(finite)[:max(3,int(.3*len(finite)))]
    med=float(np.median(low));mad=float(np.median(abs(low-med)))
    threshold=max(3.,med+6*1.4826*mad)
    smooth=speed.copy()
    for i in range(1,len(t)-1):
        vals=speed[i-1:i+2];vals=vals[np.isfinite(vals)]
        if len(vals)==3:smooth[i]=np.median(vals)
    runs=merge_intervals(time_events.intervals(t,np.isfinite(smooth)&(smooth>threshold),
        min_duration=1.,bridge_gap=.8),gap=1.0,min_duration=1.5)
    events=[]
    for run in runs:
        # Becoming visible is not evidence of a motion onset, and losing a
        # marker is not evidence of a physical stop.
        before=(t>=run['start_s']-1.5)&(t<=run['start_s']-.5)&np.isfinite(smooth)
        after=(t>=run['end_s']+.5)&(t<=run['end_s']+1.5)&np.isfinite(smooth)
        start_guard=bool(before.sum()>=2 and np.median(smooth[before])<threshold)
        end_guard=bool(after.sum()>=2 and np.median(smooth[after])<threshold)
        run['start_has_stationary_observation']=start_guard
        run['end_has_stationary_observation']=end_guard
        if start_guard:events.append(dict(vehicle_id=rows[0]['vehicle_id'],kind='motion_start',time_s=run['start_s']))
        if end_guard:events.append(dict(vehicle_id=rows[0]['vehicle_id'],kind='motion_end',time_s=run['end_s']))
    return dict(valid_fraction=float(np.isfinite(xy).all(axis=1).mean()),threshold_px_s=threshold,
        intervals=runs,events=events)


def pair_at_offset(video,ros,offset,tolerance=2.):
    if not video or not ros:return []
    cost=np.full((len(video),len(ros)),1e6)
    for i,v in enumerate(video):
        for j,r in enumerate(ros):
            if v['vehicle_id']==r['vehicle_id'] and v['kind']==r['kind']:
                cost[i,j]=abs(v['time_s']+offset-r['time_s'])
    vi,ri=linear_sum_assignment(cost)
    return [(int(i),int(j),float(cost[i,j])) for i,j in zip(vi,ri) if cost[i,j]<=tolerance]


def align(video,ros):
    options=[]
    for v in video:
        for r in ros:
            if (v['vehicle_id'],v['kind'])==(r['vehicle_id'],r['kind']):
                b=r['time_s']-v['time_s'];pairs=pair_at_offset(video,ros,b)
                options.append((len(pairs),-sum(p[2] for p in pairs),b,pairs))
    if not options:return dict(status='pending',model=None,reason='No matchable image/odom motion events')
    _,_,b,pairs=max(options,key=lambda x:x[:2])
    if len(pairs)<2:
        alternatives=[]
        for count,negative_cost,offset,match in options:
            if count==len(pairs) and not any(abs(offset-x['b_relative_s'])<.25 for x in alternatives):
                alternatives.append(dict(a=1.,b_relative_s=float(offset),clock_scale_status='assumed_only',
                    pairing=[dict(video_event=video[i],odom_event=ros[j]) for i,j,_ in match]))
        return dict(status='pending_single_event_stage_ambiguity',model=None,candidate_model=None,
            candidate_offset_family=alternatives,accepted_for_continuous_reference=False,
            reason='One observed boundary cannot identify which repeated movement stage it corresponds to',
            uncertainty=dict(total_bound_s=None,clock_scale=None),
            unmatched_video_events=len(video)-len(pairs),unmatched_odom_events=len(ros)-len(pairs))
    pairs=sorted(pairs,key=lambda p:video[p[0]]['time_s'])
    matched=[dict(vehicle_id=video[i]['vehicle_id'],kind=video[i]['kind'],video_s=video[i]['time_s'],
        ros_relative_s=ros[j]['time_s'],initial_abs_residual_s=res) for i,j,res in pairs]
    candidate=dict(a=1.,b_relative_s=float(np.median([x['ros_relative_s']-x['video_s'] for x in matched])),
        clock_scale_status='assumed_unity_not_measured')
    if len(matched)>=3 and np.ptp([x['video_s'] for x in matched])>=10:
        fit=time_events.fit_events([x['video_s'] for x in matched],[x['ros_relative_s'] for x in matched],np.full(len(matched),.75))
        candidate=fit|dict(clock_scale_status='fitted_from_events_not_independent_clock_calibration')
    candidate['events']=matched
    candidate['plausible_clock_scale']=bool(.98<=candidate['a']<=1.02)
    if 'residual_s' not in candidate:
        residual=[x['ros_relative_s']-(candidate['a']*x['video_s']+candidate['b_relative_s']) for x in matched]
        candidate['residual_s']=residual;candidate['max_abs_residual_s']=float(max(map(abs,residual)))
    return dict(status='event_alignment_candidate_not_accepted',model=None,candidate_model=candidate,
        accepted_for_continuous_reference=False,
        uncertainty=dict(video_sampling_interval_s=.5,odom_displacement_window_s=.25,
            visual_median_filter_span_s=1.,stationary_boundary_guard_s=1.,
            event_fit_assumed_sigma_s=.75,total_bound_s=None,
            unbounded_components=['Visual/odom physical-onset difference','Unmeasured timestamp/host latency',
                'Feature/board motion and visibility-dependent event selection']),
        unmatched_video_events=len(video)-len(pairs),unmatched_odom_events=len(ros)-len(pairs))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observations',type=Path,required=True);p.add_argument('--odom-events',type=Path,required=True)
    p.add_argument('--media',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    odom={e['experiment_id']:e for e in json.loads(a.odom_events.read_text(encoding='utf-8'))['experiments']}
    maps=[]
    for path in sorted(a.observations.glob('T*/marker_observations.csv')):
        if not path.with_name('observation_summary.json').is_file():continue
        rows=list(csv.DictReader(path.open(encoding='utf-8')));exp=rows[0]['experiment_id']
        if exp not in odom:continue
        video_events=[];ros_events=[];motions={}
        for v in ['car1','car2']:
            subset=[r for r in rows if r['vehicle_id']==v]
            motions[v]=image_motion(subset);video_events+=motions[v]['events']
            runs=merge_intervals(odom[exp]['vehicles'][v]['translational_intervals'])
            ros_events+=boundaries(runs,v)
        result=align(video_events,ros_events)
        result.update(experiment_id=exp,video_sha256=rows[0]['video_sha256'],mapping_id=exp+'_pts_to_receive_events_v1',
            source_clock='original_video_PTS',destination_clock='bag_receive_ROS_record_clock',
            destination_origin_epoch_ns=odom[exp]['receive_origin_epoch_ns'],
            mapping_formula='receive_epoch_ns = destination_origin_epoch_ns + round(1e9*(a*video_time_s+b_relative_s))',
            original_odom_only=True,fusion_estimates_used=False,video_motion=motions,
            video_events=video_events,odom_events=ros_events)
        candidate=result.get('candidate_model')
        if candidate:
            span=[min(float(r['video_time_s']) for r in rows),max(float(r['video_time_s']) for r in rows)]
            mapped=[candidate['a']*t+candidate['b_relative_s'] for t in span]
            result['candidate_video_interval_s']=span;result['candidate_mapped_ros_relative_interval_s']=mapped
            result['nominal_motion_span_covered']=bool(ros_events and min(e['time_s'] for e in ros_events)>=mapped[0] and max(e['time_s'] for e in ros_events)<=mapped[1])
            result['coverage_caveat']='Temporal-span coverage is not continuous marker visibility or spatial validation'
        maps.append(result)
    common.write_json(a.output/'time_mapping.json',dict(schema_version=1,mappings=maps,
        policy='Candidates retained; no fusion trajectory, filename clock or nominal sleep used as synchronization evidence'))


if __name__=='__main__':main()
