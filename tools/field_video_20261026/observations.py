"""PTS-sampled original-pixel observations with decoded/tracked/failed states separated."""
import argparse
import csv
import json
from pathlib import Path
import time
import av
import cv2
import numpy as np
import common

FIELDS=['experiment_id','video_sha256','frame_index','pts_ticks','time_base_num','time_base_den',
    'video_time_s','coordinate_convention','marker_id','vehicle_id','detected','method_version',
    *[f'corner{i}_{a}_px' for i in range(4) for a in ('x','y')],
    'quality_flags','invalid_reason','observation_status','tracked','tracking_inliers','tracking_fb_median_px']


def detectors(config):
    dictionary=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    result=[]
    for key in ['default_detector','recovery_detector']:
        params=cv2.aruco.DetectorParameters()
        for name,value in config[key].items():setattr(params,name,value)
        result.append(cv2.aruco.ArucoDetector(dictionary,params))
    return result


def decode(gray,ds):
    found={};counts=[]
    for detector_index,detector in enumerate(ds):
        corners,ids,rejected=detector.detectMarkers(gray)
        counts.append(len(rejected))
        if ids is not None:
            for marker_id,corner in zip(ids.ravel(),corners):
                marker_id=int(marker_id)
                if marker_id in (0,1) and marker_id not in found:
                    found[marker_id]=(corner.reshape(4,2),['aruco_default_subpix_v1','aruco_polygon006_subpix_v1'][detector_index])
        if len(found)==2:break
    return found,counts


def features(gray,corners):
    mask=np.zeros_like(gray)
    cv2.fillConvexPoly(mask,np.round(corners).astype(np.int32),255)
    return cv2.goodFeaturesToTrack(gray,maxCorners=120,qualityLevel=0.01,minDistance=4,
        mask=mask,blockSize=5)


def track(previous,current,points,corners,config):
    """No identity inference: only propagate an earlier decoded/manual identity."""
    if points is None or len(points)<config['minimum_inliers']:return None,{'reason':'insufficient_seed_features'}
    q,ok,_=cv2.calcOpticalFlowPyrLK(previous,current,points,None,winSize=(31,31),maxLevel=3)
    if q is None:return None,{'reason':'forward_flow_failed'}
    back,okb,_=cv2.calcOpticalFlowPyrLK(current,previous,q,None,winSize=(31,31),maxLevel=3)
    if back is None:return None,{'reason':'backward_flow_failed'}
    fb=np.linalg.norm(points-back,axis=2).ravel()
    valid=ok.ravel().astype(bool)&okb.ravel().astype(bool)&(fb<config['forward_backward_threshold_px'])
    if valid.sum()<config['minimum_inliers']:return None,{'reason':'forward_backward_rejected'}
    H,inliers=cv2.findHomography(points[valid],q[valid],cv2.RANSAC,config['ransac_threshold_px'])
    if H is None:return None,{'reason':'no_tracking_homography'}
    n=int(inliers.sum());fraction=n/len(inliers)
    if n<config['minimum_inliers'] or fraction<config['minimum_inlier_fraction']:
        return None,{'reason':'insufficient_tracking_inliers'}
    result=common.transform_pixels(corners,H).astype(np.float32)
    h,w=current.shape
    if not np.isfinite(result).all() or cv2.contourArea(result)<25 or not cv2.isContourConvex(result):
        return None,{'reason':'invalid_tracked_quad'}
    if np.any(result[:,0]<0) or np.any(result[:,0]>=w) or np.any(result[:,1]<0) or np.any(result[:,1]>=h):
        return None,{'reason':'tracked_quad_outside_image'}
    return result,dict(inliers=n,fb_median_px=float(np.median(fb[valid])),inlier_fraction=fraction)


def row_state(base,marker_id,corners,method,diagnostic=None):
    row=dict(base,marker_id=marker_id,vehicle_id='car1' if marker_id==0 else 'car2',
        detected=int(method.startswith('aruco_')),tracked=int(method.startswith('lk_')),
        method_version=method,quality_flags='metric_calibration_not_applied',invalid_reason='',
        observation_status='decoded' if method.startswith('aruco_') else ('tracked' if corners is not None else 'failed'))
    if marker_id==1:row['quality_flags']+=';board_bending_and_tilt_unverified'
    if corners is None:row['invalid_reason']=(diagnostic or {}).get('reason','not_decoded_or_tracked')
    else:
        for i,(x,y) in enumerate(corners):row[f'corner{i}_x_px']=float(x);row[f'corner{i}_y_px']=float(y)
    if diagnostic:
        row['tracking_inliers']=diagnostic.get('inliers','')
        row['tracking_fb_median_px']=diagnostic.get('fb_median_px','')
    return row


