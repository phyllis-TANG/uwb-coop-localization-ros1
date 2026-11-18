"""Prepare the runtime-only development feed from the original sensor generator."""
import argparse
import hashlib
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/ground_continuous_b'))
from run_b import generate, simulate
from legacy import wrap

OUT = ROOT / 'docs/research/ground_b_round2/runtime'


def export(seed, scene):
    folder = OUT / f'{seed}_{scene}'
    cfg, events, _ = generate(seed, scene)
    epoch = simulate.EPOCH_NS
    fields = ('vehicle_id', 'kind', 'header_epoch_ns', 'receive_epoch_ns', 'source_observation_id')
    messages = []
    indexed = {}
    last_yaw = {}
    local_pose = {}
    for event in events:
        kind = event['kind']
        if kind not in ('uwb', 'odom'):
            continue
        car = event['vehicle_id']
        keys = ['pose'] if kind == 'odom' else [
            *sorted(cfg['models'][car]['anchors_xyz_m']), {'car1':'node_0','car2':'node_1'}[car]]
        msg = {k:event[k] for k in fields}
        msg['value'] = {k:event['value'][k] for k in keys}
        if kind == 'odom':
            x,y,yaw = msg['value']['pose']
            if car in last_yaw:
                yaw = last_yaw[car] + wrap(yaw-last_yaw[car])
            last_yaw[car] = yaw
            local_pose[car,event['header_epoch_ns']] = [x,y,yaw]
        messages.append(msg)
        indexed[car,kind,event['header_epoch_ns']] = msg

    # The archive contains downsampled odometry, raw epoch ranges and source IDs.
    archive = ROOT / f'docs/research/ground_continuous_b/runs/{seed}_{scene}/records.json.gz'
    with gzip.open(archive,'rt') as f:
        records = json.load(f)
    assert len(records) == 63
    for row in records:
        obs = row['obs']
        stamp = epoch + row['t'] * 10**9
        frames = [indexed[c,'uwb',stamp] for c in ('car1','car2')]
        values = [m['value'][k] for m in frames for k in obs['anchor_order']]
        assert values + [frames[0]['value']['node_0']] == obs['ranges']
        assert [m['source_observation_id'] for m in frames] == obs['ids']
        assert (max(m['receive_epoch_ns'] for m in frames)-epoch)/1e9 == obs['received']
        for car in ('car1','car2'):
            assert local_pose[car,stamp] == row['bins'][car]['local_odom']
    assert len(messages) == len(indexed) == 5124
    assert all(a['receive_epoch_ns'] <= b['receive_epoch_ns'] for a,b in zip(messages,messages[1:]))
    models = {car:{k:model[k] for k in ('anchors_xyz_m','antenna_height_m',
              'base_to_antenna_body_xy_m','initial_heading_deg','start_antenna_xyz_m','graph_parameters')}
              for car,model in cfg['models'].items()}
    geometry = dict(epoch_ns=epoch, prior_state_s=1, models=models, raw_range_sigma_m=.04,
                    odom_body_step_xy_sigma_m=.002,odom_step_yaw_sigma_rad=.0008)
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
    data = ''.join(json.dumps(m,separators=(',',':'))+'\n' for m in messages)
    with (folder/'events.jsonl.gz').open('wb') as raw, gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as f:
        f.write(data.encode())
    sums = [hashlib.sha256((folder/name).read_bytes()).hexdigest()+'  '+name for name in ('events.jsonl.gz','geometry.json')]
    (folder/'SHA256SUMS').write_text('\n'.join(sums)+'\n')
    print(f'{seed}_{scene}: {len(messages)} sensor events; matched {len(records)*9} ranges and {2*len(records)} local poses')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('seed',type=int,choices=[101,2026111901,2026111902])
    parser.add_argument('scene',choices=['nominal','wall','peer_ramp','peer_step'])
    args = parser.parse_args()
    export(args.seed,args.scene)
