"""Explicit manual-quadrilateral LK supplement, for motion timing only, never pose truth."""
import argparse
import csv
import json
from pathlib import Path
import av
import cv2
import numpy as np
import common
import observations


def cropped_features(gray,corners):
    lo=np.floor(corners.min(axis=0)-8).astype(int);hi=np.ceil(corners.max(axis=0)+9).astype(int)
    x0,y0=np.maximum(lo,0);x1,y1=np.minimum(hi,[gray.shape[1],gray.shape[0]])
    origin=np.array([x0,y0],np.float32)
    points=observations.features(gray[y0:y1,x0:x1],corners-origin)
    return None if points is None else points+origin


def cropped_track(previous,current,points,corners,config):
    pad=max(128,int(np.ptp(corners,axis=0).max()*.75))
    lo=np.floor(corners.min(axis=0)-pad).astype(int);hi=np.ceil(corners.max(axis=0)+pad).astype(int)
    x0,y0=np.maximum(lo,0);x1,y1=np.minimum(hi,[current.shape[1],current.shape[0]])
    origin=np.array([x0,y0],np.float32)
    local_points=None if points is None else points-origin
    q,diagnostic=observations.track(previous[y0:y1,x0:x1],current[y0:y1,x0:x1],
        local_points,corners-origin,config)
    return (None if q is None else q+origin),diagnostic


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--video',type=Path,required=True);p.add_argument('--seed',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--experiment',default='')
    p.add_argument('--crop-flow',action='store_true',help='Compute LK in bounded marker ROI; timing-only v2')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    seed=json.loads(a.seed.read_text(encoding='utf-8'));digest=common.sha256(a.video)
    if digest!=seed['video_sha256']:raise ValueError('Manual seed video identity mismatch')
    config=json.loads(Path(observations.__file__).with_name('observation_config.json').read_text(encoding='utf-8'))
    feature_fn=cropped_features if a.crop_flow else observations.features
    track_fn=cropped_track if a.crop_flow else observations.track
    cv2.setNumThreads(2);previous=None;points=None;corners=None;next_target=seed['video_time_s'];counts={};started=False
    with av.open(str(a.video)) as c,(a.output/'marker_observations.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=observations.FIELDS);w.writeheader();s=c.streams.video[0];s.codec_context.thread_count=2
        for index,frame in enumerate(c.decode(s)):
            t=float(frame.pts*frame.time_base)
            if t+1e-9<next_target:continue
            next_target+=config['sampling_period_s'];gray=frame.to_ndarray(format='gray')
            diag={};method='failed_manual_tracking_v1'
            if not started:
                if index!=seed['frame_index']:raise ValueError('Seed frame/PTS do not agree')
                corners=np.array(seed['corners_canonical_order_inferred'],np.float32)
                points=feature_fn(gray,corners);started=True
                method='lk_manual_initialization_timing_only_v1'
            elif previous is not None and corners is not None:
                corners,diag=track_fn(previous,gray,points,corners,config['tracking'])
                if corners is not None:
                    points=feature_fn(gray,corners);method='lk_manual_seed_crop_timing_only_v2' if a.crop_flow else 'lk_manual_seed_timing_only_v1'
            row=observations.row_state(dict(experiment_id=a.experiment,video_sha256=digest,frame_index=index,
                pts_ticks=frame.pts,time_base_num=frame.time_base.numerator,time_base_den=frame.time_base.denominator,
                video_time_s=t,coordinate_convention='encoded_pixels'),seed['marker_id'],corners,method,diag)
            row['quality_flags']+=';timing_diagnostic_only;manual_corner_order_template_inferred;metric_pose_prohibited'
            w.writerow(row);previous=gray
            counts[row['observation_status']]=counts.get(row['observation_status'],0)+1
            if sum(counts.values())%60==0:print(a.experiment,'samples',sum(counts.values()),counts,flush=True)
    common.write_json(a.output/'observation_summary.json',dict(video_sha256=digest,seed=seed,counts=counts,
        purpose='Visual-motion timing feasibility only',crop_flow=a.crop_flow,maximum_metric_reference_scope='not_accepted',
        limitations=['Unmeasured board curvature','Accumulated tracking drift unbounded',
            'Forward/backward LK consistency does not validate absolute corner location']))
    print(json.dumps(counts),flush=True)


if __name__=='__main__':main()