def process(path,asset_id,relative_path,output,config,manual_seed=None):
    output.mkdir(parents=True,exist_ok=False)
    ds=detectors(config);cv2.setNumThreads(2)
    video_sha=common.sha256(path);experiment=asset_id[:3] if asset_id.startswith('T') else ''
    states={};previous=None;next_target=0.;count=0;counts={}
    period=config['sampling_period_s']
    with av.open(str(path)) as container,(output/'marker_observations.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader()
        stream=container.streams.video[0];stream.codec_context.thread_count=2
        for frame_index,frame in enumerate(container.decode(stream)):
            if frame.pts is None:raise ValueError('Missing PTS')
            t=float(frame.pts*frame.time_base)
            if t+1e-9<next_target:continue
            next_target+=period
            gray=frame.to_ndarray(format='gray')
            found,rejected=decode(gray,ds)
            base=dict(experiment_id=experiment,video_sha256=video_sha,frame_index=frame_index,
                pts_ticks=frame.pts,time_base_num=frame.time_base.numerator,time_base_den=frame.time_base.denominator,
                video_time_s=t,coordinate_convention='encoded_pixels')
            for marker_id in (0,1):
                corner=None;method='failed_v1';diag={}
                if marker_id in found:
                    corner,method=found[marker_id]
                    states[marker_id]=dict(last_decode_s=t,corners=corner,features=features(gray,corner),seed='decoded')
                elif manual_seed and frame_index==manual_seed['frame_index'] and str(marker_id) in manual_seed['corners']:
                    corner=np.array(manual_seed['corners'][str(marker_id)],np.float32)
                    method='lk_manual_initialization_v1'
                    states[marker_id]=dict(last_decode_s=t,corners=corner,features=features(gray,corner),seed='manual')
                elif previous is not None and marker_id in states and config['tracking']['enabled']:
                    state=states[marker_id]
                    if t-state['last_decode_s']<=config['tracking']['max_gap_since_decode_s']:
                        corner,diag=track(previous,gray,state['features'],state['corners'],config['tracking'])
                        if corner is not None:
                            method='lk_'+state['seed']+'_seed_v1'
                            state.update(corners=corner,features=features(gray,corner))
                    else:diag={'reason':'tracking_seed_expired'}
                row=row_state(base,marker_id,corner,method,diag);w.writerow(row)
                counts[row['vehicle_id']+'_'+row['observation_status']]=counts.get(row['vehicle_id']+'_'+row['observation_status'],0)+1
                if corner is None:states.pop(marker_id,None)
            previous=gray;count+=1
            if count%60==0:print(asset_id,path.name,'samples',count,counts,flush=True)
    result=dict(asset_id=asset_id,relative_path=relative_path,video_sha256=video_sha,
        sampled_frames=count,counts=counts,sampling_period_s=period,
        source='original encoded-resolution pixels',manual_seed=manual_seed,
        spatial_reference_status='not_validated')
    common.write_json(output/'observation_summary.json',result)
    print(json.dumps(result),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--assets',nargs='+',required=True);p.add_argument('--config',type=Path,default=Path(__file__).with_name('observation_config.json'))
    p.add_argument('--wait-for-intake',action='store_true');p.add_argument('--manual-seeds',type=Path)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    config=json.loads(a.config.read_text(encoding='utf-8'))
    seeds=json.loads(a.manual_seeds.read_text(encoding='utf-8')) if a.manual_seeds else {}
    for asset in a.assets:
        root=a.data_root/'extracted'/asset;receipt=root/'.prepared.json'
        deadline=time.monotonic()+3*3600
        while not receipt.is_file():
            if not a.wait_for_intake or time.monotonic()>deadline:raise FileNotFoundError(receipt)
            time.sleep(5)
        for item in json.loads(receipt.read_text(encoding='utf-8'))['files']:
            path=Path(item['path'])
            if path.suffix.lower()!='.mov' or path.name.startswith('._') or '__MACOSX' in path.parts:continue
            process(root/path,asset,path.as_posix(),a.output/(asset+'__'+path.stem),config,seeds.get(item['sha256']))


if __name__=='__main__':main()
