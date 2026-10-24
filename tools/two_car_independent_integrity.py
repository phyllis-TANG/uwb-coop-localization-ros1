#!/usr/bin/env python3
"""Receipt-association v1 adapter. Original locator and monitors stay untouched."""
from __future__ import annotations
import bisect
import collections
import copy
import math
from pathlib import Path
import numpy as np
from single_car_sequential_replay import Event

ROOT = Path(__file__).resolve().parents[1]
CARS = ('car1', 'car2')
TAGS = {'car1': 'node_1', 'car2': 'node_0'}
PEERS = {'car1': 'node_0', 'car2': 'node_1'}
ANCHORS = ('node_10', 'node_2', 'node_3', 'node_8')


def adapt_message(topic, msg, receipt_ns, origin_ns, car):
    """Return estimator event and external provenance. No peer value crosses API.

    Event.header_s is the *association* coordinate for this version only.
    Raw headers are preserved losslessly as integer ns in external provenance.
    Unknown/other-car messages are clock ticks, never measurements for this car.
    """
    if car not in CARS:
        raise ValueError('Unknown car')
    received = (int(receipt_ns)-int(origin_ns))/1e9
    if topic not in ('/'+car+'/odom', '/'+car+'/uwb/ranges'):
        return Event(received, 'clock'), None
    stamp = msg.header.stamp
    header_ns = int(stamp.sec)*10**9+int(stamp.nanosec)
    if header_ns <= 0:
        raise ValueError('Invalid original header: '+topic)
    meta = dict(car=car, topic=topic, origin_bag_receipt_ns=int(origin_ns),
                original_header_ns=header_ns, original_header_relative_s=(header_ns-origin_ns)/1e9,
                bag_receipt_ns=int(receipt_ns), bag_receipt_s=received,
                association_time_s=received, frame_id=msg.header.frame_id)
    if topic.endswith('/odom'):
        if msg.header.frame_id != car+'/odom_combined' or msg.child_frame_id != 'base_footprint':
            raise ValueError('Unexpected Odom identity/frame: '+topic)
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        norm = math.sqrt(q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w)
        if not np.isfinite(norm) or not .5 <= norm <= 1.5:
            raise ValueError('Invalid Odom quaternion')
        x,y,z,w = q.x/norm,q.y/norm,q.z/norm,q.w/norm
        yaw = math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
        pose = [float(p.x),float(p.y),yaw]
        if not np.isfinite(pose).all():
            raise ValueError('Invalid Odom position')
        meta.update(kind='odom', local_pose=pose, child_frame_id=msg.child_frame_id,
                    linear_velocity_m_s=[float(msg.twist.twist.linear.x),float(msg.twist.twist.linear.y)],
                    angular_velocity_rad_s=float(msg.twist.twist.angular.z))
        return Event(received,'odom',received,pose), meta
    if msg.tag_id != TAGS[car] or msg.header.frame_id != car+'/uwb_linktrack':
        raise ValueError('Unexpected UWB identity/frame: '+topic)
    groups = collections.defaultdict(list)
    for entry in msg.ranges:
        groups[entry.anchor_id].append(float(entry.range))
    unique = {k:v[0] for k,v in groups.items() if len(v)==1 and np.isfinite(v[0])}
    meta.update(kind='uwb', tag_id=msg.tag_id,
                raw_entries={k:[x if np.isfinite(x) else None for x in v] for k,v in groups.items()},
                duplicate_groups=sum(len(v)!=1 for v in groups.values()),
                wall_raw_m={k:v for k,v in unique.items() if k in ANCHORS},
                peer_raw_m=unique.get(PEERS[car]))
    return Event(received,'uwb',received,meta['wall_raw_m'].copy()), meta


def bag_events(path, car, diagnostics, provenance_sink=lambda row: None):
    from rosbags.highlevel import AnyReader
    origin = last = None
    counts = collections.Counter()
    gaps = collections.defaultdict(list)
    headers = collections.defaultdict(list)
    duplicates = 0
    with AnyReader([Path(path)]) as reader:
        for connection, ns, raw in reader.messages():
            if origin is None:
                origin = int(ns)
            last = int(ns)
            topic = connection.topic
            selected = topic in ('/'+car+'/odom', '/'+car+'/uwb/ranges')
            msg = reader.deserialize(raw,connection.msgtype) if selected else None
            event, meta = adapt_message(topic,msg,ns,origin,car)
            counts[topic] += 1
            if meta is not None:
                provenance_sink(meta)
                gaps[topic].append((ns-meta['original_header_ns'])/1e9)
                headers[topic].append(meta['original_header_ns'])
                duplicates += meta.get('duplicate_groups',0)
            yield event
    diagnostics.update(origin_bag_receipt_ns=origin, last_bag_receipt_ns=last,
        eof_receipt_s=(last-origin)/1e9, topic_counts=dict(counts), duplicate_uwb_id_groups=duplicates,
        timing={t:dict(header_nonincreasing_steps=int(np.sum(np.diff(headers[t])<=0)),
            receipt_minus_header_s=dict(zip(['min','median','p95','max'],map(float,np.percentile(v,[0,50,95,100])))))
            for t,v in gaps.items()}, imu_factors=0, peer_factors=0,
        association_version='bag-receipt-v1; no physical synchronization claim')


def make_config(template, parent, calibration, case, car):
    """Only estimator fields; evaluation coordinates never enter the config."""
    out = copy.deepcopy(template)
    model = out['model']
    model.update(anchors_xyz_m=copy.deepcopy(parent['anchors_xyz_m']),
        range_bias_m=copy.deepcopy(calibration['applied_biases_m'][car]),
        start_antenna_xyz_m=list(case['start_antenna_xyz_m'][car]),
        initial_heading_deg=case['initial_heading_deg'][car],
        base_to_antenna_body_xy_m=list(parent['mounts'][car]['lever_xy_m']),
        antenna_height_m=parent['mounts'][car]['height_m'],
        graph_parameters=copy.deepcopy(parent['graph_parameters']))
    out['replay']['association_version'] = 'bag-receipt-v1'
    assert out['lag_s']==20 and out['max_nfev']==50
    return out


def odom_bracket(trace, state_time, cutoff):
    """Independent provenance audit, considering only arrived endpoints."""
    rows = [r for r in trace if r['kind']=='odom' and r['bag_receipt_s']<=cutoff]
    stamps = [r['association_time_s'] for r in rows]
    i = bisect.bisect_left(stamps,state_time)
    if i<len(rows) and stamps[i]==state_time:
        pair = [rows[i],rows[i]]
    elif 0<i<len(rows):
        pair = [rows[i-1],rows[i]]
    else:
        return None
    keys = ('original_header_ns','bag_receipt_ns','bag_receipt_s','association_time_s')
    return [{k:r[k] for k in keys} for r in pair]
