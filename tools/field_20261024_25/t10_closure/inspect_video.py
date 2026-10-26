"""Bounded T10-only PTS review using PR49 observations, not new calibration."""
import argparse
import csv
import json
from pathlib import Path
import time

from common import MOV_SHA, VIDEO, finish, sha, start, verify_video_artifacts, write


def select_frames(rows, targets):
    # Exact rational PTS arithmetic for selection; frame/30 is never used.
    from fractions import Fraction
    unique = {int(r['frame_index']):r for r in rows}
    def stamp(r): return Fraction(int(r['pts_ticks']) * int(r['time_base_num']), int(r['time_base_den']))
    return [min(unique.values(), key=lambda r:abs(stamp(r)-Fraction(str(t)))) for t in targets]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mov',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args(); run = start(args.output,'T10_targeted_video_review'); started=time.monotonic()
    try:
        import av
        import cv2
        import numpy as np
        run['pr49_reuse'] = verify_video_artifacts()
        if sha(args.mov) != MOV_SHA: raise ValueError('T10 original MOV identity mismatch')
        run['inputs']=[{'asset_id':'T10_video','relative_path':'IMG_7347.MOV','sha256':MOV_SHA},
            {'relative_path':'marker_observations.csv','sha256':sha(VIDEO/'marker_observations.csv')},
            {'relative_path':'frame_pts/f7ec52ce2393.csv','sha256':sha(VIDEO/'frame_pts/f7ec52ce2393.csv')}]
        rows = [r for r in csv.DictReader((VIDEO/'marker_observations.csv').open()) if r['experiment_id']=='T10']
        protocol = json.loads(Path(__file__).with_name('protocol.json').read_text())
        chosen = select_frames(rows,protocol['video_review']['sample_targets_s'])
        targets = {int(r['frame_index']):r for r in chosen}
        annotations = {}
        for r in rows: annotations.setdefault(int(r['frame_index']),[]).append(r)
        pts = {int(r['frame_index']):r for r in csv.DictReader((VIDEO/'frame_pts/f7ec52ce2393.csv').open())}
        tiles, bindings = [], []
        with av.open(str(args.mov)) as c:
            stream=c.streams.video[0]; stream.codec_context.thread_count=2
            for index, frame in enumerate(c.decode(stream)):
                if time.monotonic()-started>300: raise TimeoutError('targeted video review 300s bound')
                if index not in targets: continue
                old=pts[index]
                if (frame.pts,frame.time_base.numerator,frame.time_base.denominator) != tuple(int(old[k]) for k in ('pts_ticks','time_base_num','time_base_den')):
                    raise ValueError('original PTS differs from PR49')
                image=frame.to_ndarray(format='bgr24')
                for r in annotations[index]:
                    if r['detected']!='1': continue
                    corners=np.array([[float(r[f'corner{i}_{k}_px']) for k in ('x','y')] for i in range(4)])
                    color=(40,230,30) if r['vehicle_id']=='car1' else (255,180,0)
                    cv2.polylines(image,[corners.astype(np.int32)],True,color,5)
                    cv2.putText(image,r['vehicle_id'],tuple(corners[0].astype(int)),cv2.FONT_HERSHEY_SIMPLEX,2,color,4)
                tile=cv2.resize(image,(960,540));cv2.rectangle(tile,(0,0),(960,40),(0,0,0),-1)
                cv2.putText(tile,f'frame {index} PTS {frame.pts} / {frame.time_base.denominator} s  PR49 overlays',
                            (8,26),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,255),1)
                tiles.append((index,tile));bindings.append({'frame_index':index,'pts_ticks':frame.pts,
                    'time_base_num':frame.time_base.numerator,'time_base_den':frame.time_base.denominator,
                    'video_time_s':float(frame.pts*frame.time_base),'source':'actual PyAV frame; overlay reused PR49 corners'})
                if len(tiles)==len(targets): break
        if len(tiles)!=len(targets): raise ValueError('targeted frames missing')
        tiles.sort();sheet=np.vstack([np.hstack([t[1] for t in tiles[i:i+2]]) for i in range(0,len(tiles),2)])
        if not cv2.imwrite(str(args.output/'T10_contact_sheet.jpg'),sheet,[cv2.IMWRITE_JPEG_QUALITY,85]): raise IOError('image write failed')
        write(args.output/'review.json',{'schema_version':1,'status':'DONE','video_sha256':MOV_SHA,
            'samples':bindings,'saved_images':1,'saved_full_resolution_frames':0,'last_decoded_frame_index':max(targets),
            'full_media_integrity_check_repeated':False,'new_marker_detection':False,
            'elapsed_seconds':time.monotonic()-started,'scope':'targeted scene/stage review, not metric reference or synchronization calibration'})
        finish(args.output,run,'DONE');return 0
    except Exception as error:
        write(args.output/'failure.json',{'error':str(error)});finish(args.output,run,'FAILED');raise


if __name__=='__main__':raise SystemExit(main())
