"""Independent transfer readback: all selected rows, PTS, nulls and old source poses.

No estimator, metric pose recovery or clock fitting is invoked.
"""
import argparse
import csv
import itertools
import json
from pathlib import Path

from common import BAG_SHA, MOV_SHA, SESSION, VIDEO, finish, sha, start, verify_packet, write
import verify_outputs


def compare_selection(original, selected, key, value):
    with Path(original).open(newline='') as src,Path(selected).open(newline='') as dst:
        a,b=csv.DictReader(src),csv.DictReader(dst)
        if a.fieldnames!=b.fieldnames:raise ValueError('column identity changed')
        count=0
        for x,y in itertools.zip_longest((r for r in a if r[key]==value),b):
            if x!=y:raise ValueError('selected row changed, omitted, added or reordered')
            if 'source_file_sha256' in y and y['source_file_sha256']!=BAG_SHA:raise ValueError('wrong attempt')
            count+=1
    return count


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet',type=Path,required=True);p.add_argument('--normalized',type=Path,required=True)
    p.add_argument('--review',type=Path,required=True);p.add_argument('--strict-run',type=Path,required=True)
    p.add_argument('--reference-decision',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'T10_independent_readback')
    try:
        packet_receipt=verify_packet(args.packet)
        with (args.packet/'normalized_T10/odom.csv').open() as f:odom=list(csv.DictReader(f))
        row_checks={}
        for name in ('odom.csv','ranges.csv','frames.csv','imu.csv','commands.csv'):
            row_checks[name]=compare_selection(args.normalized/name,args.packet/'normalized_T10'/name,'experiment_id','T10')
        row_checks['marker_observations.csv']=compare_selection(VIDEO/'marker_observations.csv',args.packet/'video_T10/marker_observations.csv','experiment_id','T10')
        if sha(VIDEO/'frame_pts/f7ec52ce2393.csv')!=sha(args.packet/'video_T10/frame_pts.csv'):raise ValueError('T10 PTS table changed')
        pts={int(r['frame_index']):r for r in csv.DictReader((args.packet/'video_T10/frame_pts.csv').open())}
        bindings=json.loads((args.packet/'initialization_records.json').read_text())
        for car,b in bindings.items():
            identity=b['selected_source_record']
            candidates=[r for r in odom if r['vehicle_id']==car]
            earliest=min(candidates,key=lambda r:(int(r['receive_epoch_ns']),int(r['record_index'])))
            if any(int(earliest[k])!=identity[k] for k in ('record_index','header_epoch_ns','receive_epoch_ns')):raise ValueError('initial record mismatch')
            if b['adopted_as_actual_room_initialization'] or b['actual_initial_antenna_xy_room_m'] is not None or b['actual_initial_body_yaw_room_rad'] is not None:
                raise ValueError('unknown physical pose promoted')
            c=b['conditional_video_candidate'];actual=pts[c['frame_index']]
            if any(int(actual[k])!=c[k] for k in ('pts_ticks','time_base_num','time_base_den')):raise ValueError('binding PTS changed')
        origin=next(r for r in json.loads((SESSION/'manifest.json').read_text())['formal_bags'] if r['id']=='T10')['first_bag_receive_epoch_ns']
        prior=args.packet/'reused_PR46_T10'
        with (prior/'estimate.csv').open() as f:old=verify_outputs.verify_rows(csv.DictReader(f),odom,origin)
        review=json.loads((args.review/'review.json').read_text())
        if review['video_sha256']!=MOV_SHA or review['saved_full_resolution_frames']!=0:raise ValueError('review scope changed')
        for b in review['samples']:
            r=pts[b['frame_index']]
            if any(int(r[k])!=b[k] for k in ('pts_ticks','time_base_num','time_base_den')):raise ValueError('review PTS mismatch')
        execution=json.loads((args.strict_run/'execution.json').read_text())
        config=json.loads((args.strict_run/'baseline_config.json').read_text())
        if execution['status']!='BLOCKED' or execution['new_estimator_runs']!=0:raise ValueError('unexpected strict execution')
        for car,h in [('car1',.17),('car2',.20)]:
            c=config['vehicles'][car]
            if c['antenna_height_m']['value']!=h or c['antenna_height_m']['uncertainty_m'] is not None:raise ValueError('manual height provenance changed')
            if c['antenna_body_xy_m']['value'] is not None or c['initial_room_pose']['value'] is not None:raise ValueError('unknown geometry filled')
            for clock in ('odom_clock','range_clock'):
                if c[clock]['destination_origin_ns'] is not None or c[clock]['uncertainty_ns'] is not None:raise ValueError('unknown clock filled')
            if 'base_height_m' in c or 'antenna_body_xyz_m' in c:raise ValueError('redundant/fake Z decomposition')
        reference=json.loads(args.reference_decision.read_text())
        if reference['metric_reference_scope']!='not_accepted' or any(v is not None for v in reference['field_accuracy_metrics'].values()):
            raise ValueError('unsupported field accuracy claim')
        write(args.output/'verification.json',{'status':'DONE','all_passed':True,'packet':packet_receipt,
            'selected_rows_compared_to_originals':row_checks,'PTS_rows_verified':len(pts),'initial_record_identities_verified':2,
            'targeted_video_PTS_verified':len(review['samples']),'old_T10_source_replay':old,
            'strict_unknowns_and_nulls_verified':True,'new_estimator_runs':0,'holdout_replay_or_error_evaluation':False,
            'field_accuracy_evaluated':False})
        run['inputs']=[{'relative_path':'packet/run.json','sha256':sha(args.packet/'run.json')},
            {'relative_path':'reference_decision.json','sha256':sha(args.reference_decision)}]
        finish(args.output,run,'DONE');return 0
    except Exception as error:
        write(args.output/'failure.json',{'error':str(error)});finish(args.output,run,'FAILED');raise


if __name__=='__main__':raise SystemExit(main())
