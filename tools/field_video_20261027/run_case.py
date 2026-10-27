"""T10 evidence audit. All outputs are candidates until independent acceptance."""
import argparse
import collections
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import cv2
import numpy as np

import evidence as e

REPO = Path(__file__).resolve().parents[2]
OLD_DOC = REPO / 'docs/field_tests/20261024_25/video_reference_20261026'
BASE_DOC = REPO / 'docs/field_tests/20261024_25'
TOOLS = Path(__file__).resolve().parent
CONFIG = e.load_json(TOOLS / 'case_config.json')
BASELINE = CONFIG['baseline_commit']
sys.path.insert(0, str(REPO / 'tools/field_video_20261026'))
import common as prior_common
import observations as prior_observations
import event_sync as prior_sync
import time_events as prior_time


def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args], text=True, encoding='utf-8').strip()


def copy_new(source, target):
    if Path(target).exists():
        raise FileExistsError(target)
    shutil.copyfile(source, target)


def source_snapshot():
    paths = [*TOOLS.glob('*.py'), TOOLS / 'case_config.json',
             *sorted((REPO / 'tools/field_video_20261026').glob('*.py')),
             REPO / 'tools/field_video_20261026/observation_config.json',
             REPO / 'tools/field_20261024_25/bag_decoder.py']
    return {p.relative_to(REPO).as_posix(): e.sha256(p) for p in paths}


def intake(args):
    args.output.mkdir(parents=True, exist_ok=False)
    if subprocess.run(['git', '-C', str(REPO), 'merge-base', '--is-ancestor', BASELINE, 'HEAD']).returncode:
        raise ValueError('Specified baseline is not an ancestor of this checkout')
    if git('diff', BASELINE, '--', *['docs/field_tests/20261024_25/' + n for n in
                                    ['manifest.json', 'geometry.json', 'RESULT_CONTRACT.md']]):
        raise ValueError('Public input contract/configuration differs from the specified baseline')
    sources = {}
    required = ['RESULT_CONTRACT.md', 'geometry.json', 'RUNBOOK_LOCAL_VIDEO.md',
                'EXPERIMENTS.md', 'SESSION_LOG_ARCHIVE.md', 'manifest.json']
    required += ['video_reference_20261026/' + name for name in
                 ['README.md', 'HANDOFF.md', 'reference_validation.json',
                  'calibration_stability.json', 'frame_transforms.json', 'time_mapping.json',
                  'marker_observations.csv', 'video_inventory.csv', 'source_lineage.json',
                  'P_annotations.json', 'car1_mount_confirmation.json']]
    required += ['t10_closure_20261027/' + name for name in
                 ['operator_evidence.json', 'reference_decision.json', 'HANDOFF.md']]
    for name in required:
        p = BASE_DOC / name
        sources[p.relative_to(REPO).as_posix()] = e.sha256(p)
        if p.suffix == '.json':
            e.load_json(p)
        else:
            p.read_text(encoding='utf-8-sig')
    inventory = e.read_csv(OLD_DOC / 'video_inventory.csv')
    verified_names = {'IMG_7347.MOV', 'IMG_7336.MOV', 'IMG_7337.MOV',
                      *CONFIG['reference_review_videos']}
    availability, verified = [], []
    for row in inventory:
        raw_root = 'calibration_data' if row['role'] == 'calibration' else 'data'
        # The inventory's relative paths retain the original data-root identity.
        if Path(row['relative_path']).name in {'IMG_7336.MOV', 'IMG_7337.MOV'}:
            raw_root = 'calibration_data'
        path = args.legacy / raw_root / row['relative_path']
        size = path.stat().st_size if path.is_file() else None
        check = Path(row['relative_path']).name in verified_names
        digest = e.sha256(path) if check and path.is_file() else None
        if check and (size != int(row['size_bytes']) or digest != row['sha256']):
            raise ValueError('Required input missing or identity mismatch: ' + str(path))
        record = dict(asset_id=row['asset_id'], experiment_id=row['experiment_id'],
                      logical_path=raw_root + '/' + row['relative_path'],
                      expected_sha256=row['sha256'], expected_size_bytes=int(row['size_bytes']),
                      actual_size_bytes=size, sha256_verified_this_run=check,
                      actual_sha256=digest,
                      inherited_full_decode_status=row['full_decode_status'],
                      full_decode_repeated=False,
                      local_status='present_size_matches' if size == int(row['size_bytes']) else 'missing_or_size_differs')
        availability.append(record)
        if check:
            verified.append(record)
            print('SHA verified', Path(row['relative_path']).name, digest, flush=True)
    manifest = e.load_json(BASE_DOC / 'manifest.json')
    bag_entry = next(x for x in manifest['formal_bags'] if x['id'] == 'T10')
    bag = args.legacy / 'bag_data/extracted/bags' / bag_entry['relative_path']
    bag_hash = e.sha256(bag)
    if bag_hash != bag_entry['sha256']:
        raise ValueError('T10 bag SHA mismatch')
    pts_path = args.legacy / 'results/media_001/T10_video__IMG_7347/frame_pts.csv'
    pts = e.read_csv(pts_path)
    all_obs = e.read_csv(OLD_DOC / 'marker_observations.csv')
    obs = [r for r in all_obs if r['experiment_id'] == 'T10']
    pts_check = e.validate_pts(obs, pts)
    if len(obs) != 388 or len(pts) != 2903:
        raise ValueError('Unexpected T10 input counts')
    copy_new(pts_path, args.output / 'T10_frame_pts.csv')
    copy_new(OLD_DOC / 'marker_observations.csv', args.output / 'marker_observations.csv')
    for r in inventory:
        r['v2_review_status'] = 'SHA_verified_targeted_review' if Path(r['relative_path']).name in verified_names else 'PR49_reused_no_rerun'
    e.write_csv(args.output / 'video_inventory.csv', inventory)
    # This older snapshot is public evidence about the completed upload/decode
    # stage; RUNBOOK_LOCAL_VIDEO upload wording is historical, not current QC.
    e.write_json(args.output / 'prior_status.json', {
        'verified_via': 'GitHub connector get_pr_info and fetch_pr_comments, 2026-10-27',
        'url': 'https://github.com/phyllis-TANG/uwb-coop-localization-ros1/pull/49',
        'merged': True, 'head_sha': CONFIG['prior_commit'],
        'merge_commit_sha': '7128abc769121f1f39c3959ce195ac545656c86c',
        'decoded_original_videos': 18, 'decoded_frames': 41381,
        'repeat_full_media_audit': False, 'checkerboards_on_release': False,
        'checkerboards_locally_present_and_verified': True})
    sources[pts_path.relative_to(args.legacy).as_posix()] = e.sha256(pts_path)
    for name in ['T10_car1_odom.csv', 'T10_car2_odom.csv', 'T10_car1_commands.csv', 'odom_events.json']:
        p = args.legacy / 'results/odom_events_001' / name
        sources[p.relative_to(args.legacy).as_posix()] = e.sha256(p)
    e.write_json(args.output / 'input_evidence.json', {
        'schema_version': 1, 'baseline_commit': BASELINE, 'source_sha256': sources,
        'raw_media': availability,
        'bag': {'logical_path': 'bag_data/extracted/bags/' + bag_entry['relative_path'],
                'sha256': bag_hash, 'size_bytes': bag.stat().st_size},
        'pts_validation': pts_check,
        'raw_location_policy': 'Legacy I: copies reused read-only in place; no copies to data, downloads or extraction',
        'all_raw_inputs_ready': all(x['local_status'] == 'present_size_matches' for x in availability),
        'acceptance_inputs_ready': False})
    e.write_json(args.output / 'checkpoint_001.json', {
        'schema_version': 1, 'phase': 'input_and_identity_complete',
        'repository': str(REPO), 'branch': git('branch', '--show-current'),
        'HEAD': git('rev-parse', 'HEAD'), 'worktree_status': git('status', '--porcelain=v1'),
        'free_bytes_I': shutil.disk_usage('I:\\').free,
        'TEMP': os.environ.get('TEMP'), 'TMP': os.environ.get('TMP'),
        'pts': pts_check, 'full_decode_reruns': 0,
        'confirmed_missing': ['actual P/Q survey and uncertainty',
                              'validated imaging and mount transforms',
                              'independently bounded video/ROS synchronization'],
        'next': ['targeted original frames', 'conditional geometry and sensitivity',
                 'original T10 odom/cmd event verification', 'contract and gap-table packaging']})


def exact_frame(path, tick):
    import av
    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        stream.codec_context.thread_count = 2
        container.seek(tick, stream=stream, backward=True, any_frame=False)
        decoded = 0
        for frame in container.decode(stream):
            decoded += 1
            if frame.pts == tick:
                return frame.to_ndarray(format='bgr24'), {
                    'pts_ticks': frame.pts, 'time_base_num': frame.time_base.numerator,
                    'time_base_den': frame.time_base.denominator,
                    'rotation_ccw_deg': frame.rotation,
                    'decoded_frames_after_seek': decoded, 'decoder': 'PyAV ' + av.__version__}
            if frame.pts is not None and frame.pts > tick:
                break
    raise ValueError('Exact PTS not found: ' + str(tick))


