#!/usr/bin/env python3
"""Read-only transfer check. P1 alone calibrates; surveyed points evaluate only."""
import argparse
import collections
import csv
import hashlib
import json
import math
import platform
import sys
import tarfile
import zipfile
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load_bag(path):
    from rosbags.highlevel import AnyReader
    ranges, odom, commands = [], [], []
    with AnyReader([path]) as reader:
        origin = reader.start_time
        topics = {c.topic: c.msgcount for c in reader.connections}
        conns = [c for c in reader.connections if c.topic.endswith(('/uwb/ranges', '/odom', '/cmd_vel'))]
        for c, received, raw in reader.messages(connections=conns):
            msg = reader.deserialize(raw, c.msgtype)
            recv = (received-origin)*1e-9
            if c.topic.endswith('/cmd_vel'):
                commands.append([recv, float(msg.linear.x), float(msg.angular.z)])
                continue
            stamp = (int(msg.header.stamp.sec)*1000000000+int(msg.header.stamp.nanosec)-origin)*1e-9
            if c.topic.endswith('/uwb/ranges'):
                grouped = collections.defaultdict(list)
                for item in msg.ranges:
                    grouped[item.anchor_id].append(float(item.range))
                values = {k: v[0] for k, v in grouped.items()
                          if len(v) == 1 and math.isfinite(v[0]) and v[0] > 0}
                ranges.append([stamp, values, msg.tag_id])
            else:
                p = msg.pose.pose.position
                odom.append([stamp, float(p.x), float(p.y)])
    return {'origin_ns': origin, 'topics': topics, 'ranges': ranges,
            'odom': odom, 'commands': commands, 'sha256': sha(path.read_bytes())}


def dump_csv(path, rows):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def solve_xy(medians, anchors, bias):
    """Unweighted median-range LS diagnostic, no reference position as input."""
    ids = sorted(medians)
    a = np.array([anchors[k] for k in ids])
    r = np.array([medians[k]-bias.get(k, 0.) for k in ids])
    if len(ids) < 3 or np.any(r <= 0):
        raise ValueError('insufficient/nonpositive corrected range')
    def residual(x):
        return np.linalg.norm(np.column_stack((np.tile(x, (len(a), 1)), np.full(len(a), .2)))-a, axis=1)-r
    trials = [least_squares(residual, seed, ftol=1e-12, xtol=1e-12, gtol=1e-12)
              for seed in [[2.665, 2.69], [0., 0.], [5.33, 5.38]]]
    best = min(trials, key=lambda x: float(np.sum(x.fun*x.fun)))
    if not best.success:
        raise ValueError('position diagnostic failed')
    return best.x, float(np.sqrt(np.mean(best.fun**2)))


