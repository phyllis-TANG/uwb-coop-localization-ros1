"""Locate written P cross intersections in explicit human-selected original-pixel ROIs."""
import argparse
from pathlib import Path
import cv2
import numpy as np
import common

ROIS={'P1':[900,900,1220,1120],'P2':[280,1490,700,1930],
      'P3':[3000,900,3410,1180],'P4':[3310,1660,3839,2140]}


def cross_intersection(crop):
    gray=cv2.cvtColor(crop,cv2.COLOR_BGR2GRAY)
    white=(gray>170).astype(np.uint8)*255
    contours,_=cv2.findContours(white,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:raise ValueError('No white paper in ROI')
    contour=max(contours,key=cv2.contourArea)
    mask=np.zeros_like(gray);cv2.drawContours(mask,[contour],-1,255,-1)
    mask=cv2.erode(mask,np.ones((11,11),np.uint8))
    local_contrast=cv2.morphologyEx(gray,cv2.MORPH_BLACKHAT,np.ones((11,11),np.uint8))
    ink=((local_contrast>10)&(mask>0)).astype(np.uint8)*255
    lines=cv2.HoughLinesP(ink,1,np.pi/720,threshold=15,minLineLength=30,maxLineGap=8)
    if lines is None:raise ValueError('No cross strokes')
    lines=lines.reshape(-1,4).astype(float)
    length=np.linalg.norm(lines[:,2:]-lines[:,:2],axis=1)
    order=np.argsort(-length);first=lines[order[0]]
    def angle(line):return np.arctan2(line[3]-line[1],line[2]-line[0])%np.pi
    def difference(a,b):return abs((a-b+np.pi/2)%np.pi-np.pi/2)
    a=angle(first);other=[i for i in order if difference(angle(lines[i]),a)>np.deg2rad(25)]
    if not other:raise ValueError('Only one cross direction')
    b=angle(lines[other[0]])
    groups=[[line for line in lines if difference(angle(line),seed)<np.deg2rad(10)] for seed in (a,b)]
    fitted=[]
    for group in groups:
        points=np.vstack([line.reshape(2,2) for line in group]).astype(np.float32)
        vx,vy,x,y=cv2.fitLine(points,cv2.DIST_HUBER,0,.01,.01).ravel()
        fitted.append((np.array([x,y]),np.array([vx,vy])))
    (p,u),(q,v)=fitted
    coefficient=np.linalg.solve(np.c_[u,-v],q-p)[0]
    xy=p+coefficient*u
    if not(0<xy[0]<crop.shape[1] and 0<xy[1]<crop.shape[0]):raise ValueError('Cross outside ROI')
    return xy,dict(stroke_lines=[len(g) for g in groups],fitted_lines=[dict(point=p.tolist(),direction=u.tolist()) for p,u in fitted])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frame',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--manual-pixels',nargs=8,type=float,help='Explicit original-pixel P1/P2/P3/P4 x,y annotations')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
    im=cv2.imread(str(a.frame));overlay=im.copy();points=[];records=[]
    for index,(label,(x0,y0,x1,y1)) in enumerate(ROIS.items()):
        if a.manual_pixels:
            point=np.array(a.manual_pixels[index*2:index*2+2]);diag={'method':'explicit_human_annotation'}
        else:
            point,diag=cross_intersection(im[y0:y1,x0:x1]);point+=np.array([x0,y0])
        points.append(point.tolist());records.append(dict(id=label,ROI_xyxy=[x0,y0,x1,y1],pixel=point.tolist(),diagnostic=diag))
        cv2.drawMarker(overlay,tuple(np.round(point).astype(int)),(0,0,255),cv2.MARKER_CROSS,30,3)
        cv2.putText(overlay,label,tuple(np.round(point+np.array([15,-15])).astype(int)),cv2.FONT_HERSHEY_SIMPLEX,1.4,(0,0,255),3)
    cv2.imwrite(str(a.output/'P_annotations_preview.jpg'),cv2.resize(overlay,None,fx=.4,fy=.4))
    common.write_json(a.output/'P_annotations.json',dict(schema_version=1,
        reference_frame_sha256=common.sha256(a.frame),coordinate_convention='encoded_pixels',
        P_ids=list(ROIS),P_pixels=points,annotations=records,
        identity_source='Written P1/P2/P3/P4 labels read in original video, consistent with session log section50',
        coordinate_source='geometry.json instructed nominal coordinates; actual ruler survey not supplied',
        coordinate_uncertainty_m=None,pixel_annotation_uncertainty_px=None,
        independent_Q_used_for_identification_or_fit=False,status='nominal_geometry_feasibility_only'))
    print(points,flush=True)


if __name__=='__main__':main()