def diagnose(args):
    temp = args.temp / 'raw_samples_001'
    temp.mkdir(parents=True, exist_ok=False)
    out = args.output / 'diagnostics_001'
    out.mkdir(exist_ok=False)
    pts = e.read_csv(args.output / 'T10_frame_pts.csv')
    prior_rows = e.read_csv(args.output / 'marker_observations.csv')
    old_by_frame = {(int(r['frame_index']), r['vehicle_id']): r for r in prior_rows if r['experiment_id'] == 'T10'}
    detector_config = e.load_json(REPO / 'tools/field_video_20261026/observation_config.json')
    ds = prior_observations.detectors(detector_config)
    videos = e.read_csv(args.output / 'video_inventory.csv')
    sample_sources = []
    qc_dir = args.legacy / 'results/media_001/T10_video__IMG_7347'
    qc = e.load_json(qc_dir / 'media_qc.json')
    saved = {f['frame_index']: f for f in qc['diagnostic_frames']}
    for target in CONFIG['t10_review_target_s']:
        frame = next(x for x in pts if float(x['video_time_s']) + 1e-9 >= target)
        index = int(frame['frame_index'])
        if index in saved:
            f = saved[index]
            path = qc_dir / f['path']
            if e.sha256(path) != f['sha256']:
                raise ValueError('Existing lossless diagnostic frame SHA mismatch')
            meta = dict(frame, source_kind='existing_original_4K_lossless_frame',
                        decoded_frames_after_seek=0, rotation_ccw_deg=qc['rotation'])
        else:
            image, meta = exact_frame(args.legacy / 'data/extracted/T10_video/IMG_7347.MOV', int(frame['pts_ticks']))
            path = temp / ('T10_frame_%06d.png' % index)
            if not cv2.imwrite(str(path), image):
                raise OSError('Could not save selected frame')
            meta.update(frame_index=index, video_time_s=float(frame['video_time_s']),
                        source_kind='exact_original_PTS_seek')
        sample_sources.append(('IMG_7347.MOV', frame, path, meta))
    for video in CONFIG['reference_review_videos']:
        stem = Path(video).stem
        folder = args.legacy / ('results/media_001/camera_reference__' + stem)
        info = e.load_json(folder / 'media_qc.json')
        f = info['diagnostic_frames'][0]
        path = folder / f['path']
        if e.sha256(path) != f['sha256']:
            raise ValueError('Existing P/Q original-frame SHA mismatch')
        sample_sources.append((video, f, path, dict(f, source_kind='existing_original_4K_lossless_frame',
                                                  decoded_frames_after_seek=0, rotation_ccw_deg=info['rotation'])))
    manual_roi = {'IMG_7365.MOV': [1350, 690, 1900, 960],
                  'IMG_7366.MOV': [2500, 650, 3060, 950],
                  'IMG_7367.MOV': [1800, 950, 2390, 1270]}
    records, rows, panels, profiles = [], [], [], []
    fields = list(prior_rows[0]) + ['source_stage', 'source_frame_png_sha256']
    for video, f, path, meta in sample_sources:
        image = cv2.imread(str(path))
        if image is None or image.shape[:2] != (2160, 3840):
            raise ValueError('Expected an unscaled original 3840x2160 frame')
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        found, rejected = prior_observations.decode(gray, ds)
        vinfo = next(x for x in videos if Path(x['relative_path']).name == video)
        index = int(f['frame_index'])
        frame_sha = e.sha256(path)
        rec = dict(video=video, video_sha256=vinfo['sha256'], frame_index=index,
                   pts_ticks=int(f['pts_ticks']), time_base_num=int(f['time_base_num']),
                   time_base_den=int(f['time_base_den']), video_time_s=float(f['video_time_s']),
                   frame_png_sha256=frame_sha, encoded_size_wh=[3840, 2160],
                   pixel_representation='BGR24 lossless PNG then cv2.COLOR_BGR2GRAY; prior extraction used PyAV gray',
                   source=meta, local_frame_path=str(path), rejected_candidate_counts=rejected,
                   decoded_marker_ids=sorted(found), coordinate_convention='encoded_pixels')
        annotated = image.copy()
        expected = [0, 1] if video == 'IMG_7347.MOV' else ([1] if video in manual_roi else [])
        for marker in expected:
            base = dict(experiment_id=vinfo['experiment_id'], video_sha256=vinfo['sha256'],
                        frame_index=index, pts_ticks=rec['pts_ticks'], time_base_num=rec['time_base_num'],
                        time_base_den=rec['time_base_den'], video_time_s=rec['video_time_s'], coordinate_convention='encoded_pixels')
            corners, method = found.get(marker, (None, 'failed_v2'))
            row = prior_observations.row_state(base, marker, corners, method)
            row.update(source_stage='targeted_4K_recheck_v2', source_frame_png_sha256=frame_sha,
                       clip_role=vinfo['role'], vehicle_expected_in_clip=1)
            rows.append(row)
            if corners is not None:
                q = np.round(corners).astype(np.int32)
                cv2.polylines(annotated, [q], True, (0, 255, 0), 3)
                for k, xy in enumerate(q):
                    cv2.putText(annotated, str(k), tuple(xy), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 0, 255), 2)
                old = old_by_frame.get((index, row['vehicle_id'])) if video == 'IMG_7347.MOV' else None
                comparison = None
                if old and old['observation_status'] == 'decoded':
                    old_q = np.array([[float(old[f'corner{k}_x_px']), float(old[f'corner{k}_y_px'])] for k in range(4)])
                    comparison = {'per_corner_difference_px': np.linalg.norm(corners - old_q, axis=1).tolist(),
                                  'meaning': 'extraction representation/version comparison, not ground-truth error'}
                profiles.append(dict(video=video, frame_index=index, vehicle_id=row['vehicle_id'],
                                     source_frame_png_sha256=frame_sha,
                                     corners_encoded_px=corners.tolist(),
                                     prior_pixel_comparison=comparison,
                                     edge_profiles=e.edge_profiles(gray, corners)))
        overview = cv2.resize(annotated, (640, 360), interpolation=cv2.INTER_AREA)
        title = np.full((36, 640, 3), 245, np.uint8)
        cv2.putText(title, f'{Path(video).stem} frame {index} PTS {rec["pts_ticks"]}  IDs {sorted(found)}',
                    (8, 24), cv2.FONT_HERSHEY_SIMPLEX, .49, (0, 0, 0), 1)
        panels.append(np.vstack([title, overview]))
        if video in manual_roi:
            x0, y0, x1, y1 = manual_roi[video]
            crop = image[y0:y1, x0:x1]
            crop_path = out / (Path(video).stem + '_Car2_native_crop.png')
            cv2.imwrite(str(crop_path), crop)
            rec['manual_ROI'] = {'xyxy_encoded_px': manual_roi[video],
                                 'source': 'analyst visual selection from original full frame for inspection only',
                                 'corner_annotation': False, 'metric_use': False,
                                 'crop_sha256': e.sha256(crop_path)}
        records.append(rec)
        print('Reviewed exact 4K sample', video, index, 'IDs', sorted(found), flush=True)
    if len(panels) % 2:
        panels.append(np.full_like(panels[0], 245))
    sheet = np.vstack([np.hstack(panels[i:i + 2]) for i in range(0, len(panels), 2)])
    cv2.imwrite(str(out / 'original_frame_contact_sheet.jpg'), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    e.write_csv(out / 'sample_recheck_observations.csv', rows, fields)
    e.write_json(out / 'edge_profiles.json', {'method': e.edge_profiles.__doc__, 'records': profiles,
                                             'spatial_accuracy_passed': False,
                                             'board_rigidity_verified': False})
    e.write_json(out / 'selected_frames_local.json', records)
    shared = [{k: v for k, v in r.items() if k != 'local_frame_path'} for r in records]
    e.write_json(out / 'selected_frames.json', shared)
    summary = {'schema_version': 1, 'original_4K_frames_reviewed': len(records),
               'new_targeted_decoded_frames_including_preroll': sum(int(r['source']['decoded_frames_after_seek']) for r in records),
               'full_video_decode_repeated': False, 'tracker_runs': 0, 'manual_corner_annotations': 0,
               'manual_inspection_ROIs': len(manual_roi),
               'counts': dict(collections.Counter((r['experiment_id'] or 'Q') + '_' + r['vehicle_id'] + '_' + r['observation_status'] for r in rows)),
               'coverage_scope': 'Only these selected frames; the complete 2Hz observations are inherited from PR49',
               'Q_metric_errors_used_for_detector_selection': False, 'fallback_detector': 'fixed PR49 recovery preset only'}
    e.write_json(out / 'extraction_summary.json', summary)
    top = BASE_DOC / 'evidence/car1_top.jpg'
    c, ids, _ = ds[0].detectMarkers(cv2.imread(str(top)))
    if ids is None or 0 not in ids:
        raise ValueError('Car1 installation image ID0 could not be decoded')
    q = c[list(ids.ravel()).index(0)].reshape(4, 2)
    e.write_json(out / 'car1_front_evidence.json', {
        'operator_current': CONFIG['operator_confirmation'],
        'prior_operator_and_inference': e.load_json(OLD_DOC / 'car1_mount_confirmation.json'),
        'installation_image': top.relative_to(REPO).as_posix(), 'image_sha256': e.sha256(top),
        'automatically_decoded_ID': 0, 'corners_encoded_px': q.tolist(),
        'analyst_visual_read': 'Printed CAR 1 title lies beyond edge corners 0-1 in the original installation image; therefore title side is canonical marker +Y under the declared corner convention',
        'new_conditional_relation': 'body +X toward canonical marker +Y, from current explicit user title-edge statement and this installation-image reading',
        'full_3D_rotation_measured': False, 'angle_uncertainty_rad': None,
        'public_geometry_changed': False, 'selected_using_Q_or_fusion': False,
        'previous_opposite_direction_retained_as_sensitivity': True})


def corners_from_row(row):
    return np.array([[float(row[f'corner{k}_x_px']), float(row[f'corner{k}_y_px'])] for k in range(4)])


def stats(values):
    a = np.asarray(values, float)
    return {'min': float(a.min()), 'median': float(np.median(a)), 'max': float(a.max())}


def geometry(args):
    transform = e.load_json(OLD_DOC / 'frame_transforms.json')
    calibration = e.load_json(OLD_DOC / 'calibration_stability.json')
    geo = e.load_json(BASE_DOC / 'geometry.json')
    if abs(geo['marker']['black_border_side_m'] - .144) > 1e-12:
        raise ValueError('Expected measured 144mm black border')
    if not np.allclose(calibration['pitch_xy_m'], geo['checkerboard']['pitch_xy_m'], rtol=0, atol=1e-12):
        raise ValueError('Checkerboard pitch differs from geometry')
    t10 = next(x for x in transform['records'] if x['asset_id'] == 'T10_video')
    first = t10['clips'][0]
    if first['frame_index'] != 15:
        raise ValueError('Frozen first-pose sample policy differs')
    rows = [x for x in e.read_csv(args.output / 'marker_observations.csv') if x['experiment_id'] == 'T10']
    models = calibration['models']
    primary = CONFIG['primary_camera_candidate']
    candidate_rows, sensitivities, square_fits = [], [], []
    review = e.load_json(args.output / 'diagnostics_001/edge_profiles.json')['records']
    # Choose initial/middle/post-motion observation samples solely by PTS.
    sample_indices = [int(min(rows, key=lambda x: abs(float(x['video_time_s']) - target))['frame_index'])
                      for target in [.5, 48.5, 75.0]]
    sample_keys = set(sample_indices)
    for row in rows:
        if row['observation_status'] != 'decoded':
            raise ValueError('T10 geometry expects inherited decoded observations; do not silently drop failures')
        vehicle = row['vehicle_id']
        mount = geo['mounts'][vehicle]
        height = mount['black_border_center_height_m']
        q = corners_from_row(row)
        computed = {}
        for name in CONFIG['camera_sensitivity_candidates']:
            model = models[name]
            T = first['room_pose_candidates'][name]['T_room_camera']
            center, vertices, heading = e.conditional_geometry(q, model['K'], model['D'], T, height)
            edges = np.linalg.norm(np.roll(vertices, -1, axis=0) - vertices, axis=1)
            antenna = e.antenna_candidate(center, heading, mount['marker_center_to_antenna_body_aligned_xyz_m']) if vehicle == 'car1' else None
            computed[name] = (center, vertices, heading, antenna)
            candidate_rows.append(dict(experiment_id='T10', video_sha256=row['video_sha256'],
                vehicle_id=vehicle, frame_index=row['frame_index'], pts_ticks=row['pts_ticks'],
                time_base_num=row['time_base_num'], time_base_den=row['time_base_den'],
                video_time_s=row['video_time_s'], camera_candidate=name, camera_pose_source_frame=15,
                marker_x_m=float(center[0]), marker_y_m=float(center[1]), marker_z_m=float(center[2]),
                antenna_x_m=float(antenna[0]) if antenna is not None else '',
                antenna_y_m=float(antenna[1]) if antenna is not None else '',
                antenna_z_m=float(antenna[2]) if antenna is not None else '',
                assumed_body_yaw_rad=heading if vehicle == 'car1' else '',
                edge0_m=float(edges[0]), edge1_m=float(edges[1]), edge2_m=float(edges[2]), edge3_m=float(edges[3]),
                metric_reference_valid=0, approved_scope='not_accepted',
                assumptions='nominal_P;candidate_intrinsics;fixed_first_pose;reported_height;horizontal_rigid_plane;' +
                    ('current_user_title_edge_forward' if vehicle == 'car1' else 'Car2_body_rotation_unknown_antenna_blank')))
        if int(row['frame_index']) not in sample_keys:
            continue
        center, vertices, heading, antenna = computed[primary]
        model = models[primary]
        T = first['room_pose_candidates'][primary]['T_room_camera']
        for name, (point, _, _, _) in computed.items():
            sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='camera_model',
                assumed_value=name, delta_marker_xy_m=float(np.linalg.norm(point[:2] - center[:2])),
                note=CONFIG['sensitivity_policy']))
        for dh in CONFIG['height_sensitivity_delta_m']:
            point, _, _ = e.conditional_geometry(q, model['K'], model['D'], T, height + dh)
            sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='board_height_delta_m',
                assumed_value=dh, delta_marker_xy_m=float(np.linalg.norm(point[:2] - center[:2])), note=CONFIG['sensitivity_policy']))
        ground, _, _ = e.conditional_geometry(q, model['K'], model['D'], T, 0.)
        sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='wrong_ground_plane',
            assumed_value=0, delta_marker_xy_m=float(np.linalg.norm(ground[:2] - center[:2])),
            note='Diagnostic of applying a ground plane to an elevated marker; not an uncertainty estimate'))
        for pose in t10['clips']:
            point, _, _ = e.conditional_geometry(q, model['K'], model['D'], pose['room_pose_candidates'][primary]['T_room_camera'], height)
            sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='existing_per_clip_pose_sample',
                assumed_value=pose['frame_index'], delta_marker_xy_m=float(np.linalg.norm(point[:2] - center[:2])),
                note='Observed registration/model variation only; floor homography is not applied to marker pixels'))
        pixel_changes = []
        for k in range(4):
            for axis in range(2):
                for sign in [-1, 1]:
                    perturb = q.copy()
                    perturb[k, axis] += sign * CONFIG['pixel_sensitivity_delta_px']
                    point, _, angle = e.conditional_geometry(perturb, model['K'], model['D'], T, height)
                    if vehicle == 'car1':
                        point = e.antenna_candidate(point, angle, mount['marker_center_to_antenna_body_aligned_xyz_m'])
                        delta = np.linalg.norm(point[:2] - antenna[:2])
                    else:
                        delta = np.linalg.norm(point[:2] - center[:2])
                    pixel_changes.append(float(delta))
        sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='one_corner_one_axis_1px_max',
            assumed_value=CONFIG['pixel_sensitivity_delta_px'], delta_marker_xy_m=max(pixel_changes),
            note='Max of 16 deterministic perturbations; Car1 includes lever arm, Car2 is marker-only; not a bound'))
        if vehicle == 'car1':
            for angle in CONFIG['car1_heading_sensitivity_delta_deg']:
                point = e.antenna_candidate(center, heading + np.deg2rad(angle), mount['marker_center_to_antenna_body_aligned_xyz_m'])
                sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='body_heading_delta_deg',
                    assumed_value=angle, delta_marker_xy_m=float(np.linalg.norm(point[:2] - antenna[:2])),
                    note='Current title-edge direction plus hypothetical angle; 180deg preserves the old opposite inference'))
        else:
            for angle in CONFIG['car2_unknown_heading_sweep_deg']:
                point = e.antenna_candidate(center, np.deg2rad(angle), mount['marker_center_to_antenna_body_aligned_xyz_m'])
                sensitivities.append(dict(vehicle_id=vehicle, frame_index=row['frame_index'], kind='unknown_body_yaw_example_deg',
                    assumed_value=angle, delta_marker_xy_m=float(np.linalg.norm(point[:2] - center[:2])),
                    note='Example yaw locus under flat-body assumption; no angle selected; not a measured or bounded reference'))
        # PnP fits all four corners: even small residuals do not validate board
        # rigidity, camera calibration, or independent room-space accuracy.
        result = cv2.solvePnPGeneric(prior_common.marker_object_points(.144), q,
                                    np.asarray(model['K']), np.asarray(model['D']), flags=cv2.SOLVEPNP_IPPE_SQUARE)
        alternatives = []
        for rv, tv in zip(result[1], result[2]):
            projected = cv2.projectPoints(prior_common.marker_object_points(.144), rv, tv,
                                         np.asarray(model['K']), np.asarray(model['D']))[0].reshape(4, 2)
            R = cv2.Rodrigues(rv)[0]
            depth = (prior_common.marker_object_points(.144) @ R.T + tv.ravel())[:, 2]
            alternatives.append({'rvec_camera_marker': rv.ravel().tolist(), 'tvec_camera_marker_m': tv.ravel().tolist(),
                                 'positive_depth_all_corners': bool(np.all(depth > 0)),
                                 'fit_reprojection_rms_px': float(np.sqrt(np.mean(np.sum((projected - q) ** 2, axis=1))))})
        square_fits.append({'vehicle_id': vehicle, 'frame_index': row['frame_index'],
                           'model': primary, 'solutions': alternatives, 'solution_selected': None,
                           'independent_board_flatness_or_accuracy_test': False})
    e.write_csv(args.output / 'T10_candidate_geometry.csv', candidate_rows)
    e.write_csv(args.output / 'T10_sensitivity.csv', sensitivities)
    e.write_json(args.output / 'T10_square_pose_diagnostics.json', square_fits)
    calibration_review = {'source_sha256': e.sha256(OLD_DOC / 'calibration_stability.json'),
        'recalibration_run': False, 'checkerboard_pitch_xy_m': geo['checkerboard']['pitch_xy_m'],
        'intrinsics_approved': False, 'models': {
            name: {'n_views': m['n_views'], 'rms_px': m['rms_px'], 'fx_px': m['K'][0][0],
                   'fy_px': m['K'][1][1], 'cx_px': m['K'][0][2], 'cy_px': m['K'][1][2]}
            for name, m in models.items()},
        '7337_interleaved_fx_relative_difference': abs(models['IMG_7337_interleaved_even']['K'][0][0] - models['IMG_7337_interleaved_odd']['K'][0][0]) / models['IMG_7337_all']['K'][0][0],
        '7336_to_7337_fx_ratio': models['IMG_7336_all']['K'][0][0] / models['IMG_7337_all']['K'][0][0],
        'model_choice': primary, 'choice_source': 'Preserved PR49 pre-Q primary; all other models sensitivity only',
        'limitations': ['RMS and split differences are fit diagnostics, not independent spatial accuracy',
                        'Same 4K dimensions do not establish lens, stabilization or processing equivalence',
                        'Handheld checkerboard flatness and measurement uncertainty remain unknown']}
    e.write_json(args.output / 'calibration_review.json', calibration_review)
    summary = {'schema_version': 1, 'experiment_id': 'T10', 'approved_scope': 'not_accepted',
        'conditional_rows': len(candidate_rows), 'actual_independent_position_error_m': None,
        'formal_T_room_camera': None, 'uncertainty_model': None,
        'sampling_policy': CONFIG['camera_pose_sample_policy'],
        'fit_point_ids': ['P1', 'P2', 'P3', 'P4'], 'fit_coordinate_status': 'instructed_not_precisely_surveyed',
        'independent_check_ids': ['Q1', 'Q2', 'Q3'], 'Q_used_for_fit_or_model_selection': False,
        'per_vehicle': {}, 'spatial_tolerance_m': None,
        'floor_registration_note': 'T10 per-clip nominal P pixels propagated through existing floor-only registration. At least P2 lies outside the T10 image; extrapolation and distortion remain unvalidated. Ground homography never acts on elevated marker pixels.',
        'per_clip_registration': [{'frame_index': s['frame_index'], 'video_time_s': s['video_time_s'],
                                   'median_floor_transfer_residual_px': s['registration']['median_transfer_residual_px'],
                                   'p95_floor_transfer_residual_px': s['registration']['p95_transfer_residual_px'],
                                   'P_fit_reprojection_rms_px': s['room_pose_candidates'][primary]['fit_reprojection_rms_px']}
                                  for s in t10['clips']],
        'centering_change_from_PR49': 'Diagonal intersection after per-corner undistortion; PR49 formed a pixel-space homography before undistortion. This is a model-consistent candidate computation, not an accuracy validation.'}
    for vehicle in ['car1', 'car2']:
        subset = [r for r in candidate_rows if r['vehicle_id'] == vehicle and r['camera_candidate'] == primary]
        edge = [r[f'edge{k}_m'] for r in subset for k in range(4)]
        kinds = {}
        for kind in sorted({r['kind'] for r in sensitivities if r['vehicle_id'] == vehicle}):
            kinds[kind] = stats([r['delta_marker_xy_m'] for r in sensitivities if r['vehicle_id'] == vehicle and r['kind'] == kind])
        summary['per_vehicle'][vehicle] = {'observed_frames': len(subset), 'conditional_edge_length_m': stats(edge),
             'reported_marker_height_m': geo['mounts'][vehicle]['black_border_center_height_m'],
             'reported_antenna_height_m': geo['mounts'][vehicle]['antenna_reference_height_m'],
             'sensitivity_xy_m': kinds,
             'antenna_candidate_computed': vehicle == 'car1',
             'antenna_rotation_status': 'current_operator_title_edge_relation_only_full_angle_unknown' if vehicle == 'car1' else 'unknown_not_zero_no_antenna_position',
             'actual_position_error_m': None, 'total_error_bound_m': None}
    summary['car2_flat_yaw_locus_radius_m'] = float(np.linalg.norm(geo['mounts']['car2']['marker_center_to_antenna_body_aligned_xyz_m'][:2]))
    e.write_json(args.output / 'T10_geometry_summary.json', summary)
    transform['version'] = 'video_reference_20261027_v2'
    transform['baseline_commit'] = BASELINE
    transform['operator_car1_front_confirmation_PR49'] = transform['operator_car1_front_confirmation']
    transform['operator_car1_front_confirmation'] = e.load_json(args.output / 'diagnostics_001/car1_front_evidence.json')
    transform['T10_v2_audit'] = summary
    transform['candidate_geometry_file'] = 'T10_candidate_geometry.csv'
    transform['candidate_geometry_is_accepted_reference'] = False
    e.write_json(args.output / 'frame_transforms.json', transform)
    print('Conditional geometry rows', len(candidate_rows), '; accepted spatial rows 0', flush=True)


