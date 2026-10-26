"""Full original-video decode, integer PTS ledger and lossless diagnostic frames.

PyAV uses FFmpeg libavcodec with err_detect=explode; no video auto-rotation.
Raw EXIF/GPS/creation-time fields are intentionally not exported.
"""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import time
import av
import cv2
import common


def audit(path, asset_id, relative_path, output):
    output.mkdir(parents=True,exist_ok=False)
    started = time.monotonic()
    result = dict(asset_id=asset_id,relative_path=relative_path,sha256=common.sha256(path),
        size_bytes=path.stat().st_size,decoder='PyAV '+av.__version__,
        decoder_libraries={k:list(v) for k,v in av.library_versions.items()},
        pixel_convention='encoded_pixels',decode_status='IN_PROGRESS')
    rows = []
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            stream.codec_context.thread_count=2
            stream.codec_context.options={'err_detect':'explode'}
            tb = stream.time_base
            result.update(codec=stream.codec_context.name,encoded_width=stream.width,
                encoded_height=stream.height,declared_frames=stream.frames,
                time_base_num=tb.numerator,time_base_den=tb.denominator,
                average_rate=str(stream.average_rate),base_rate=str(stream.base_rate),
                start_time_ticks=stream.start_time,duration_ticks=stream.duration,
                duration_s=float(stream.duration*tb) if stream.duration is not None else None)
            # Save just three true original-resolution frames, selected by PTS.
            targets=[0.5,5.0,max(0.5,(result['duration_s'] or 12)/2)]
            saved=set()
            rotations=set()
            with av.logging.Capture(local=False) as logs:
                for i,frame in enumerate(container.decode(stream)):
                    frame_tb=frame.time_base
                    t=float(frame.pts*frame_tb) if frame.pts is not None else None
                    rotations.add(frame.rotation)
                    rows.append([i,frame.pts,frame_tb.numerator,frame_tb.denominator,t])
                    for j,target in enumerate(targets):
                        if j not in saved and t is not None and t>=target:
                            name=f'diagnostic_{j}_frame_{i:06d}.png'
                            # BGR24 conversion preserves encoded geometry, not a calibrated colour reference.
                            if not cv2.imwrite(str(output/name),frame.to_ndarray(format='bgr24')):
                                raise OSError('failed to save frame')
                            result.setdefault('diagnostic_frames',[]).append(dict(
                                path=name,frame_index=i,pts_ticks=frame.pts,
                                time_base_num=frame_tb.numerator,time_base_den=frame_tb.denominator,
                                video_time_s=t,sha256=common.sha256(output/name)))
                            saved.add(j)
                    if i and i%900==0:
                        print(f'{asset_id} decoded {i} frames',flush=True)
            # AV_LOG_ERROR=16; warnings are retained separately, never silently discarded.
            result['decoder_logs']=[dict(level=int(x[0]),component=x[1],message=x[2]) for x in logs]
            result['rotation_ccw_degrees']=sorted(rotations)
            if len(rotations)==1:
                rotation=next(iter(rotations))
                H,display_size=common.encoded_to_display(stream.width,stream.height,rotation)
                result.update(rotation=rotation,encoded_to_display=H.tolist(),
                    display_width=display_size[0],display_height=display_size[1])
            pts=[r[1] for r in rows]
            result.update(decoded_frames=len(rows),missing_pts=sum(x is None for x in pts),
                nonincreasing_pts=sum(b is not None and a is not None and b<=a for a,b in zip(pts,pts[1:])),
                first_pts_ticks=pts[0] if pts else None,last_pts_ticks=pts[-1] if pts else None)
            declared=result['declared_frames']
            health=(len(rows)>0 and (not declared or len(rows)==declared) and
                result['missing_pts']==0 and result['nonincreasing_pts']==0 and
                not any(x['level']<=16 for x in result['decoder_logs']))
            result['decode_status']='passed' if health else 'failed_or_requires_review'
    except Exception as e:
        result.update(decode_status='failed',error=repr(e),decoded_frames=len(rows))
    with (output/'frame_pts.csv').open('x',newline='',encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['frame_index','pts_ticks','time_base_num','time_base_den','video_time_s']);w.writerows(rows)
    result['elapsed_s']=time.monotonic()-started
    result['checked_at_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    common.write_json(output/'media_qc.json',result)
    print(json.dumps({k:result.get(k) for k in ['asset_id','relative_path','decode_status','decoded_frames','elapsed_s']}),flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-root',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--assets',nargs='+',required=True)
    p.add_argument('--wait-for-intake',action='store_true')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    for asset in args.assets:
        root=args.data_root/'extracted'/asset
        receipt=root/'.prepared.json'
        deadline=time.monotonic()+3*3600
        while not receipt.is_file():
            if not args.wait_for_intake or time.monotonic()>deadline:
                raise FileNotFoundError(receipt)
            time.sleep(5)
        r=json.loads(receipt.read_text(encoding='utf-8'))
        for item in r['files']:
            path=Path(item['path'])
            if path.suffix.lower() not in ['.mov','.mp4'] or path.name.startswith('._') or '__MACOSX' in path.parts:
                continue
            audit(root/path,asset,path.as_posix(),args.output/(asset+'__'+path.stem))


if __name__=='__main__':
    main()
