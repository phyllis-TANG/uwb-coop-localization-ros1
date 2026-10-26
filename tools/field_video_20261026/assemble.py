"""Assemble compact, identity-checked contract artifacts; never promote candidates to truth."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import common
import observations


def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def save_csv(path,fields,rows):
    with Path(path).open('x',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def role(filename):
    stem=Path(filename).stem
    if stem in ['IMG_7336','IMG_7337']:return 'camera_calibration',[]
    if stem=='IMG_7364':return 'ground_reference',[]
    if stem in ['IMG_7365','IMG_7366','IMG_7367']:return 'provisional_check_car2',['car2']
    if stem in ['IMG_7369','IMG_7370','IMG_7371','IMG_7373']:return 'provisional_check_car1',['car1']
    return 'motion',['car1','car2']


def qualify(row,clip_role,expected):
    row=dict(row);row['clip_role']=clip_role
    row['vehicle_expected_in_clip']=int(row['vehicle_id'] in expected)
    if row['vehicle_id'] not in expected:
        row['quality_flags']+=';not_expected_in_this_reference_scene'
        if row['observation_status']=='failed':
            row['observation_status']='not_applicable';row['invalid_reason']='vehicle_not_expected_in_reference_scene'
        else:row['quality_flags']+=';unexpected_vehicle_identity_requires_review'
    return row


def check_observation(row,inventory,pts):
    sha=row['video_sha256'];index=int(row['frame_index'])
    if sha not in inventory:raise ValueError('Unknown original video identity')
    original=pts[sha].get(index)
    if original is None:raise ValueError('Unknown frame index')
    for key in ['pts_ticks','time_base_num','time_base_den']:
        if int(row[key])!=int(original[key]):raise ValueError('Frame/PTS identity mismatch: '+key)
    if row['coordinate_convention']!='encoded_pixels':raise ValueError('Unexpected pixel convention')
    corners=[row.get(f'corner{i}_{axis}_px','') for i in range(4) for axis in ['x','y']]
    present=[x!='' for x in corners]
    if any(present) and not all(present):raise ValueError('Partly missing quadrilateral')
    if all(present) and not np.isfinite(list(map(float,corners))).all():raise ValueError('Non-finite corners')
    if row['observation_status']=='failed' and any(present):raise ValueError('Failure contains fabricated corners')
    if row['method_version'].startswith('lk_') and row['detected']!='0':raise ValueError('Tracking mislabelled as decoding')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--results',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--time-mapping',type=Path,required=True);p.add_argument('--spatial',type=Path,nargs='+',required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);root=a.results
    inventory=[];qc_by_sha={};pts={};rows=[];observation_summary=[]
    for directory in [root/'media_001',root/'calibration_media_001']:
        for path in sorted(directory.glob('*/media_qc.json')):
            q=load(path)
            if q['decode_status']!='passed':raise ValueError('Incomplete/failed media')
            if q['sha256'] in qc_by_sha:raise ValueError('Duplicate original video identity')
            qc_by_sha[q['sha256']]=q;clip_role,expected=role(q['relative_path'])
            experiment=q['asset_id'][:3] if clip_role=='motion' else ''
            inventory.append(dict(experiment_id=experiment,asset_id=q['asset_id'],
                relative_path='extracted/'+q['asset_id']+'/'+q['relative_path'],sha256=q['sha256'],size_bytes=q['size_bytes'],
                duration_s=q['duration_s'],codec=q['codec'],encoded_width=q['encoded_width'],encoded_height=q['encoded_height'],
                display_width=q['display_width'],display_height=q['display_height'],rotation_ccw_deg=q['rotation'],
                frame_rate_description='avg='+q['average_rate']+'; base='+q['base_rate']+'; use integer PTS',
                pts_source='original decoded frame PTS',time_base_num=q['time_base_num'],time_base_den=q['time_base_den'],
                decoded_frames=q['decoded_frames'],full_decode_status=q['decode_status'],role=clip_role,
                experiment_mapping_status='operator_archive_label' if experiment else 'calibration_identity_verified' if clip_role=='camera_calibration' else 'provisional_role_sequence',
                spatial_reference_status='not_accepted'))
            pts[q['sha256']]={int(r['frame_index']):r for r in csv.DictReader((path.parent/'frame_pts.csv').open(encoding='utf-8'))}
            target=a.output/'frame_pts';target.mkdir(exist_ok=True)
            shutil.copyfile(path.parent/'frame_pts.csv',target/(q['sha256'][:12]+'.csv'))
    if len(inventory)!=18:raise ValueError('Expected 8 motion + 8 reference + 2 calibration originals')
    expected_experiments={f'T{i:02}' for i in range(8,16)}
    if {v['experiment_id'] for v in inventory if v['role']=='motion'}!=expected_experiments:
        raise ValueError('Incomplete formal motion movie roster')
    for path in sorted((root/'observations_001').glob('*/observation_summary.json')):
        summary=load(path);q=qc_by_sha[summary['video_sha256']];clip_role,expected=role(q['relative_path'])
        counts={}
        local=list(csv.DictReader(path.with_name('marker_observations.csv').open(encoding='utf-8')))
        if len(local)!=summary['sampled_frames']*2:raise ValueError('Incomplete observation rows')
        for original in local:
            row=qualify(original,clip_role,expected);check_observation(row,qc_by_sha,pts)
            rows.append(row);key=row['vehicle_id']+'_'+row['observation_status'];counts[key]=counts.get(key,0)+1
        observation_summary.append(dict(video=q['relative_path'],video_sha256=q['sha256'],asset_id=q['asset_id'],
            experiment_id=q['asset_id'][:3] if clip_role=='motion' else '',role=clip_role,
            sampled_frames=summary['sampled_frames'],counts=counts,expected_vehicle_ids=expected))
    if len(observation_summary)!=16:raise ValueError('Expected primary observations for all 16 reference/motion clips')
    rows.sort(key=lambda r:(r['video_sha256'],int(r['frame_index']),int(r['marker_id'])))
    fields=observations.FIELDS+['clip_role','vehicle_expected_in_clip']
    save_csv(a.output/'marker_observations.csv',fields,rows)
    save_csv(a.output/'video_inventory.csv',list(inventory[0]),sorted(inventory,key=lambda x:(x['role'],x['relative_path'])))
    common.write_json(a.output/'observation_summary.json',observation_summary)
    common.write_json(a.output/'media_qc.json',list(qc_by_sha.values()))
    # Merge independently computed clip records, checking shared geometry/version identity.
    transforms=load(a.spatial[0]);seen={x['video_sha256'] for x in transforms['records']}
    for path in a.spatial[1:]:
        extra=load(path)
        for key in ['reference_frame_sha256','geometry_sha256','calibration_sha256','point_annotations']:
            if extra[key]!=transforms[key]:raise ValueError('Spatial stages use different frozen inputs')
        for record in extra['records']:
            if record['video_sha256'] in seen:raise ValueError('Duplicate spatial clip')
            seen.add(record['video_sha256']);transforms['records'].append(record)
    if len(seen)!=16:raise ValueError('Missing per-clip camera/floor relations')
    transforms['operator_car1_front_confirmation']=load(root/'car1_mount_confirmation.json')
    transforms['calibration_video_room_relation']='not_applicable_handheld_calibration_views_not_fixed_room_clips'
    common.write_json(a.output/'frame_transforms.json',transforms)
    timing=load(a.time_mapping)
    if {m['experiment_id'] for m in timing['mappings']}!=expected_experiments:
        raise ValueError('Time mapping lacks a formal experiment')
    for m in timing['mappings']:
        if m.get('model') is not None or m.get('accepted_for_continuous_reference'):
            raise ValueError('Unapproved event candidate promoted to accepted clock mapping')
        int(m['destination_origin_epoch_ns'])
    timing['non_ROS_reference_clips']=[dict(video_sha256=x['sha256'],relative_path=x['relative_path'],
        status='not_applicable_no_corresponding_ROS_experiment',model=None) for x in inventory if not x['experiment_id']]
    common.write_json(a.output/'time_mapping.json',timing)
    validation=load(root/'reference_validation_003/reference_validation.json')
    if validation['approved_scope']!='not_accepted':raise ValueError('Unexpected reference approval')
    validation['observation_summary_file']='observation_summary.json'
    validation['camera_transforms_file']='frame_transforms.json';validation['time_mapping_file']='time_mapping.json'
    common.write_json(a.output/'reference_validation.json',validation)
    # Explicitly separate the manual timing supplement from primary detector/seed-tracker observations.
    manual_path=root/'manual_timing_T12_001/marker_observations.csv'
    manual=list(csv.DictReader(manual_path.open(encoding='utf-8')))
    for r in manual:check_observation(r,qc_by_sha,pts)
    shutil.copyfile(manual_path,a.output/'manual_timing_T12_observations.csv')
    shutil.copyfile(root/'manual_timing_T12_001/observation_summary.json',a.output/'manual_timing_T12_summary.json')
    for exp in ['T14','T15']:
        phase=root/('manual_timing_'+exp+'_001')
        records=list(csv.DictReader((phase/'marker_observations.csv').open(encoding='utf-8')))
        for row in records:check_observation(row,qc_by_sha,pts)
        shutil.copyfile(phase/'marker_observations.csv',a.output/('manual_timing_'+exp+'_observations.csv'))
        shutil.copyfile(phase/'observation_summary.json',a.output/('manual_timing_'+exp+'_summary.json'))
        shutil.copyfile(root/(exp+'_manual_seed.json'),a.output/(exp+'_manual_seed.json'))
    shutil.copyfile(root/'manual_time_candidate_001/T12_manual_event_candidate.json',a.output/'T12_manual_event_candidate.json')
    automatic={r['frame_index']:r for r in rows if r['experiment_id']=='T12' and r['vehicle_id']=='car2' and r['detected']=='1'}
    differences=[]
    for r in manual:
        if r['frame_index'] not in automatic or r['observation_status']!='tracked':continue
        q=automatic[r['frame_index']]
        p1=np.array([[float(r[f'corner{k}_x_px']),float(r[f'corner{k}_y_px'])] for k in range(4)])
        p2=np.array([[float(q[f'corner{k}_x_px']),float(q[f'corner{k}_y_px'])] for k in range(4)])
        differences.append([float(r['video_time_s']),float(np.linalg.norm(p1.mean(0)-p2.mean(0))),float(np.linalg.norm(p1-p2,axis=1).mean())])
    common.write_json(a.output/'manual_timing_pixel_consistency.json',dict(n_overlapping_decoded_frames=len(differences),
        median_centroid_difference_px=float(np.median(np.array(differences)[:,1])),
        median_ordered_corner_difference_px=float(np.median(np.array(differences)[:,2])),
        rows=differences,scope='Detector consistency only, not absolute pixel or metric accuracy',
        manual_pixel_tracks_are_not_metric_reference=True))
    copies={
        'calibration_002/calibration_stability.json':'calibration_stability.json',
        'calibration_002/corner_observations.json':'calibration_corner_observations.json',
        'local_calibration_intake.json':'calibration_original_identity.json',
        'floor_annotations_003/P_annotations.json':'P_annotations.json',
        'car1_mount_confirmation.json':'car1_mount_confirmation.json',
        'manifest_patch_001/coordinator_manifest_patch.json':'coordinator_manifest_patch.json',
        'manifest_patch_001/manifest_proposal.diff':'manifest_proposal.diff',
        'manifest_patch_001/new_video_identities.json':'new_video_identities.json',
        'T12_manual_seed.json':'T12_manual_seed.json',
        'odom_events_001/odom_events.json':'odom_events.json'}
    for source,target in copies.items():shutil.copyfile(root/source,a.output/target)
    diagnostics=[]
    for phase in ['diagnostics_002','diagnostics_003']:
        diagnostics+=load(root/phase/'marker_diagnostic.json')['frames']
    if len({(x['video_sha256'],x['frame_index']) for x in diagnostics})!=48:
        raise ValueError('Expected 3 original-resolution diagnostic frames for all 16 motion/reference clips')
    common.write_json(a.output/'marker_diagnostic.json',dict(frames=diagnostics,scope='Decoding diagnostics, no spatial approval'))
    checks=dict(video_count=len(inventory),primary_observation_rows=len(rows),manual_T12_timing_rows=len(manual),
        all_observation_frame_PTS_identities_checked=True,all_origins_decimal_integer_strings=True,
        no_nonfinite_numeric_corner_fields=True,public_geometry_overwritten=False,
        approved_reference_scope='not_accepted',checkpoints_csv_generated=False,antenna_reference_csv_generated=False,
        code_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[2],text=True).strip())
    common.write_json(a.output/'contract_checks.json',checks)
    print(json.dumps(checks),flush=True)


if __name__=='__main__':main()
