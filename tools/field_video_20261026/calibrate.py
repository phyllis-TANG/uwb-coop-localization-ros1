"""Calibration-stability audit in encoded pixels; no independent accuracy approval."""
import argparse
import json
from pathlib import Path
import av
import cv2
import numpy as np
import common


def object_points():
    q=np.zeros((54,3),np.float32)
    q[:,:2]=np.mgrid[:9,:6].T.reshape(-1,2)*[0.192/10,0.134/7]
    return q


def fit(views,indices,size):
    obj=[object_points() for _ in indices]
    image=[views[i]['corners'].astype(np.float32) for i in indices]
    rms,K,D,r,t,std_i,std_e,errors=cv2.calibrateCameraExtended(obj,image,size,None,None)
    return dict(rms_px=float(rms),K=K.tolist(),D=D.ravel().tolist(),
        per_view_rms_px=errors.ravel().tolist(),std_intrinsics_linearized=std_i.ravel().tolist(),
        view_indices=indices,n_views=len(indices),
        note='Linearized fit statistics, not a metrological or spatial accuracy guarantee')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--videos',nargs=2,required=True,type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    views=[];samples=[];size=None
    cv2.setNumThreads(2)
    for path in a.videos:
        video_sha=common.sha256(path)
        with av.open(str(path)) as c:
            s=c.streams.video[0];s.codec_context.thread_count=2
            size=(s.width,s.height)
            next_target=0.
            for frame_index,frame in enumerate(c.decode(s)):
                if frame.pts is None:raise ValueError('Missing frame PTS')
                ts=float(frame.pts*frame.time_base)
                if ts+1e-9<next_target:continue
                next_target+=0.5
                gray=frame.to_ndarray(format='gray')
                small=cv2.resize(gray,None,fx=0.5,fy=0.5,interpolation=cv2.INTER_AREA)
                ok,corners=cv2.findChessboardCornersSB(small,(9,6),cv2.CALIB_CB_NORMALIZE_IMAGE)
                row=dict(file=path.name,video_sha256=video_sha,frame_index=frame_index,
                    pts_ticks=frame.pts,time_base_num=frame.time_base.numerator,
                    time_base_den=frame.time_base.denominator,video_time_s=ts,
                    rotation_ccw=frame.rotation,detected=bool(ok),coordinate_convention='encoded_pixels')
                if ok:
                    original=(corners*2).astype(np.float32)
                    before_refinement=original.copy()
                    refined=cv2.cornerSubPix(gray,original,(5,5),(-1,-1),
                        (cv2.TERM_CRITERIA_EPS+cv2.TERM_CRITERIA_MAX_ITER,40,0.001))
                    row['corner_refinement_shift_max_px']=float(np.linalg.norm(refined-before_refinement,axis=2).max())
                    row['corners']=refined.reshape(54,2).tolist()
                    views.append(dict(file=path.name,frame_index=frame_index,time_s=ts,corners=refined))
                    image=cv2.cvtColor(small,cv2.COLOR_GRAY2BGR)
                    cv2.drawChessboardCorners(image,(9,6),refined/2,True)
                    cv2.imwrite(str(a.output/f'{path.stem}_{frame_index:04d}_corners.jpg'),image)
                samples.append(row)
                print(path.name,frame_index,ok,flush=True)
    common.write_json(a.output/'corner_observations.json',samples)
    models={}
    for path in a.videos:
        ids=[i for i,v in enumerate(views) if v['file']==path.name]
        for label,idx in [('all',ids),('interleaved_even',ids[::2]),('interleaved_odd',ids[1::2]),
                         ('early',ids[:len(ids)//2]),('late',ids[len(ids)//2:])]:
            if len(idx)>=6:
                models[path.stem+'_'+label]=fit(views,idx,size)
    models['both_all']=fit(views,list(range(len(views))),size)
    report=dict(schema_version=1,status='candidate_not_spatially_validated',
        encoded_size_wh=list(size),sampling='first actual frame at/after each 0.5s PTS target',
        pitch_xy_m=[0.192/10,0.134/7],inner_corners=[9,6],
        methods='SB half-resolution, multiply by 2, original-pixel 5x5 subpixel refinement; standard five distortion coefficients',
        samples=len(samples),valid_views=len(views),models=models,
        limitations=['Board flatness and measurement uncertainty are unverified',
            'Video imaging/focus equivalence is unverified',
            'Interleaved and adjacent views are temporally correlated',
            'No Q point is used for intrinsics fitting; reprojection RMS is not independent position accuracy'])
    common.write_json(a.output/'calibration_stability.json',report)
    print(json.dumps({k:dict(rms=v['rms_px'],fx=v['K'][0][0],fy=v['K'][1][1]) for k,v in models.items()}),flush=True)


if __name__=='__main__':main()
