"""Frozen confirmation-only static field adapter + pinned graph core.

Uses VM receipt time, not uncalibrated cross-machine header alignment. State XY
is the static antenna origin, with zero *model* lever; this is not a measured
body extrinsic and the adapter must not be used for moving vehicles.
"""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
import argparse
import bisect
import collections
import copy
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).parent
PROJECT = HERE.parents[2]
ACQ = PROJECT / 'outputs/field_measurements_20261031/v001'
CORE = PROJECT / 'outputs/pr87_review_20261030/v001/snapshot/tools/two_car_fixed_lag_fgo_v1'
sys.path.insert(0, str(CORE))
import graph
import legacy
CARS = ('car1', 'car2')
ALLOWED = ('G1_R2_W1','G1_R2_N','G1_R3_N','G1_R3_W1','G2_R1_N','G2_R1_W1','G2_R2_W1','G2_R2_N','G2_R3_N','G2_R3_W1')
ARMS = {'I': 0., 'J': 1., 'W025': .25}
WALLS = ('node_10', 'node_2', 'node_3', 'node_8')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def table(path, rows):
    if not rows:
        return
    with Path(path).open('x', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def source_lock():
    paths = [CORE/'graph.py', CORE/'legacy.py', CORE/'config.json', CORE/'dependency_lock.json',
             Path(__file__), ACQ/'P00_QC/bag_decoder_snapshot.py']
    paths += [legacy.ROOT/name for name in legacy.LOCK['files']]
    return {str(p): sha(p) for p in paths}


def specification():
    return dict(status='confirmation_protocol_v001',
        allowed_run_ids=list(ALLOWED), estimator='existing pinned WindowGraph; no source modifications',
        case_scope='static antenna-frame reduction, not dynamic body-frame calibration',
        state='antenna XY plus auxiliary yaw; fixed historical antenna heights',
        initial='independent per-car four-wall-only first-five-receipt-second bootstrap; no surveyed XY or peer',
        timing='VM bag receipt order; integer ns; 1Hz cutoff; trailing 0.8s median; no future input',
        minimum_per_wall_or_peer_samples=5, bootstrap_s=5, first_keyframe_s=6,
        max_odom_age_s=.5, static_odom_translation_gate_m=.001,
        core_inherited=dict(lag_s=20, wall_sigma_m=.2, peer_sigma_m=.2,
                            odom_translation_sigma_m=.03, initial_prior_sigma_m=.2),
        fixed_strength=ARMS, weight_definition='multiply original peer pseudo-Huber residual AND Jacobian by sqrt(weight); keep robust scale fixed',
        peer='car1-to-car2 only; reverse diagnostic, not a second independent factor',
        ranges='parsed bridge canonical once; raw topics not duplicated as additional factors',
        no_range_bias_calibration=True, imu_factors=0,
        phases='normal electronic-start+40:55; human hold_ack+5:25; recovery returned_ack+60:85; P00 normal bag-start+40:55',
        score='same run/car/reference/time; common accepted I/J/W025; per-window descriptive, not population MSE',
        reference_epsilon_m=[0,.01,.02,.05,.10], epsilon_status='hypothetical sensitivity, not measured uncertainty',
        reference_bound='static shared point: meanD(r) +/- 2*epsilon*norm(mean(c-i)); no epsilon certification',
        limitations=['Receipt time does not establish physical action latency or a calibrated dynamic clock.',
                     'Normal operation is not zero-bias certification; both vehicles can be biased.',
                     'Engineering graph weights are not calibrated sampling covariance.',
                     'Fixed-height installation and anchor uncertainty have not been quantified.',
                     'Single static run and correlated keyframes are not independent experimental repetitions.',
                     'Single-update theoretical MSE boundary is not an exact theorem for nonlinear fixed-lag outputs.'])


def load_confirmation(entry):
    if entry['run_id'] not in ALLOWED or entry['assigned_use'] != 'reserved_confirmation':
        raise ValueError('Only the ten preassigned reserved bags may be opened')
    bag = Path(entry['bag_path'])
    if sha(bag) != entry['sha256']:
        raise ValueError('Bag identity changed')
    decoder_path = ACQ/'P00_QC/bag_decoder_snapshot.py'
    spec = importlib.util.spec_from_file_location('field_bag_decoder', decoder_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    connections, messages = mod.load_bag(bag)
    decoders = {cid: mod.Decoder(c['type'], c['definition']) for cid,c in connections.items()}
    origin = min(r for _,r,_ in messages)
    streams = {c: [] for c in CARS}
    odom = {c: [] for c in CARS}
    events = []
    offsets = collections.defaultdict(list)
    for index,(cid,receipt,payload) in enumerate(messages):
        topic = connections[cid]['topic']
        if topic not in ('/car1/uwb/ranges','/car2/uwb/ranges','/car1/odom','/car2/odom','/experiment/events'):
            continue
        msg = decoders[cid].decode(payload, connections[cid]['type'])
        if topic == '/experiment/events':
            event = json.loads(msg['data'])
            event['receipt_ns'] = receipt
            events.append(event)
            continue
        car = topic.split('/')[1]
        h = msg['header']['stamp']
        offsets[topic].append((h['secs']*10**9+h['nsecs']-receipt)/1e9)
        if topic.endswith('/ranges'):
            expected_tag = 'node_1' if car == 'car1' else 'node_0'
            if msg['tag_id'] != expected_tag:
                raise ValueError('Physical tag identity mismatch')
            values = {}
            for r in msg['ranges']:
                if r['anchor_id'] in values:
                    raise ValueError('Duplicate chain in a frame')
                if math.isfinite(r['range']) and r['range'] > 0:
                    values[r['anchor_id']] = float(r['range'])
            streams[car].append((receipt,index,values))
        else:
            if msg['header']['frame_id'] != car+'/odom' or msg['child_frame_id'] != car+'/base_footprint':
                raise ValueError('Unexpected odometry frame')
            p = msg['pose']['pose']['position']
            q = msg['pose']['pose']['orientation']
            yaw = math.atan2(2*(q['w']*q['z']+q['x']*q['y']),1-2*(q['y']**2+q['z']**2))
            odom[car].append((receipt,index,[p['x'],p['y'],yaw]))
    for car in CARS:
        streams[car].sort(key=lambda x:x[:2])
        odom[car].sort(key=lambda x:x[:2])
        states = np.asarray([o[2] for o in odom[car]])
        excursion = float(np.max(np.linalg.norm(states[:,:2]-states[0,:2],axis=1)))
        if excursion > .001:
            raise ValueError('Static-only antenna-frame adapter refuses moving odometry')
    diag = {t:dict(min_s=float(min(v)),median_s=float(np.median(v)),max_s=float(max(v))) for t,v in offsets.items()}
    return dict(origin_ns=origin, end_ns=max(r for _,r,_ in messages), streams=streams, odom=odom,
                events=events, header_minus_receipt_diagnostics=diag)


def bootstrap(streams, origin, base):
    config = copy.deepcopy(base)
    config['scope'] = 'field_static_development_antenna_frame_not_dynamic'
    config['provenance'] = dict(clock='common VM bag receipt domain, not synchronized sensor-header domain',
        initial='first five seconds four-wall data only, same initialization for all three arms',
        geometry='historical unchanged anchors/heights; no accepted extrinsic uncertainty model',
        weights='inherited engineering assumptions, not calibrated probability model')
    evidence = {}
    for car in CARS:
        grouped = {k:[] for k in WALLS}
        for stamp,_,values in streams[car]:
            if stamp > origin+5_000_000_000:
                break
            for k in WALLS:
                if k in values:
                    grouped[k].append(values[k])
        if any(len(v)<5 for v in grouped.values()):
            raise ValueError('Insufficient four-wall bootstrap')
        measured = np.asarray([np.median(grouped[k]) for k in WALLS])
        m = config['models'][car]
        anchors = np.asarray([m['anchors_xyz_m'][k] for k in WALLS])
        z = m['antenna_height_m']
        a = 2*(anchors[1:,:2]-anchors[0,:2])
        b = (np.sum(anchors[1:,:2]**2,axis=1)-np.sum(anchors[0,:2]**2)
             +(z-anchors[1:,2])**2-(z-anchors[0,2])**2-(measured[1:]**2-measured[0]**2))
        seed = np.linalg.lstsq(a,b,rcond=None)[0]
        solution = least_squares(lambda xy:np.linalg.norm(np.r_[xy,z]-anchors,axis=1)-measured,
                                 seed,loss='soft_l1',f_scale=.2,max_nfev=100)
        if not solution.success or not np.isfinite(solution.x).all():
            raise ValueError('UWB-only initialization failed')
        m['start_antenna_xyz_m'] = [*solution.x.tolist(),z]
        m['base_to_antenna_body_xy_m'] = [0.,0.]
        m['initial_heading_deg'] = 0.
        m['range_bias_m'] = {k:0. for k in WALLS}
        evidence[car] = dict(wall_medians_m=dict(zip(WALLS,measured.tolist())),
            initialized_antenna_xyz_m=m['start_antenna_xyz_m'], initialization_uses_reference_xy=False,
            range_fit_residuals_m=(np.linalg.norm(np.r_[solution.x,z]-anchors,axis=1)-measured).tolist())
    return config,evidence


def make_bins(data):
    origin = data['origin_ns']
    stamps = {c:[r[0] for r in data['streams'][c]] for c in CARS}
    odom_stamps = {c:[r[0] for r in data['odom'][c]] for c in CARS}
    bins = []
    for k in range(6,int((data['end_ns']-origin)//10**9)+1):
        cutoff = origin+k*10**9
        observations,counts,local,dependency = {},{},[],0
        for car in CARS:
            left = bisect.bisect_left(stamps[car],cutoff-800_000_000)
            right = bisect.bisect_right(stamps[car],cutoff)
            grouped = collections.defaultdict(list)
            for stamp,_,values in data['streams'][car][left:right]:
                dependency = max(dependency,stamp)
                for key,value in values.items():
                    grouped[key].append(value)
            counts[car] = {key:len(v) for key,v in grouped.items()}
            observations[car] = {key:float(np.median(grouped[key])) for key in WALLS if len(grouped[key])>=5}
            peer_key = 'node_0' if car == 'car1' else 'node_1'
            observations[car]['_peer'] = float(np.median(grouped[peer_key])) if len(grouped[peer_key])>=5 else None
            pos = bisect.bisect_right(odom_stamps[car],cutoff)-1
            if pos<0 or cutoff-odom_stamps[car][pos]>500_000_000:
                raise ValueError('Missing/stale arrived odometry')
            dependency = max(dependency,odom_stamps[car][pos])
            local.append(data['odom'][car][pos][2])
        if dependency>cutoff:
            raise AssertionError('Future receipt leaked into a bin')
        bins.append(dict(second=k,cutoff_ns=cutoff,dependency_max_ns=dependency,
            local=local,wall={c:{k:v for k,v in observations[c].items() if k!='_peer'} for c in CARS},
            peer=observations['car1']['_peer'],reverse_peer=observations['car2']['_peer'],counts=counts))
    return bins


def replay(bins, config, weight, label, progress=True):
    original_peer = graph.peer_residual
    def weighted_peer(*args,**kwargs):
        r,j = original_peer(*args,**kwargs)
        return math.sqrt(weight)*r,math.sqrt(weight)*j
    graph.peer_residual = weighted_peer
    rows = []
    started = time.monotonic()
    try:
        model = graph.WindowGraph(config,peer_enabled=weight>0)
        for i,b in enumerate(bins):
            if time.monotonic()-started>600:
                raise TimeoutError('Bounded development replay runtime exceeded')
            result = model.update(b['second'],b['local'],b['wall'],b['peer'])
            rows.append(dict(second=b['second'],cutoff_ns=b['cutoff_ns'],dependency_max_ns=b['dependency_max_ns'],
                pose=result['pose'],accepted=result['accepted_graph'],status=result['status'],
                wall_factors=sum(len(v) for v in b['wall'].values()),peer_used=weight>0 and b['peer'] is not None,
                nfev=result.get('optimizer',{}).get('nfev'),marginalizations=result['marginalizations']))
            if progress and (i+1)%60==0:
                print(json.dumps(dict(progress=label,processed=i+1,total=len(bins))),flush=True)
    finally:
        graph.peer_residual = original_peer
    if graph.peer_residual is not original_peer:
        raise AssertionError('Graph kernel peer function not restored')
    return rows


def meaningful_checks(config,bins,outputs):
    prefix = bins[:9]
    small_i = replay(prefix,config,0,'test',False)
    changed = copy.deepcopy(prefix)
    for b in changed:
        b['peer'] = 20.
    changed_i = replay(changed,config,0,'test',False)
    np.testing.assert_allclose([r['pose'] for r in small_i],[r['pose'] for r in changed_i],atol=1e-10,rtol=0)
    small_j = replay(prefix,config,1,'test',False)
    np.testing.assert_allclose([r['pose'] for r in small_j],[r['pose'] for r in outputs['J'][:9]],atol=1e-10,rtol=0)
    for r in small_i:
        if r['accepted']:
            pos = r['pose']
            x=np.asarray(pos);delta=1e-5
            # Independent no-peer block factor: off-block derivative must be zero.
            obj=graph.Objective([r['second']],np.asarray([prefix[0]['local']]),
                [prefix[0]['wall']],[prefix[0]['peer']],config,graph.joint_initial(config),False)
            _,j=obj.evaluate(x)
            if np.any(np.sum(np.abs(j[:,:3]),axis=1)*np.sum(np.abs(j[:,3:]),axis=1)>1e-12):
                raise AssertionError('Independent objective mixes vehicle blocks')
            break
    return dict(no_peer_leak_into_I=True,causal_prefix_J_exact=True,independent_factor_blocks=True,
                all_dependency_receipts_before_cutoff=all(b['dependency_max_ns']<=b['cutoff_ns'] for b in bins))


def phase_windows(data):
    by_name = {e['event']:e['receipt_ns'] for e in data['events']}
    origin = data['origin_ns']
    start = by_name.get('start',origin)
    windows = {'normal':[(start-origin)/1e9+40,(start-origin)/1e9+55]}
    if 'hold_ack' in by_name and 'returned_ack' in by_name:
        windows['human']=[(by_name['hold_ack']-origin)/1e9+5,(by_name['hold_ack']-origin)/1e9+25]
        windows['recovery']=[(by_name['returned_ack']-origin)/1e9+60,(by_name['returned_ack']-origin)/1e9+85]
    return windows


def evaluate(outputs,windows,reference):
    rows = []
    for phase,(start,end) in windows.items():
        selected = [k for k,r in enumerate(outputs['I']) if start<=r['second']<=end]
        common = [k for k in selected if all(outputs[a][k]['accepted'] for a in ARMS)]
        if not common:
            raise ValueError('No common accepted phase publications')
        for ci,car in enumerate(CARS):
            r = np.asarray(reference[car])
            poses={a:np.asarray([outputs[a][k]['pose'][ci*3:ci*3+2] for k in common]) for a in ARMS}
            err={a:np.linalg.norm(v-r,axis=1) for a,v in poses.items()}
            for arm in ('J','W025'):
                d = float(np.mean(err[arm]**2-err['I']**2))
                delta = np.mean(poses[arm]-poses['I'],axis=0)
                radius = None if np.linalg.norm(delta)<1e-15 else abs(d)/(2*np.linalg.norm(delta))
                row=dict(phase=phase,car=car,arm=arm,n_common=len(common),n_scheduled=len(selected),
                    independent_rmse_m=float(np.sqrt(np.mean(err['I']**2))),
                    arm_rmse_m=float(np.sqrt(np.mean(err[arm]**2))),
                    rmse_difference_m=float(np.sqrt(np.mean(err[arm]**2))-np.sqrt(np.mean(err['I']**2))),
                    paired_mean_squared_error_difference_m2=d,
                    mean_arm_minus_I_xy_m=delta.tolist(),nominal_direction='improve' if d<0 else 'harm' if d>0 else 'tie',
                    reference_robustness_radius_m=radius,
                    reference_uncertainty_certified=False,
                    independent_bias_xy_m=np.mean(poses['I']-r,axis=0).tolist(),
                    arm_bias_xy_m=np.mean(poses[arm]-r,axis=0).tolist())
                row['hypothetical_reference_sensitivity']={}
                for eps in (0,.01,.02,.05,.10):
                    half=2*eps*float(np.linalg.norm(delta))
                    low,high=d-half,d+half
                    row['hypothetical_reference_sensitivity'][str(eps)]=dict(lower_m2=low,upper_m2=high,
                        direction='improve' if high<0 else 'harm' if low>0 else 'indeterminate')
                rows.append(row)
    return rows

