"""Independent readback of candidate geometry and the acceptance boundary."""
import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(output, repo):
    output, repo = Path(output), Path(repo)
    prior = repo / 'docs/field_tests/20261024_25/video_reference_20261026'
    geo = read_json(repo / 'docs/field_tests/20261024_25/geometry.json')
    calibration = read_json(prior / 'calibration_stability.json')['models']
    transforms = read_json(output / 'frame_transforms.json')
    times = read_json(output / 'time_mapping.json')
    validation = read_json(output / 'reference_validation.json')
    candidates = read_csv(output / 'T10_candidate_geometry.csv')
    source = [r for r in read_csv(output / 'marker_observations.csv') if r['experiment_id'] == 'T10']
    source_map = {(r['frame_index'], r['vehicle_id']): r for r in source}
    pose = next(r for r in transforms['records'] if r['asset_id'] == 'T10_video')['clips'][0]
    max_error = 0.
    keys = set()
    for row in candidates:
        key = (row['frame_index'], row['vehicle_id'], row['camera_candidate'])
        require(key not in keys, 'Duplicate candidate row')
        keys.add(key)
        obs = source_map[(row['frame_index'], row['vehicle_id'])]
        for field in ['pts_ticks', 'time_base_num', 'time_base_den']:
            require(int(row[field]) == int(obs[field]), 'Candidate PTS mismatch')
        name = row['camera_candidate']
        K = np.array(calibration[name]['K'])
        D = np.array(calibration[name]['D'])
        T = np.array(pose['room_pose_candidates'][name]['T_room_camera'])
        raw = np.array([[float(obs[f'corner{k}_x_px']), float(obs[f'corner{k}_y_px'])] for k in range(4)])
        q = cv2.undistortPoints(raw.reshape(4, 1, 2), K, D).reshape(4, 2)
        # Solve the two diagonal parametric equations independently of the
        # production homogeneous-cross-product implementation.
        uv = np.linalg.solve(np.column_stack([q[2] - q[0], -(q[3] - q[1])]), q[1] - q[0])
        xy = q[0] + uv[0] * (q[2] - q[0])
        height = geo['mounts'][row['vehicle_id']]['black_border_center_height_m']
        ray = T[:3, :3] @ np.array([xy[0], xy[1], 1.])
        center = T[:3, 3] + ray * ((height - T[2, 3]) / ray[2])
        actual = np.array([float(row[f'marker_{a}_m']) for a in 'xyz'])
        max_error = max(max_error, float(np.linalg.norm(center - actual)))
        require(np.linalg.norm(center - actual) < 1e-9, 'Independent ray/diagonal readback differs')
        require(row['metric_reference_valid'] == '0' and row['approved_scope'] == 'not_accepted', 'Candidate promoted to truth')
        if row['vehicle_id'] == 'car2':
            require(all(row[f'antenna_{a}_m'] == '' for a in 'xyz') and row['assumed_body_yaw_rad'] == '',
                    'Unknown Car2 yaw filled with an antenna position')
        else:
            vertices = []
            for p in q:
                ray = T[:3, :3] @ np.r_[p, 1.]
                vertices.append(T[:3, 3] + ray * ((height - T[2, 3]) / ray[2]))
            v = np.array(vertices)
            forward = (v[0] + v[1] - v[2] - v[3])[:2]
            yaw = np.arctan2(forward[1], forward[0])
            require(abs(yaw - float(row['assumed_body_yaw_rad'])) < 1e-10, 'Current title-edge source not respected')
            dx, dy, dz = geo['mounts']['car1']['marker_center_to_antenna_body_aligned_xyz_m']
            ant = center + np.array([np.cos(yaw) * dx - np.sin(yaw) * dy,
                                     np.sin(yaw) * dx + np.cos(yaw) * dy, dz])
            require(np.linalg.norm(ant - [float(row[f'antenna_{a}_m']) for a in 'xyz']) < 1e-9,
                    'Independent lever-arm readback differs')
    require(len(candidates) == 3 * len(source) == 1164, 'Candidate coverage differs from observed frames')
    require(validation['approved_scope'] == 'not_accepted', 'Unapproved spatial evidence accepted')
    require(validation['actual_independently_measured_checkpoint_errors'] is None, 'Invented independent errors')
    require(validation['acceptance_tolerance_m'] is None, 'Invented or result-selected tolerance')
    require(set(validation['fit_point_ids']).isdisjoint(validation['independent_check_ids']), 'Fit/check leakage')
    require(not validation['Q_used_for_fit_or_selection'], 'Q used for tuning')
    require(not (output / 'antenna_reference.csv').exists() and not (output / 'checkpoints.csv').exists(),
            'Unaccepted reference CSV published')
    for mapping in times['mappings']:
        require(mapping['model'] is None, 'Unapproved clock model published')
    previous_times = read_json(prior / 'time_mapping.json')
    for exp in ['T14', 'T15']:
        old = next(x for x in previous_times['mappings'] if x['experiment_id'] == exp)
        new = next(x for x in times['mappings'] if x['experiment_id'] == exp)
        require(new == old, 'Ambiguous event family changed without evidence')
    original = read_csv(output / 'T10_original_odom_cmd.csv')
    require(len(original) == 2972, 'Original odom/cmd coverage lost')
    for row in original:
        require(str(int(row['receive_epoch_ns'])) == row['receive_epoch_ns'], 'Receive epoch precision lost')
        if row['header_epoch_ns']:
            require(str(int(row['header_epoch_ns'])) == row['header_epoch_ns'], 'Header epoch precision lost')
    all_json = list(output.glob('*.json')) + list((output / 'diagnostics_001').glob('*.json'))
    for path in all_json:
        read_json(path)
    return {'status': 'passed', 'independent_geometry_rows': len(candidates),
            'max_independent_readback_difference_m': max_error,
            'original_odom_cmd_records': len(original), 'strict_JSON_files_read': len(all_json),
            'accepted_metric_reference_rows': 0, 'T14_T15_candidate_families_preserved': True,
            'Q_fit_leakage': False, 'temporal_interpolation': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(audit(args.output, args.repo), indent=2))