def motion_at_threshold(rows, threshold):
    t = np.array([float(r['video_time_s']) for r in rows])
    xy = np.array([corners_from_row(r).mean(axis=0) for r in rows])
    speed = np.r_[np.nan, np.linalg.norm(np.diff(xy, axis=0), axis=1) / np.diff(t)]
    smooth = speed.copy()
    for i in range(1, len(t) - 1):
        if np.isfinite(speed[i - 1:i + 2]).all():
            smooth[i] = np.median(speed[i - 1:i + 2])
    runs = prior_sync.merge_intervals(prior_time.intervals(t, np.isfinite(smooth) & (smooth > threshold),
                                          min_duration=1., bridge_gap=.8), gap=1., min_duration=1.5)
    events = []
    for run in runs:
        before = (t >= run['start_s'] - 1.5) & (t <= run['start_s'] - .5) & np.isfinite(smooth)
        after = (t >= run['end_s'] + .5) & (t <= run['end_s'] + 1.5) & np.isfinite(smooth)
        for kind, key, guard in [('motion_start', 'start_s', before), ('motion_end', 'end_s', after)]:
            if guard.sum() >= 2 and np.median(smooth[guard]) < threshold:
                index = int(np.argmin(abs(t - run[key])))
                neighbour = max(0, index - 1) if kind == 'motion_start' else min(len(t) - 1, index + 1)
                ids = sorted([index, neighbour])
                events.append({'vehicle_id': rows[0]['vehicle_id'], 'kind': kind, 'time_s': run[key],
                               'observed_frame_indices': [int(rows[x]['frame_index']) for x in ids],
                               'observed_pts_ticks': [int(rows[x]['pts_ticks']) for x in ids],
                               'sample_bracket_s': [float(t[x]) for x in ids],
                               'physical_onset_or_stop_time_bound': False})
    return events


