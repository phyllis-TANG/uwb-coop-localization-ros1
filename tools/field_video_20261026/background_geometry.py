"""Per-clip floor-image registration and explicitly provisional room pose candidates."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import common


def carpet_mask(im):
    h,w=im.shape[:2];hsv=cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([0,0,20],np.uint8),np.array([179,100,190],np.uint8))
    mask[:int(.33*h)]=0;mask[:,int(.97*w):]=0
    return mask


def register(source,destination):
    scale=.5
    a=cv2.resize(source,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    b=cv2.resize(destination,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    sift=cv2.SIFT_create(nfeatures=6000)
    ka,da=sift.detectAndCompute(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY),carpet_mask(a))
    kb,db=sift.detectAndCompute(cv2.cvtColor(b,cv2.COLOR_BGR2GRAY),carpet_mask(b))
    if da is None or db is None:return dict(status='failed',reason='No floor features')
    matches=cv2.BFMatcher().knnMatch(da,db,k=2)
    good=[m for pair in matches if len(pair)==2 for m,n in [pair] if m.distance<.7*n.distance]
    if len(good)<20:return dict(status='failed',reason='Insufficient floor feature matches',matches=len(good))
    qa=np.float32([ka[m.queryIdx].pt for m in good])/scale
    qb=np.float32([kb[m.trainIdx].pt for m in good])/scale
    H,inliers=cv2.findHomography(qa,qb,cv2.RANSAC,3.)
    if H is None:return dict(status='failed',reason='Floor homography not found')
    inliers=inliers.ravel().astype(bool)
    errors=np.linalg.norm(common.transform_pixels(qa[inliers],H)-qb[inliers],axis=1)
    hull_fraction=float(cv2.contourArea(cv2.convexHull(qa[inliers]))/(source.shape[0]*source.shape[1]))
    accepted=bool(inliers.sum()>=20 and hull_fraction>=.03)
    return dict(status='candidate' if accepted else 'weak_candidate',H_destination_from_reference_floor_pixels=H.tolist(),
        matches=len(good),inliers=int(inliers.sum()),inlier_fraction=float(inliers.mean()),
        floor_inlier_hull_fraction=hull_fraction,median_transfer_residual_px=float(np.median(errors)),
        p95_transfer_residual_px=float(np.quantile(errors,.95)),
        warning='Image registration residual is not independent metric accuracy; floor planarity/background identity remain assumptions')


def room_pose(points_xy_pixels,room_xyz,K,D):
    obj=np.array(room_xyz,dtype=np.float64);image=np.array(points_xy_pixels,dtype=np.float64)
    ok,r,t=cv2.solvePnP(obj,image,np.array(K,dtype=np.float64),np.array(D,dtype=np.float64),flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:raise ValueError('PnP failed')
    R=cv2.Rodrigues(r)[0];T=np.eye(4);T[:3,:3]=R.T;T[:3,3]=-R.T@t.ravel()
    projected=cv2.projectPoints(obj,r,t,np.array(K),np.array(D))[0].reshape(-1,2)
    if np.any((obj@R.T+t.ravel())[:,2]<=0):raise ValueError('Room points behind camera')
    if T[2,3]<=0:raise ValueError('Camera below room floor')
    return dict(T_room_camera=T.tolist(),solver='SOLVEPNP_ITERATIVE_planar_initialization',
        fit_reprojection_rms_px=float(np.sqrt(np.mean(np.sum((projected-image)**2,axis=1)))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--media',required=True,type=Path);p.add_argument('--reference-frame',required=True,type=Path)
    p.add_argument('--calibration',required=True,type=Path);p.add_argument('--geometry',required=True,type=Path)
    p.add_argument('--annotations',type=Path);p.add_argument('--output',required=True,type=Path)
    p.add_argument('--assets',nargs='*')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(2)
    reference=cv2.imread(str(a.reference_frame));models=json.loads(a.calibration.read_text(encoding='utf-8'))['models']
    geometry=json.loads(a.geometry.read_text(encoding='utf-8'));annotation=json.loads(a.annotations.read_text(encoding='utf-8')) if a.annotations else None
    records=[]
    for qc in sorted(a.media.glob('*/media_qc.json')):
        info=json.loads(qc.read_text(encoding='utf-8'));clips=[]
        if a.assets and info['asset_id'] not in a.assets:continue
        for frame in info['diagnostic_frames']:
            im=cv2.imread(str(qc.parent/frame['path']));registration=register(reference,im)
            result=dict(frame_index=frame['frame_index'],video_time_s=frame['video_time_s'],registration=registration,
                T_room_camera=None,transform_status='pending',covariance=None)
            if annotation and 'H_destination_from_reference_floor_pixels' in registration:
                points=common.transform_pixels(annotation['P_pixels'],registration['H_destination_from_reference_floor_pixels'])
                room=[geometry['ground_reference_points'][name] for name in annotation['P_ids']]
                candidates={}
                for key in ['IMG_7337_all','IMG_7336_all','both_all']:
                    model=models[key]
                    try:candidates[key]=room_pose(points,room,model['K'],model['D'])
                    except ValueError as e:candidates[key]={'error':str(e)}
                result.update(provisional_P_pixels=points.tolist(),room_pose_candidates=candidates,
                    transform_status='nominal_P_and_unstable_intrinsics_candidates_not_accepted')
            clips.append(result)
        records.append(dict(asset_id=info['asset_id'],video_sha256=info['sha256'],rotation_ccw=info['rotation'],
            encoded_to_display=info['encoded_to_display'],display_size_wh=[info['display_width'],info['display_height']],
            clips=clips))
        print(info['asset_id'],[(x['frame_index'],x['registration']['status'],x['registration'].get('inliers')) for x in clips],flush=True)
    common.write_json(a.output/'frame_transforms.json',dict(schema_version=1,
        convention=dict(direction='T_room_camera maps camera optical coordinates into room',handedness='right-handed',
            camera_axes='x right, y down, z forward',room_axes='historical room frame; z up',units='metres',rotation='3x3 block in homogeneous 4x4 matrix'),
        reference_frame_sha256=common.sha256(a.reference_frame),geometry_sha256=common.sha256(a.geometry),
        calibration_sha256=common.sha256(a.calibration),point_annotations=annotation,records=records,
        marker_geometry=dict(black_border_side_m=.144,marker_to_body_rotations={'car1':None,'car2':None},
            marker_to_antenna_policy='Body-aligned translations must not be substituted as native ArUco-frame translations',
            raised_plane_heights_m={'car1':.37,'car2':.23},antenna_heights_m={'car1':.17,'car2':.20}),
        acceptance='not_accepted',remaining=['Actual P/Q survey and video-point identities unconfirmed',
            'Intrinsics stability/clip imaging equivalence unapproved','Marker/body rotation and Car2 nonplanarity unknown']))


if __name__=='__main__':main()
