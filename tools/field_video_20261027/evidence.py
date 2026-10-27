"""Strict, append-only evidence helpers. No accepted reference is synthesized."""
import csv
import hashlib
import json
from decimal import Decimal, localcontext
from fractions import Fraction
from pathlib import Path

import cv2
import numpy as np


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=None):
    rows = list(rows)
    fields = fields or list(rows[0])
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def validate_pts(observations, ledger):
    by_index = {int(row['frame_index']): row for row in ledger}
    if len(by_index) != len(ledger):
        raise ValueError('Duplicate frame index')
    ticks = [int(row['pts_ticks']) for row in ledger]
    if any(b <= a for a, b in zip(ticks, ticks[1:])):
        raise ValueError('PTS must be strictly increasing')
    seen = set()
    for row in observations:
        key = (int(row['frame_index']), row['vehicle_id'])
        if key in seen:
            raise ValueError('Duplicate vehicle/frame observation')
        seen.add(key)
        source = by_index[int(row['frame_index'])]
        for name in ('pts_ticks', 'time_base_num', 'time_base_den'):
            if int(row[name]) != int(source[name]):
                raise ValueError('Observation/PTS ledger mismatch: ' + name)
        exact = Fraction(int(row['pts_ticks']) * int(row['time_base_num']), int(row['time_base_den']))
        if abs(float(exact) - float(row['video_time_s'])) > 1e-9:
            raise ValueError('PTS seconds mismatch')
    return {'observations': len(observations), 'ledger_frames': len(ledger),
            'first_pts_ticks': ticks[0], 'last_pts_ticks': ticks[-1],
            'unique_vehicle_frame_pairs': len(seen), 'status': 'passed'}


def normalized_quad(corners, K, D):
    return cv2.undistortPoints(np.asarray(corners, np.float64).reshape(4, 1, 2),
                              np.asarray(K, np.float64), np.asarray(D, np.float64)).reshape(4, 2)


def projective_center(normalized_corners):
    # A planar quad's diagonal intersection, after undistortion. A curved board
    # need not have its physical centre here; that limitation stays explicit.
    a, b, c, d = np.c_[np.asarray(normalized_corners), np.ones(4)]
    q = np.cross(np.cross(a, c), np.cross(b, d))
    if abs(q[2]) < 1e-12:
        raise ValueError('Degenerate quad')
    return q[:2] / q[2]


def intersect_normalized(ray_xy, T_room_camera, height_m):
    T = np.asarray(T_room_camera, float)
    ray = T[:3, :3] @ np.r_[ray_xy, 1.0]
    if abs(ray[2]) < 1e-12:
        raise ValueError('Ray parallel to plane')
    scale = (height_m - T[2, 3]) / ray[2]
    if scale <= 0:
        raise ValueError('Plane behind camera')
    return T[:3, 3] + scale * ray


def conditional_geometry(corners, K, D, T_room_camera, height_m):
    q = normalized_quad(corners, K, D)
    center = intersect_normalized(projective_center(q), T_room_camera, height_m)
    vertices = np.array([intersect_normalized(x, T_room_camera, height_m) for x in q])
    forward = (vertices[0] + vertices[1] - vertices[2] - vertices[3])[:2]
    return center, vertices, float(np.arctan2(forward[1], forward[0]))


def antenna_candidate(marker_xyz, heading_rad, offset_body_xyz):
    if heading_rad is None:
        raise ValueError('Unknown marker/body yaw cannot be replaced with zero')
    c, s = np.cos(heading_rad), np.sin(heading_rad)
    return np.asarray(marker_xyz) + np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]]) @ np.asarray(offset_body_xyz)


def candidate_receive_epoch_ns(tick, num, den, a, b, origin_ns):
    """Navigation candidate only; avoid epoch precision loss through float."""
    with localcontext() as context:
        context.prec = 60
        seconds = Decimal(str(a)) * Decimal(tick) * Decimal(num) / Decimal(den) + Decimal(str(b))
        delta = int((seconds * Decimal(10 ** 9)).to_integral_value())
    return str(int(origin_ns) + delta)


def edge_profiles(gray, corners):
    """Image-only edge diagnostics. No metric bend or accuracy inference.

    At 41 stations along each edge (excluding the ends), find the strongest
    outward dark-to-light gradient within +/-5 encoded pixels of the corner
    chord. Corner chord, peak contrast, failures, and offsets are retained.
    Printing, blur, lens distortion, background edges and bending all confound
    this profile. A straight profile cannot prove a rigid plane.
    """
    corners = np.asarray(corners, float)
    center = corners.mean(axis=0)
    profiles = []
    offsets = np.linspace(-5, 5, 41).astype(np.float32)
    stations = np.linspace(.1, .9, 41)
    for i in range(4):
        start, end = corners[i], corners[(i + 1) % 4]
        v = end - start
        length = np.linalg.norm(v)
        if length < 8:
            profiles.append({'edge': i, 'status': 'failed_short_edge'})
            continue
        n = np.array([-v[1], v[0]]) / length
        if np.dot((start + end) / 2 - center, n) < 0:
            n = -n
        base = start + stations[:, None] * v
        samples = base[:, None, :] + offsets[None, :, None] * n
        values = cv2.remap(gray, samples[:, :, 0].astype(np.float32),
                           samples[:, :, 1].astype(np.float32), cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REFLECT101).astype(float)
        gradient = (values[:, 2:] - values[:, :-2]) / .5
        index = np.argmax(gradient, axis=1)
        peak = gradient[np.arange(len(index)), index]
        signed = offsets[1:-1][index].astype(float)
        boundary = (index == 0) | (index == gradient.shape[1] - 1)
        valid = (peak >= 10) & ~boundary
        profiles.append({'edge': i, 'status': 'image_diagnostic_only',
                         'chord_length_px': float(length),
                         'stations': len(stations), 'usable_stations': int(valid.sum()),
                         'peak_at_search_boundary': int(boundary.sum()),
                         'station_fraction': stations.tolist(),
                         'signed_peak_offset_px': signed.tolist(),
                         'peak_gradient_intensity_per_px': peak.tolist(),
                         'valid_station_mask': valid.tolist(),
                         'median_offset_px': float(np.median(signed[valid])) if valid.any() else None,
                         'p95_abs_offset_from_chord_px': float(np.quantile(abs(signed[valid]), .95)) if valid.any() else None})
    return profiles
