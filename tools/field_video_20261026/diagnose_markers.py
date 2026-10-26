"""Small original-4K-frame diagnostic, separating decoding from geometric validity."""
import argparse
import json
from pathlib import Path
import cv2
import numpy as np
import common


def bit_diagnostic(image,quad,marker_id):
    target=np.array([[0,0],[119,0],[119,119],[0,119]],np.float32)
    H=cv2.getPerspectiveTransform(np.array(quad,np.float32),target)
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY) if image.ndim==3 else image
    warped=cv2.warpPerspective(gray,H,(120,120))
    threshold,binary=cv2.threshold(warped,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    cells=np.array([[np.mean(binary[20*r+5:20*r+15,20*c+5:20*c+15])>127
        for c in range(6)] for r in range(6)],np.uint8)
    d=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    expected=cv2.aruco.Dictionary_getBitsFromByteList(d.bytesList[marker_id:marker_id+1],4)
    hamming=[int(np.count_nonzero(cells[1:5,1:5]!=np.rot90(expected,k))) for k in range(4)]
    border=np.r_[cells[0],cells[-1],cells[1:-1,0],cells[1:-1,-1]]
    return dict(best_interior_hamming=min(hamming),hamming_by_rotation=hamming,
        border_white_cells=int(border.sum()),sampled_cells=cells.tolist(),otsu_threshold=threshold),warped


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--media-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--assets',nargs='*')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);cv2.setNumThreads(2)
    dictionary=cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    rows=[]
    for qc in sorted(a.media_root.glob('*/media_qc.json')):
        info=json.loads(qc.read_text(encoding='utf-8'))
        if a.assets and info['asset_id'] not in a.assets:continue
        for sample in info['diagnostic_frames']:
            path=qc.parent/sample['path'];image=cv2.imread(str(path))
            if image.shape[:2]!=(info['encoded_height'],info['encoded_width']):raise ValueError('Not original resolution')
            record=dict(asset_id=info['asset_id'],video_sha256=info['sha256'],
                frame_index=sample['frame_index'],pts_ticks=sample['pts_ticks'],
                time_base_num=sample['time_base_num'],time_base_den=sample['time_base_den'],
                source_frame_sha256=common.sha256(path),encoded_size_wh=[image.shape[1],image.shape[0]],variants=[])
            overlay=image.copy()
            for label,poly in [('default',0.03),('polygon006',0.06),('polygon010_diagnostic_only',0.10)]:
                par=cv2.aruco.DetectorParameters();par.polygonalApproxAccuracyRate=poly
                corners,ids,rejected=cv2.aruco.ArucoDetector(dictionary,par).detectMarkers(image)
                found=[]
                if ids is not None:
                    for marker_id,corner in zip(ids.ravel(),corners):
                        q=corner.reshape(4,2);bits,_=bit_diagnostic(image,q,int(marker_id))
                        found.append(dict(marker_id=int(marker_id),corners=q.tolist(),
                            shortest_edge_px=float(np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1).min()),
                            nominal_shortest_module_px=float(np.linalg.norm(np.roll(q,-1,axis=0)-q,axis=1).min()/6),**bits))
                    if label=='default':cv2.aruco.drawDetectedMarkers(overlay,corners,ids)
                # Closest rejected quadrilateral to ID1 helps separate contour failure from code failure.
                rejected_bits=[]
                for quad in rejected:
                    diagnostic,_=bit_diagnostic(image,quad.reshape(4,2),1)
                    rejected_bits.append(dict(corners=quad.reshape(4,2).tolist(),**diagnostic))
                rejected_bits=sorted(rejected_bits,key=lambda x:(x['best_interior_hamming'],x['border_white_cells']))[:3]
                record['variants'].append(dict(method=label,found=found,rejected_count=len(rejected),best_rejected_for_id1=rejected_bits))
            # Preview only; original frame identity stays separate.
            preview=cv2.resize(overlay,None,fx=0.4,fy=0.4,interpolation=cv2.INTER_AREA)
            name=qc.parent.name+f'_{sample["frame_index"]:06d}.jpg'
            cv2.imwrite(str(a.output/name),preview)
            record['preview']=name;rows.append(record)
            print(info['asset_id'],sample['frame_index'],[(v['method'],[x['marker_id'] for x in v['found']]) for v in record['variants']],flush=True)
    common.write_json(a.output/'marker_diagnostic.json',dict(schema_version=1,frames=rows,
        scope='Image extraction and code recognition only. No metric-position approval.',
        geometry_limit='Car2 bending and marker/body alignment remain unverified even when ID1 is decoded'))


if __name__=='__main__':main()