def timing(args):
    from bag_decoder import load_bag, Decoder
    inputs = e.load_json(args.output / 'input_evidence.json')
    bag = args.legacy / inputs['bag']['logical_path']
    if e.sha256(bag) != inputs['bag']['sha256']:
        raise ValueError('Bag changed after intake')
    connections, messages = load_bag(bag)
    origin = min(t for _, t, _ in messages)
    decoders = {}
    vehicles = {v: {'odom': [], 'commands': []} for v in ['car1', 'car2']}
    exported = []
    for record_index, (cid, stamp, raw) in enumerate(messages):
        connection = connections[cid]
        topic = connection['topic']
        if topic not in ['/car1/odom', '/car2/odom', '/car1/cmd_vel', '/car2/cmd_vel']:
            continue
        if cid not in decoders:
            decoders[cid] = Decoder(connection['type'], connection['definition'])
        msg = decoders[cid].decode(raw, connection['type'])
        vehicle = topic.split('/')[1]
        row = dict(record_index=record_index, receive_epoch_ns=str(stamp), receive_relative_s=(stamp - origin) / 1e9)
        extra = {}
        if topic.endswith('/odom'):
            pose = msg['pose']['pose']
            header = msg['header']['stamp']
            row.update(header_epoch_ns=str(header['secs'] * 10 ** 9 + header['nsecs']),
                       x_m=pose['position']['x'], y_m=pose['position']['y'],
                       yaw_rad=prior_time.yaw(pose['orientation']),
                       frame_id=msg['header']['frame_id'], child_frame_id=msg['child_frame_id'])
            extra = {'header_seq': msg['header']['seq'], 'position_z_driver_diagnostic': pose['position']['z'],
                     'position_z_semantics': 'driver_yaw_related_not_height' if vehicle == 'car2' else 'raw_diagnostic_not_used_as_room_height'}
            vehicles[vehicle]['odom'].append(row)
        else:
            row.update(linear_x=msg['linear']['x'], angular_z=msg['angular']['z'])
            vehicles[vehicle]['commands'].append(row)
        exported.append(dict(row, vehicle_id=vehicle, topic=topic, bag_sha256=inputs['bag']['sha256'], **extra))
    fields = ['vehicle_id', 'topic', 'bag_sha256', 'record_index', 'header_seq', 'receive_epoch_ns',
              'header_epoch_ns', 'receive_relative_s', 'x_m', 'y_m', 'yaw_rad', 'frame_id', 'child_frame_id',
              'linear_x', 'angular_z', 'position_z_driver_diagnostic', 'position_z_semantics']
    e.write_csv(args.output / 'T10_original_odom_cmd.csv', exported, fields)
    compared = 0
    for vehicle, data in vehicles.items():
        for kind, rows in data.items():
            if not rows:
                continue
            prior = e.read_csv(args.legacy / f'results/odom_events_001/T10_{vehicle}_{kind}.csv')
            if len(rows) != len(prior):
                raise ValueError('Raw/previous timing export count differs')
            for actual, old in zip(rows, prior):
                for key, value in actual.items():
                    if isinstance(value, float):
                        if not np.isfinite(value) or abs(value - float(old[key])) > 1e-12:
                            raise ValueError('Raw/previous export numerical mismatch: ' + key)
                    elif str(value) != old[key]:
                        raise ValueError('Raw/previous record identity mismatch: ' + key)
                compared += 1
    summary = {'schema_version': 1, 'experiment_id': 'T10', 'bag_sha256': inputs['bag']['sha256'],
               'bag_receive_origin_epoch_ns': str(origin), 'raw_records_verified_against_PR49': compared,
               'total_bag_message_records': len(messages), 'raw_export_sha256': e.sha256(args.output / 'T10_original_odom_cmd.csv'),
               'odom_command_events': {}, 'accepted_model': None, 'approved_scope': 'not_accepted',
               'total_offset_uncertainty_s': None, 'drift_uncertainty': None, 'total_time_error_bound_s': None,
               'fusion_or_UWB_estimates_used': False, 'event_selection': 'same Car1 unique translational bout, guarded image onset/end; no filename clocks or planned sleeps',
               'event_ambiguity': 'Two event labels and ordering support a T10 candidate; physical onset/stop, latency and drift remain unbounded. Stationary Car2 adds no independent clock event.',
               'original_sampling_clock_semantics': 'bag receive clock only; header retained separately, not assumed simultaneous'}
    raw_events = {}
    for vehicle, data in vehicles.items():
        odom = data['odom']
        t = np.array([r['receive_relative_s'] for r in odom])
        xy = np.array([[r['x_m'], r['y_m']] for r in odom])
        index = np.minimum(np.searchsorted(t, t - .25), np.arange(len(t)))
        delta = t - t[index]
        speed = np.divide(np.linalg.norm(xy - xy[index], axis=1), delta,
                          out=np.zeros(len(t)), where=delta > 0)
        runs = prior_time.intervals(t, speed > .005)
        commands = data['commands']
        ct = [r['receive_relative_s'] for r in commands]
        command_runs = prior_time.intervals(ct, [abs(r['linear_x']) > 1e-6 for r in commands])
        event_records = []
        for run in runs:
            for key in ['start_s', 'end_s']:
                row = min(odom, key=lambda r: abs(r['receive_relative_s'] - run[key]))
                event_records.append({'kind': key, **row})
        summary['odom_command_events'][vehicle] = {'odom_samples': len(odom), 'command_samples': len(commands),
            'odom_translation_intervals': runs, 'nonzero_linear_command_intervals': command_runs,
            'raw_odom_boundary_records': event_records,
            'header_receive_delta_s_range': stats([(int(r['receive_epoch_ns']) - int(r['header_epoch_ns'])) / 1e9 for r in odom]),
            'header_receive_delta_is_latency_calibration': False}
        raw_events[vehicle] = prior_sync.boundaries(prior_sync.merge_intervals(runs), vehicle)
        if runs and command_runs:
            summary['odom_command_events'][vehicle]['odom_threshold_minus_command_boundary_s'] = {
                'start': runs[0]['start_s'] - command_runs[0]['start_s'],
                'end': runs[-1]['end_s'] - command_runs[-1]['end_s'],
                'meaning': 'Observed different event definitions in the same receive clock, not a calibrated camera offset'}
    all_observations = e.read_csv(args.output / 'marker_observations.csv')
    obs = [r for r in all_observations if r['experiment_id'] == 'T10']
    image_events = []
    image_motions = {}
    for vehicle in ['car1', 'car2']:
        rows = [r for r in obs if r['vehicle_id'] == vehicle]
        motion = prior_sync.image_motion(rows)
        image_motions[vehicle] = motion
        image_events += motion['events']
    ros_events = raw_events['car1'] + raw_events['car2']
    candidate = prior_sync.align(image_events, ros_events)
    mappings = e.load_json(OLD_DOC / 'time_mapping.json')
    old = next(x for x in mappings['mappings'] if x['experiment_id'] == 'T10')
    if candidate['candidate_model'] != old['candidate_model'] or str(origin) != old['destination_origin_epoch_ns']:
        raise ValueError('Independent reconstruction disagrees with inherited T10 candidate')
    summary['reproduced_PR49_candidate'] = candidate
    summary['video_events_with_sampling_records'] = motion_at_threshold([r for r in obs if r['vehicle_id'] == 'car1'], 3.)
    summary['full_video_PTS_support'] = {k: e.read_csv(args.output / 'T10_frame_pts.csv')[i][k]
                                      for k, i in [('pts_ticks', 0)]}
    ledger = e.read_csv(args.output / 'T10_frame_pts.csv')
    summary['full_video_PTS_support'] = {'first': ledger[0], 'last': ledger[-1], 'frames': len(ledger)}
    summary['observed_marker_PTS_support'] = {'first_ticks': int(obs[0]['pts_ticks']),
        'last_ticks': int(obs[-1]['pts_ticks']), 'samples_per_vehicle': len(obs) // 2}
    ev = candidate['candidate_model']['events']
    summary['individual_offset_candidates_s'] = [x['ros_relative_s'] - x['video_s'] for x in ev]
    summary['two_event_affine_diagnostic'] = {
        'a': (ev[1]['ros_relative_s'] - ev[0]['ros_relative_s']) / (ev[1]['video_s'] - ev[0]['video_s']),
        'residual_degrees_of_freedom': 0, 'accepted': False,
        'reason': 'Two points exactly determine an affine line; physical event mismatch and clock drift cannot be separated'}
    sensitivity = []
    c1obs = [r for r in obs if r['vehicle_id'] == 'car1']
    c1odom = vehicles['car1']['odom']
    t = np.array([r['receive_relative_s'] for r in c1odom])
    xy = np.array([[r['x_m'], r['y_m']] for r in c1odom])
    idx = np.minimum(np.searchsorted(t, t - .25), np.arange(len(t)))
    dtimes = t - t[idx]
    speed = np.divide(np.linalg.norm(xy - xy[idx], axis=1), dtimes, out=np.zeros(len(t)), where=dtimes > 0)
    for visual_threshold in CONFIG['video_speed_threshold_sensitivity_px_s']:
        visual_events = motion_at_threshold(c1obs, visual_threshold)
        for odom_threshold in CONFIG['odom_speed_threshold_sensitivity_m_s']:
            runs = prior_time.intervals(t, speed > odom_threshold)
            aligned = prior_sync.align(visual_events, prior_sync.boundaries(prior_sync.merge_intervals(runs), 'car1'))
            sensitivity.append({'visual_threshold_px_s': visual_threshold, 'odom_threshold_m_s': odom_threshold,
                                'visual_events': visual_events, 'odom_intervals': runs,
                                'candidate': aligned, 'selected_as_new_model': False})
    summary['threshold_sensitivity'] = sensitivity
    summary['candidate_navigation_example'] = {
        'frame_index': 15, 'pts_ticks': 300,
        'receive_epoch_ns_candidate_only': e.candidate_receive_epoch_ns(300, 1, 600,
            candidate['candidate_model']['a'], candidate['candidate_model']['b_relative_s'], str(origin)),
        'validated_canonical_time': None, 'integer_epoch_preserved': True}
    # New image samples were rechecked, not used to move thresholds/events.
    summary['new_targeted_samples_role'] = 'Visibility and extraction recheck around inherited boundaries; no retiming from unlabelled frames'
    e.write_json(args.output / 'T10_time_audit.json', summary)
    old['v2_raw_input_audit'] = {'file': 'T10_time_audit.json', 'raw_records_compared': compared,
                               'original_bag_SHA_verified': True, 'candidate_reproduced': True,
                               'acceptance_unchanged': True}
    mappings['version'] = 'video_reference_20261027_v2'
    mappings['baseline_commit'] = BASELINE
    mappings['T14_T15_policy'] = 'Inherited candidate families preserved byte-for-JSON-value unchanged; no new evidence to select a phase'
    for exp in ['T14', 'T15']:
        original = next(x for x in e.load_json(OLD_DOC / 'time_mapping.json')['mappings'] if x['experiment_id'] == exp)
        actual = next(x for x in mappings['mappings'] if x['experiment_id'] == exp)
        if actual != original:
            raise ValueError('Ambiguous holdout mapping altered')
    e.write_json(args.output / 'time_mapping.json', mappings)
    print('Verified original odom/cmd records', compared, '; candidate reproduced; approved time model null', flush=True)


def review(args):
    out = args.output / 'review_001'
    out.mkdir(exist_ok=False)
    records = e.load_json(args.output / 'diagnostics_001/selected_frames_local.json')
    observations = e.read_csv(args.output / 'diagnostics_001/sample_recheck_observations.csv')
    provenance = []
    for index in [15, 1452]:
        rec = next(r for r in records if r['video'] == 'IMG_7347.MOV' and r['frame_index'] == index)
        image = cv2.imread(rec['local_frame_path'])
        for vehicle in ['car1', 'car2']:
            row = next(r for r in observations if r['experiment_id'] == 'T10' and int(r['frame_index']) == index and r['vehicle_id'] == vehicle)
            q = corners_from_row(row)
            low = np.maximum(np.floor(q.min(axis=0)).astype(int) - 55, [0, 0])
            high = np.minimum(np.ceil(q.max(axis=0)).astype(int) + 55, [3840, 2160])
            crop = image[low[1]:high[1], low[0]:high[0]]
            path = out / f'T10_frame_{index}_{vehicle}_native_crop.png'
            cv2.imwrite(str(path), crop)
            provenance.append({'file': path.name, 'source_frame_png_sha256': rec['frame_png_sha256'],
                'source_video_sha256': rec['video_sha256'], 'frame_index': index, 'pts_ticks': rec['pts_ticks'],
                'crop_xyxy_encoded_px': [int(low[0]), int(low[1]), int(high[0]), int(high[1])],
                'pixel_resampling': False, 'sha256': e.sha256(path), 'metric_annotation': False})
    e.write_json(out / 'crop_provenance.json', provenance)


def metadata(args):
    import av
    inventory = e.read_csv(args.output / 'video_inventory.csv')
    results = []
    for name in ['IMG_7336.MOV', 'IMG_7337.MOV', 'IMG_7347.MOV']:
        row = next(r for r in inventory if Path(r['relative_path']).name == name)
        root = 'calibration_data' if name in ['IMG_7336.MOV', 'IMG_7337.MOV'] else 'data'
        with av.open(str(args.legacy / root / row['relative_path'])) as container:
            stream = container.streams.video[0]
            stream.codec_context.thread_count = 2
            frame = next(container.decode(stream))
            H, size = prior_common.encoded_to_display(stream.width, stream.height, frame.rotation)
            if (stream.width, stream.height) != (int(row['encoded_width']), int(row['encoded_height'])):
                raise ValueError('Actual encoded dimensions differ from inventory')
            if frame.rotation % 360 != int(row['rotation_ccw_deg']) % 360:
                raise ValueError('Actual display rotation differs from inventory')
            if (frame.time_base.numerator, frame.time_base.denominator) != (int(row['time_base_num']), int(row['time_base_den'])):
                raise ValueError('Actual frame time base differs from inventory')
            results.append({'video': name, 'video_sha256': row['sha256'], 'first_pts_ticks': frame.pts,
                            'time_base_num': frame.time_base.numerator, 'time_base_den': frame.time_base.denominator,
                            'encoded_size_wh': [stream.width, stream.height], 'rotation_ccw_deg': frame.rotation,
                            'encoded_to_display': H.tolist(), 'display_size_wh': list(size),
                            'decoded_frames_for_metadata': 1, 'image_saved': False, 'full_decode_repeated': False})
    e.write_json(args.output / 'rotation_spotcheck.json', {'records': results,
        'status': 'passed', 'purpose': 'Targeted first-frame original metadata verification only; not a repeated media integrity audit'})


def tests(args):
    out = args.output / ('tests_' + args.attempt)
    out.mkdir(exist_ok=False)
    environment = dict(os.environ, VIDEO_CASE_OUTPUT=str(args.output))
    commands = []
    for label, directory, pattern in [
            ('new', 'tools/field_video_20261027', 'test_case.py'),
            ('prior', 'tools/field_video_20261026', 'test_video_reference.py')]:
        argv = [sys.executable, '-m', 'unittest', 'discover', '-s', directory, '-p', pattern, '-v']
        result = subprocess.run(argv, cwd=REPO, env=environment, capture_output=True, text=True, encoding='utf-8')
        with (out / (label + '.log')).open('x', encoding='utf-8') as stream:
            stream.write(result.stdout + result.stderr)
        commands.append({'argv': argv, 'returncode': result.returncode, 'log': label + '.log'})
        print(label, result.stdout + result.stderr, flush=True)
    e.write_json(out / 'test_results.json', {'commands': commands,
        'source_sha256': source_snapshot(), 'all_passed': all(c['returncode'] == 0 for c in commands)})
    if any(c['returncode'] for c in commands):
        raise RuntimeError('Tests failed; preserve this attempt and use a new --attempt after repair')


def gap_rows():
    return [
        {'id': 'raw_media', 'existing_evidence': '18片PR49完整性已通过；T10、两棋盘及P/Car2-Q本轮SHA一致；原件就在I盘旧目录',
         'true_gap': '无本地输入缺件；两棋盘仍未登记Release，仅影响纯远端取得',
         'impact': '不阻塞本机T10审计；纯GitHub复现需同SHA棋盘附件',
         'minimum_supplement': '需要跨环境复现时由协调端登记现有同SHA附件，不重拍、不重复下载', 'repeat_operator_question_needed': False},
        {'id': 'P_survey', 'existing_evidence': 'P1-P4原片、纸面编号、原像素人工交点、指导坐标齐全',
         'true_gap': '实际逐点尺量、点位误差和像素标注不确定度未提供，已在B端补证中确认',
         'impact': '房间外参仅名义候选；拟合残差不能证明精度',
         'minimum_supplement': '若历史测量表存在，提供读数/量具/轴向/安装时态；如今重摆不能补造旧实际坐标', 'repeat_operator_question_needed': False},
        {'id': 'Q_checks', 'existing_evidence': 'Q1-Q3指导坐标和拍摄完成记录、暂定片序对应；Q始终未参与拟合',
         'true_gap': '实际坐标/测量不确定度及逐片实际位置朝向未确认；Car2三Q片提取失败',
         'impact': '不能给独立精度误差；Car2检查点不可验收',
         'minimum_supplement': '核对已有摆位记录/独立测量单与原帧；Car2先解决可解释的板形状与像素提取，保留失败', 'repeat_operator_question_needed': False},
        {'id': 'intrinsics_clip_relation', 'existing_evidence': '原棋盘、双向实测格距、11个既有拟合/分组模型；每片背景登记',
         'true_gap': '稳定内参与逐片成像等价性未验证；棋盘平整性不明；T10外参依赖传播的名义P且P2在画外',
         'impact': '空间尺度/射线/逐片外参不能作为正式参考',
         'minimum_supplement': '先核对历史拍摄设置和刚性/稳定性证据；可从原片继续独立像素检查，但不按Q误差选模型', 'repeat_operator_question_needed': False},
        {'id': 'Car1_mount', 'existing_evidence': '本轮人工明确标题边朝车头、车头为红支架/机械臂侧；安装原图ID0角点0-1位于标题侧；板高和marker→天线人工偏移已记录',
         'true_gap': '完整角度/水平性/偏移测量不确定度仍未知；旧报告相反边推断已保留并按最新人工来源更新',
         'impact': '可计算明确假设的Car1天线候选，不能批准其精度',
         'minimum_supplement': '无需重问哪边是车头；若需精度验收，仅补同安装状态的角度/杆臂量测及不确定度', 'repeat_operator_question_needed': False},
        {'id': 'Car2_board_mount', 'existing_evidence': 'T10本轮9帧ID1自动成功；三Q原4K样本失败；纸面/黑边曲率可见；板高0.23m/天线0.20m及body偏移已记录',
         'true_gap': '刚性板形状、倾角、marker→body旋转、角点/中心偏差及各测量不确定度未知',
         'impact': '保留平面候选诊断；Car2天线坐标留空；识别/跟踪不等于板平面或空间精度通过',
         'minimum_supplement': '优先利用原4K视角/同安装照片建立可证据化板模型；单幅四角不能唯一分离弯曲、透视、镜头与遮挡', 'repeat_operator_question_needed': False},
        {'id': 'T10_time', 'existing_evidence': '2903条整数PTS；原bag的2972条odom/cmd逐条回读一致；两个Car1运动事件重现旧候选；历史NTP快照已有',
         'true_gap': '独立同步事件、T10同期offset/drift及打戳/物理事件差的界未取得，先前补证已明确未找到',
         'impact': '时间候选可导航；连续参考的时间与总误差界仍未知；静止Car2不提供时钟约束',
         'minimum_supplement': '仅检索同期独立共同事件/部署时钟证据；当前对钟不能补造历史界；不得把拟合残差当同步界', 'repeat_operator_question_needed': False},
        {'id': 'T10_endpoint', 'existing_evidence': 'Car1末点(1.48,2.97)m、末距1.52m人工报告；Car2(2.98,3.07)m来自T09人工末点及保持计划；1.75m明确沿用而非新测',
         'true_gap': '精确同次未挪动停车窗绑定和量测不确定度不明；实际T10起始几何未单独确认',
         'impact': '保留原人工参考，不生成精度停点，也不拿计划初值校准视频',
         'minimum_supplement': '如已有同期记录，核对实际停车/测量时态及读数误差；稳定停点无需人为要求毫秒级连续同步', 'repeat_operator_question_needed': False},
        {'id': 'acceptance', 'existing_evidence': '无预先批准的空间或总时空容差；本轮列原始诊断和候选适用范围',
         'true_gap': '针对用途的独立验收容差和总不确定度模型未批准',
         'impact': 'continuous和checkpoints_only均not_accepted；不报告实包RMSE/ATE/提升',
         'minimum_supplement': '由协调端在看最终误差前确定用途与容差；不依结果反向放宽', 'repeat_operator_question_needed': False}
    ]


def package(args):
    from verify_case import audit
    tests_result = e.load_json(args.output / ('tests_' + args.attempt) / 'test_results.json')
    if not tests_result['all_passed']:
        raise RuntimeError('Package requires successful tests')
    if e.load_json(args.output / 'rotation_spotcheck.json')['status'] != 'passed':
        raise RuntimeError('Original rotation metadata verification not completed')
    previous = e.load_json(OLD_DOC / 'reference_validation.json')
    validation = dict(previous)
    validation.update(version='video_reference_20261027_v2', baseline_commit=BASELINE,
        processing_status='DONE', status='BLOCKED', approved_scope='not_accepted',
        fit_point_ids=['P1', 'P2', 'P3', 'P4'], independent_check_ids=['Q1', 'Q2', 'Q3'],
        Q_used_for_fit_or_selection=False, acceptance_tolerance_m=None,
        actual_independently_measured_checkpoint_errors=None,
        current_operator_confirmation=e.load_json(args.output / 'diagnostics_001/car1_front_evidence.json'),
        nominal_Q_checks_status='PR49 reused unchanged; no new metric Q fitting or error-based model selection',
        T10_geometry=e.load_json(args.output / 'T10_geometry_summary.json'),
        T10_extraction=e.load_json(args.output / 'diagnostics_001/extraction_summary.json'),
        T10_time_audit_file='T10_time_audit.json',
        source_evidence_file='input_evidence.json',
        gap_table_file='missing_evidence.csv',
        completed_valid_subtasks=['raw identity', 'PTS/observation consistency', 'targeted original 4K extraction diagnostics',
            'conditional room/height/lever-arm computation with declared assumptions',
            'original odom/cmd event reproduction', 'independent numerical readback and negative tests'],
        metric_valid_intervals={'car1': [], 'car2': []},
        per_use_decision={'continuous': 'not_accepted', 'checkpoints_only': 'not_accepted',
                          'image_space_and_candidate_sensitivity_diagnostics': 'supported_with_explicit_assumptions'},
        no_interpolated_truth=True, fusion_estimates_used_for_reference=False,
        why_no_checkpoints_csv='No independent surveyed position/uncertainty and precise same-parking binding; no approved tolerance. Stationary checkpoints would not require a fabricated continuous clock model.')
    # Preserve the prior qualitative source instead of silently editing history.
    validation['operator_mount_confirmation_PR49'] = validation.pop('operator_mount_confirmation', None)
    validation['operator_mount_confirmation'] = validation['current_operator_confirmation']
    e.write_json(args.output / 'reference_validation.json', validation)
    gaps = gap_rows()
    e.write_csv(args.output / 'missing_evidence.csv', gaps)
    e.write_json(args.output / 'missing_evidence.json', {'rows': gaps,
        'prior_answers_consulted': 't10_closure_20261027/operator_evidence.json plus PR49 and current task',
        'new_user_evidence_requests_sent': 0})
    crops = e.load_json(args.output / 'review_001/crop_provenance.json')
    e.write_json(args.output / 'visual_review.json', {
        'observer': 'assistant visual review in this task, not a new human field measurement',
        'inputs': ['diagnostics_001/original_frame_contact_sheet.jpg',
                   'diagnostics_001/IMG_7365_Car2_native_crop.png',
                   'diagnostics_001/IMG_7367_Car2_native_crop.png',
                   'review_001/T10_frame_15_car2_native_crop.png',
                   'repository/evidence/car1_top.jpg', 'repository/evidence/car1_side.jpg'],
        'findings': ['Q1/Q3 native crops show a non-straight sheet outline and black-border curves; a rigid tilted plane alone is not established',
                     'T10 ID1 is readable from this viewing direction; slight border/sheet curvature remains visible and does not define a metric bend',
                     'Contact sheet shows Car1 image movement and approximately stationary Car2 at these samples only',
                     'Car1 installation title is beyond decoded edge 0-1; current user explicitly states this side is forward'],
        'unknowns': ['3D curvature and tilt cannot be quantified uniquely from these views',
                     'lens distortion, blur and corner/chord offsets confound image-only edge profiles',
                     'sampled stationary appearance is not an independently calibrated continuous stationary interval'],
        'manual_human_corner_annotations': 0, 'spatial_accuracy_accepted': False,
        'native_crop_provenance_file': 'review_001/crop_provenance.json'})
    e.write_json(args.output / 'verification.json', audit(args.output, REPO))
    geo = validation['T10_geometry']['per_vehicle']
    time_audit = e.load_json(args.output / 'T10_time_audit.json')
    decode = validation['T10_extraction']
    md = f'''# T10 视频参考 v2：处理链完成，位置参考 not_accepted

共同基准 `{BASELINE}`；分支 `analysis/20261027-video-reference-v2`。只增加本报告目录和 `tools/field_video_20261027/`。

本轮完成 T10=IMG_7347.MOV 的可逐项回读案例：原件身份 → 2,903条原PTS → 每车194个既有2Hz观测 → 少量原4K复查 → 条件几何/敏感性 → 原bag运动事件 → 独立回读与参考裁决。**continuous、checkpoints_only均为not_accepted**；没有生成天线真值、精度停点、插值轨迹或实包定位RMSE。

## 已完成证据

- PR49已合并，18段41,381帧完整性继承，不重跑。实际使用的T10、两棋盘、P片和三Car2-Q原片，本轮7份SHA均一致；T10正式成功重试bag SHA一致。原始文件在I盘旧目录只读复用，没有下载/解压/搬动。
- T10 388行观测逐条对应原PTS，主表5,424行原样继承，失败、跟踪、非适用均保留。原完整PTS末帧与2Hz末样本分别记录，不以平均帧率替代PTS。
- 复查{decode['original_4K_frames_reviewed']}个原始4K样本：T10九帧两车各9/9自动解码，Car2-Q三帧0/3。新原片仅按PTS寻址解码{decode['new_targeted_decoded_frames_including_preroll']}帧（含关键帧预滚），只保存选定帧至I盘临时目录。新跟踪0次、新人工角点0条；3个人工选择的检查ROI不是位置标注。
- 四角和边缘剖面、原生像素裁剪、两支平面PnP解均保留。Car2 Q纸面/黑边曲率可见；检测成功、小拟合残差、边缘直线性均不证明刚性平面或空间精度。
- 本轮从原bag逐条核对2,972条原odom/cmd，与PR49导出一致，完整保留record_index、整数header/receive ns。没有调用定位估计器或使用融合轨迹。

## 几何与来源

黑框边长0.144m；棋盘格距0.192/10m、0.134/7m。IMG_7336/7337原片在本机且SHA一致，仍不在Release；不是输入缺件。11个旧内参模型/分组统计有来源SHA，未重跑整套标定。7337交替组fx约3238/3128px，7336与7337差异仍未解决；同为4K不证明成像等价。

主候选固定为PR49在Q前使用的7337模型；逐片外参使用T10首个0.5s既有样本，其他模型/姿态只作预先声明敏感性。P1–P4仅指导坐标，Q1–Q3独立保留、不参与拟合或模型/方向选择。T10的P2传播像素在画外，地面登记和名义P重投影残差不能当独立精度。

新计算先对四角去畸变，再求对角线交点和抬高平面射线交点；地面单应仅用于背景/P传播，未直接作用车顶标记。Car1/Car2板高0.37/0.23m、天线高0.17/0.20m沿用人工记录，不确定度未知。

Car1本轮人工明确“标题边朝车头，车头为红色支架/机械臂侧”。安装原图ID0角点0–1在标题侧，因此按该来源使用标记+Y作为条件性车前方向。旧报告相反边推断完整保留，180°情况列入敏感性；未用Q或人工末点误差选方向。完整角度与杆臂误差仍未知。Car2旋转、倾斜/弯曲均未知，**天线坐标保持空值**，不默认零旋转。

以下是给定模型和扰动的候选差异，不是测量不确定度、置信界或可接受容差：

|诊断|Car1 XY最大变化|Car2 XY最大变化|
|---|---:|---:|
|假设板高±2cm|{geo['car1']['sensitivity_xy_m']['board_height_delta_m']['max']:.4f}m|{geo['car2']['sensitivity_xy_m']['board_height_delta_m']['max']:.4f}m|
|三种旧相机候选|{geo['car1']['sensitivity_xy_m']['camera_model']['max']:.4f}m|{geo['car2']['sensitivity_xy_m']['camera_model']['max']:.4f}m|
|错误地用地面高度|{geo['car1']['sensitivity_xy_m']['wrong_ground_plane']['max']:.4f}m|{geo['car2']['sensitivity_xy_m']['wrong_ground_plane']['max']:.4f}m|

Car1当前与反向假设的水平杆臂差约0.2953m；Car2仅在“平面、body偏移已知”的附加假设下，其未知yaw的天线水平圆轨迹半径约0.1718m，仍非误差界。候选逐行结果见T10_candidate_geometry.csv，所有`metric_reference_valid=0`。

## 时间裁决

原Car1图像起止35.501667/59.001667s，对应原odom阈值起止10.366640/34.227232s。重现PR49候选 `receive_relative_s = video_PTS_s - 24.954730587166665`，最大拟合残差约0.1803s。a=1只是旧候选假设；两个点拟合漂移没有剩余自由度，不是独立时钟标定。阈值敏感性、源记录、采样括号、静止守卫和歧义完整列在T10_time_audit.json。

原cmd与odom起/止阈值差约0.960/1.740s，说明命令、可见动作与odom阈值是不同事件定义，不能互当同步界。历史NTP状态、未知打戳/物理响应差不升级为有界同步。正式model与总时间误差界仍为null。T14/T15多候选原样保留，没有新证据强选。

## 交付与缺项

五份契约：video_inventory.csv、marker_observations.csv、frame_transforms.json、time_mapping.json、reference_validation.json。一次性完整缺项表见[MISSING_EVIDENCE.md](MISSING_EVIDENCE.md)及CSV/JSON；已查PR49和T10闭环补证，不重复索要已确认的车头、近似几何中心偏移、旧NTP状态或沿用间距。独立P/Q尺量、成像/安装模型、同次停车绑定及有界同步的真实缺项限制位置验收；没有预批容差时报告证据和候选用途，不反向放宽。

实际命令、各阶段源码SHA及失败记录见commands.jsonl；输入/来源SHA见input_evidence.json；代码和运行来源见run.json，完整交付SHA见SHA256SUMS.txt；测试见tests_{args.attempt}/，独立数值回读见verification.json。HANDOFF.md给出接续入口。运行完成后没有遗留计算进程，不启动实车，不自动合并。
'''
    (args.output / 'README.md').write_text(md, encoding='utf-8')
    gap_md = '# 一次性证据与缺项表\n\n已读取PR49、实际文件、T10闭环operator_evidence及本轮人工说明。没有向用户发送新补证问题。\n\n|项|已有证据|真正缺项|影响范围|最小补证方式|\n|---|---|---|---|---|\n'
    gap_md += '\n'.join('|'+ '|'.join(str(row[k]).replace('|', '/') for k in ['id', 'existing_evidence', 'true_gap', 'impact', 'minimum_supplement']) +'|' for row in gaps) + '\n'
    (args.output / 'MISSING_EVIDENCE.md').write_text(gap_md, encoding='utf-8')
    handoff = f'''# T10 视频参考 v2 HANDOFF

仓库基准 `{BASELINE}`，分支 `analysis/20261027-video-reference-v2`，实际检出 `I:\\UWB\\project\\worktrees\\video-reference-v2`。

处理链已完成；位置参考批准范围仍`not_accepted`。保留有效的原件身份、PTS、观测、13个原4K小样本、条件几何/敏感性、原bag事件、测试和独立逐行回读。没有continuous或checkpoints_only真值，未运行定位估计器。旧18片QC不重跑，T09/T11/T13/T15不作定位调参，T14/T15候选族未变。

原始输入只读复用 `I:\\UWB\\project\\outputs\\video_reference_20261026`，本轮原件SHA见input_evidence.json。新输出 `I:\\UWB\\project\\outputs\\video_reference_20261027`；选定新解码帧 `I:\\UWB\\temp\\video_reference_20261027\\raw_samples_001`；每个任务进程TEMP/TMP设`I:\\UWB\\temp`。不得在I盘不可用时回退C盘。没有新增大型下载或解压。

Car1标题边/红支架车头采用本轮明确人工来源，旧相反推断保留；完整角度未知。Car2板倾斜/曲率与marker→body旋转未验证，天线坐标留空。候选房间XYZ不是精度参考。

接续先读README、五契约、MISSING_EVIDENCE和visual_review。真正阻塞及最小补证已列一次性表；不要重问已确认事项、重跑输入QC、按Q/融合误差选模型，或插值制造真值。如今重摆车或对钟不能补造历史实测。若取得新证据，建立新run目录/版本，不覆盖本轮结果，再独立审查空间、停车窗或时间是否足以支持指定范围。

工具、复现命令见`tools/field_video_20261027/README.md`；commands.jsonl保留实跑argv/源码SHA/退出码。tests_{args.attempt}及verification.json记录通过的检查。所有参考不确定度/精度指标仍为null，未放宽容差。
'''
    (args.output / 'HANDOFF.md').write_text(handoff, encoding='utf-8')
    packages = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze'], text=True, encoding='utf-8')
    (args.output / 'python_packages.txt').write_text(packages, encoding='utf-8')


def seal(args):
    commands = [json.loads(x) for x in (args.output / 'commands.jsonl').read_text(encoding='utf-8').splitlines()]
    e.write_json(args.output / 'source_lineage.json', {
        'baseline_commit': BASELINE,
        'actual_execution_commit': commands[0]['code_commit'],
        'worktree_dirty_during_runs': True,
        'per_stage_startup_source_hashes': [{'stage': r['stage'], 'source_sha256': r['source_sha256']} for r in commands],
        'source_evolution': 'New stage functions, audit/tests and packaging were added between stages. Numeric functions used for completed stages were not retuned or changed after their outputs were observed. Later preflight change permits exact-baseline descendants for reproduction and rejects public contract/config changes.',
        'early_transient_full_file_snapshots_saved': False,
        'limitation': 'Earlier full-module hashes include not-yet-complete module versions, whose exact bytes were not snapshotted. They are not claimed to be the final submitted source hash. Completed stage implementations are present in final source; stage-specific hashes, raw input comparison, synthetic tests and independent 1164-row numerical readback are retained.',
        'final_sources': source_snapshot(),
        'prior_PR49_source_lineage': 'Preserved unchanged in the prior evidence directory; not rewritten here'})
    files = [p for p in args.output.rglob('*') if p.is_file() and p.name != 'selected_frames_local.json']
    e.write_json(args.output / 'run.json', {'schema_version': 1, 'run_id': 'video_reference_20261027_001',
        'role': 'local_video', 'status': 'BLOCKED', 'processing_status': 'DONE', 'approved_scope': 'not_accepted',
        'created_at_utc': commands[0]['started_at_utc'], 'code_commit': BASELINE, 'worktree_dirty': True,
        'source_sha256': source_snapshot(),
        'config_sha256': {n: e.sha256(BASE_DOC / n) for n in ['manifest.json', 'geometry.json']},
        'inputs': e.load_json(args.output / 'input_evidence.json'),
        'commands': commands,
        'outputs': [{'relative_path': p.relative_to(args.output).as_posix(), 'sha256': e.sha256(p)} for p in sorted(files)],
        'manifest_policy': 'run.json excludes itself and final SHA256SUMS to avoid cycles; SHA256SUMS includes run.json and excludes itself',
        'blocked_reasons': [x['true_gap'] for x in gap_rows() if x['id'] != 'raw_media'],
        'completed_effective_subtasks': e.load_json(args.output / 'reference_validation.json')['completed_valid_subtasks'],
        'limitations': ['No independently accepted metric video reference', 'No algorithm runs or holdout localization tuning'],
        'future_reproduction': 'Run code at its submitted commit, with identical source/config hashes and original assets; original runs used explicitly recorded dirty working sources at the common baseline'})
    files = [p for p in args.output.rglob('*') if p.is_file() and p.name not in ['selected_frames_local.json', 'SHA256SUMS.txt']]
    sums = ''.join(f'{e.sha256(p)}  {p.relative_to(args.output).as_posix()}\n' for p in sorted(files))
    with (args.output / 'SHA256SUMS.txt').open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(sums)
    delivery = BASE_DOC / 'video_reference_20261027'
    delivery.mkdir(exist_ok=False)
    for p in files + [args.output / 'SHA256SUMS.txt']:
        target = delivery / p.relative_to(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        copy_new(p, target)
    print('Sealed delivery files', len(files) + 1, 'at', delivery, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['intake', 'diagnose', 'geometry', 'timing', 'review', 'metadata', 'tests', 'package'])
    parser.add_argument('--legacy', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--temp', type=Path, default=Path('I:/UWB/temp/video_reference_20261027'))
    parser.add_argument('--attempt', default='001', help='Unique test attempt label; failed logs are retained')
    args = parser.parse_args()
    if not Path('I:/').is_dir():
        raise RuntimeError('I: unavailable; stop without C: fallback')
    for path in [args.legacy, args.output, args.temp]:
        if path.resolve().drive.upper() != 'I:':
            raise ValueError('All data/output/temp paths must remain on I:')
    if shutil.disk_usage('I:/').free < 5 * 1024 ** 3:
        raise RuntimeError('Less than 5 GiB reserve on I:; stop computation')
    if os.environ.get('TEMP', '').replace('\\', '/').rstrip('/').lower() != 'i:/uwb/temp':
        raise RuntimeError('Set process TEMP/TMP to I:/UWB/temp')
    if os.environ.get('TMP') != os.environ.get('TEMP'):
        raise RuntimeError('TEMP and TMP differ')
    cv2.setNumThreads(2)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    start = time.monotonic()
    record = {'stage': args.stage, 'argv': sys.argv, 'started_at_utc': started,
              'code_commit': git('rev-parse', 'HEAD'), 'worktree_dirty': bool(git('status', '--porcelain=v1')),
              'source_sha256': source_snapshot(), 'environment': {'python': sys.version,
                'opencv': cv2.__version__, 'numpy': np.__version__,
                'TEMP': os.environ['TEMP'], 'TMP': os.environ['TMP']}}
    try:
        globals()[args.stage](args)
        record['exit_code'] = 0
    except Exception:
        record['exit_code'] = 1
        record['traceback'] = traceback.format_exc()
        raise
    finally:
        record['elapsed_s'] = time.monotonic() - start
        if args.output.is_dir():
            with (args.output / 'commands.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
    if args.stage == 'package' and record['exit_code'] == 0:
        seal(args)


if __name__ == '__main__':
    main()