def analyze(args):
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    inputs = out/'inputs'
    inputs.mkdir()
    base = Path(__file__).resolve().parent
    protocol = json.loads((base/'protocol.json').read_text())
    cfg_path = args.oct17_config
    cfg = json.loads(cfg_path.read_text())
    anchors = cfg['anchors_xyz_m']
    archive_bytes = args.oct17_archive.read_bytes()
    archive_sha = sha(archive_bytes)
    bags = {}
    with tarfile.open(args.oct17_archive, 'r:gz') as tar:
        for name in protocol['oct17_reference_points']:
            member = '20261017/'+name
            data = tar.extractfile(member).read()
            if sha(data) != cfg['known_sha256'][member]:
                raise ValueError('input hash mismatch: '+name)
            path = inputs/name
            path.write_bytes(data)
            bags[name] = load_bag(path)
        for member in tar.getmembers():
            if member.isfile() and member.name.startswith('20261017/') and '/' not in member.name[9:] and member.name.endswith('.txt'):
                (inputs/Path(member.name).name).write_bytes(tar.extractfile(member).read())
    with zipfile.ZipFile(args.review_zip) as z:
        prefix = 'repo/docs/field_tests/20261018/single_car_rebuilt_20261020_v1/'
        manifest = json.loads(z.read(prefix+'input_manifest.json'))
        windows = {r['run']: r['bounds']['evaluation_window_s'] for r in manifest['selected_inputs']}
        prior_table = list(csv.DictReader(z.read(prefix+'evidence/index/oct17_static_transfer.csv').decode().splitlines()))
        for n in z.namelist():
            if '/references/U00' in n:
                (inputs/Path(n).name).write_bytes(z.read(n))

    rows, datasets = [], []
    for name, xyz in protocol['oct17_reference_points'].items():
        bag = bags[name]
        datasets.append({'id': name, 'group': 'oct17_calibration' if name==protocol['calibration_bag'] else 'oct17_static_validation',
                         'xyz': xyz, 'window': None, 'bag': bag})
    for run, ref in protocol['oct18_endpoint_references'].items():
        p = args.oct18_data/ref['bag']
        bag = load_bag(p)
        expected = next(x['sha256'] for x in manifest['selected_inputs'] if x['run']==run)
        if bag['sha256'] != expected:
            raise ValueError('Oct18 input hash mismatch')
        datasets.append({'id': run, 'group': 'oct18_endpoint_validation', 'xyz': ref['xyz'],
                         'window': windows[run], 'bag': bag})
    for d in datasets:
        bag = d['bag']
        w = d['window']
        selected = [x for x in bag['ranges'] if x[2]=='node_0' and (w is None or w[0] <= x[0] < w[1])]
        for k, a in sorted(anchors.items()):
            vals = np.array([v[k] for _, v, _ in selected if k in v])
            if len(vals) < 5:
                raise ValueError('insufficient range support')
            geom = float(np.linalg.norm(np.array(d['xyz'])-np.array(a)))
            rows.append({'dataset': d['id'], 'group': d['group'], 'node': k,
                         'x_m': d['xyz'][0], 'y_m': d['xyz'][1], 'z_m': d['xyz'][2],
                         'window_start_s': w[0] if w else '', 'window_end_s': w[1] if w else '',
                         'uwb_frames_in_window': len(selected), 'valid_samples': len(vals),
                         'median_m': float(np.median(vals)), 'std_m': float(np.std(vals)),
                         'p05_m': float(np.percentile(vals,5)), 'p95_m': float(np.percentile(vals,95)),
                         'geometry_m': geom, 'raw_minus_geometry_m': float(np.median(vals))-geom,
                         'first_half_median_m': float(np.median(vals[:len(vals)//2])),
                         'second_half_median_m': float(np.median(vals[len(vals)//2:])),
                         'bag_sha256': bag['sha256']})
    bias = {r['node']: r['raw_minus_geometry_m'] for r in rows if r['dataset']==protocol['calibration_bag']}
    if max(abs(bias[k]-cfg['calibration']['frozen_bias_m'][k]) for k in bias) > 1e-6:
        raise ValueError('P1 calibration does not reproduce archived values')
    for r in rows:
        r['P1_offset_m'] = bias[r['node']]
        r['corrected_minus_geometry_m'] = r['raw_minus_geometry_m']-bias[r['node']]
        r['absolute_residual_improvement_m'] = abs(r['raw_minus_geometry_m'])-abs(r['corrected_minus_geometry_m'])
    metrics=[]
    for d in datasets:
        rr=[r for r in rows if r['dataset']==d['id']]
        raw=np.array([r['raw_minus_geometry_m'] for r in rr])
        corrected=np.array([r['corrected_minus_geometry_m'] for r in rr])
        medians={r['node']:r['median_m'] for r in rr}
        raw_xy,raw_fit=solve_xy(medians,anchors,{})
        corr_xy,corr_fit=solve_xy(medians,anchors,bias)
        odom=np.array(d['bag']['odom'])
        if len(odom):
            if d['window'] is not None:
                odom=odom[(odom[:,0]>=d['window'][0])&(odom[:,0]<d['window'][1])]
            path=float(np.linalg.norm(np.diff(odom[:,1:3],axis=0),axis=1).sum())
            net=float(np.linalg.norm(odom[-1,1:3]-odom[0,1:3]))
        else: path=net=None
        metrics.append({'dataset':d['id'],'group':d['group'],
                        'link_count':len(rr),'raw_median_range_MAE_m':float(np.abs(raw).mean()),
                        'corrected_median_range_MAE_m':float(np.abs(corrected).mean()),
                        'raw_median_range_RMS_m':float(np.sqrt(np.mean(raw**2))),
                        'corrected_median_range_RMS_m':float(np.sqrt(np.mean(corrected**2))),
                        'corrected_max_abs_range_residual_m':float(np.abs(corrected).max()),
                        'raw_UWB_only_x_m':float(raw_xy[0]),'raw_UWB_only_y_m':float(raw_xy[1]),
                        'corrected_UWB_only_x_m':float(corr_xy[0]),'corrected_UWB_only_y_m':float(corr_xy[1]),
                        'raw_UWB_only_position_difference_m':float(np.linalg.norm(raw_xy-np.array(d['xyz'][:2]))),
                        'corrected_UWB_only_position_difference_m':float(np.linalg.norm(corr_xy-np.array(d['xyz'][:2]))),
                        'raw_UWB_only_fit_RMS_m':raw_fit,'corrected_UWB_only_fit_RMS_m':corr_fit,
                        'window_odom_path_m':path,'window_odom_net_m':net})
    groups={}
    for group in ['oct17_static_validation','oct18_endpoint_validation']:
        rr=[r for r in rows if r['group']==group]
        groups[group]={'range_link_cases':len(rr),
                       'raw_median_range_MAE_m':float(np.mean([abs(r['raw_minus_geometry_m']) for r in rr])),
                       'corrected_median_range_MAE_m':float(np.mean([abs(r['corrected_minus_geometry_m']) for r in rr])),
                       'all_link_absolute_residuals_improve':all(r['absolute_residual_improvement_m']>0 for r in rr)}
    errors=[]
    for r in prior_table:
        x=next(x for x in rows if x['dataset']==r['bag'] and x['node']==r['link'])
        errors += [abs(x['raw_minus_geometry_m']-float(r['median_range_minus_manual_geometry_m'])),
                   abs(x['corrected_minus_geometry_m']-float(r['residual_after_P1_offset_m']))]
    if max(errors)>1e-10:
        raise ValueError('historical table consistency check failed')
    # Physical geometry / bias sign check on an independent synthetic reference.
    synthetic={k:float(np.linalg.norm(np.array([1.7,3.2,.2])-np.array(a)))+bias[k] for k,a in anchors.items()}
    synth,_=solve_xy(synthetic,anchors,bias)
    if np.linalg.norm(synth-[1.7,3.2])>1e-7:
        raise ValueError('synthetic bias-sign / 3D-geometry check failed')
    for d in datasets:
        # Raw on-disk sources are never opened for writing; verify them again.
        if d['id'] in protocol['oct18_endpoint_references']:
            p=args.oct18_data/protocol['oct18_endpoint_references'][d['id']]['bag']
        else:p=inputs/d['id']
        if sha(p.read_bytes()) != d['bag']['sha256']:
            raise ValueError('source changed')
    result={'protocol':protocol,'P1_bias_m':bias,'groups':groups,'datasets':metrics,
            'inputs':[{k:v for k,v in d.items() if k!='bag'}|{'sha256':d['bag']['sha256'],'topics':d['bag']['topics'],'origin_ns':d['bag']['origin_ns']} for d in datasets],
            'verification':{'oct17_archived_table_max_difference_m':max(errors),
                            'synthetic_geometry_and_bias_sign':'passed','input_hashes':'passed',
                            'analysis_type':'raw-bag median-range transfer; no fusion rerun; no trajectory truth'},
            'provenance':{'oct17_archive_sha256':archive_sha,'review_zip_sha256':sha(args.review_zip.read_bytes()),
                          'oct17_config_sha256':sha(cfg_path.read_bytes()),'protocol_sha256':sha((base/'protocol.json').read_bytes()),
                          'script_sha256':sha(Path(__file__).read_bytes()),'python':platform.python_version(),'numpy':np.__version__}}
    dump_csv(out/'range_transfer.csv',rows)
    dump_csv(out/'point_summary.csv',metrics)
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'groups':groups,'points':metrics,'P1_bias_m':bias,'verification':result['verification']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--oct17-archive',type=Path,required=True)
    parser.add_argument('--oct17-config',type=Path,required=True)
    parser.add_argument('--oct18-data',type=Path,required=True)
    parser.add_argument('--review-zip',type=Path,required=True)
    parser.add_argument('--rosbags-path',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.rosbags_path:sys.path.append(str(args.rosbags_path))
    analyze(args)
