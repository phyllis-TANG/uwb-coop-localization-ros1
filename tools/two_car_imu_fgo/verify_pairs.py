#!/usr/bin/env python3
"""Input/output pairing check on saved files, with no generator or online imports."""
import argparse
import json
from pathlib import Path
import numpy as np
import independent as ind
from evaluate import dump,sha


def run(a,output):
    a=Path(a);out={};origin=1790000000000000000
    index=json.loads((a/'synthetic-v1/RUN_INDEX.json').read_text())
    for seed in (101,211):
        nominal=a/'synthetic-v1/inputs'/f'nominal_seed{seed}';base=ind.lines(nominal/'events.jsonl.gz')
        # Header origin is part of the frozen independent evaluator truth.
        truth=ind.lines(nominal/'truth.jsonl.gz');origin=truth[0]['state_epoch_ns']-round(truth[0]['time_s']*1e9)
        key=lambda e:(e['vehicle_id'],e['kind'],e['source_observation_id'])
        nb={key(e):e for e in base};checked={}
        for scene in ('nominal','gyro_constant_bias','car1_gyro_gap','peer_bias','car1_common_wall_bias'):
            path=a/'synthetic-v1/inputs'/f'{scene}_seed{seed}';ev=ind.lines(path/'events.jsonl.gz');lookup={key(e):e for e in ev}
            ind.require(len(lookup)==len(ev),'source identity uniqueness')
            modified=0
            for k,e in nb.items():
                t=(e['header_epoch_ns']-origin)/1e9 if e['header_epoch_ns'] is not None else None
                omitted=scene=='car1_gyro_gap' and e['kind']=='imu' and e['vehicle_id']=='car1' and 24<=t<38
                if omitted:ind.require(k not in lookup,'declared gap not applied');continue
                f=lookup[k];ind.require((e['header_epoch_ns'],e['receive_epoch_ns'],e['topic'])==(f['header_epoch_ns'],f['receive_epoch_ns'],f['topic']),'paired timing/topic')
                want=json.loads(json.dumps(e['value']))
                if scene=='gyro_constant_bias' and e['kind']=='imu':want['angular_velocity_rad_s'][2]+=.025 if e['vehicle_id']=='car1' else -.015
                if scene=='car1_common_wall_bias' and e['kind']=='uwb' and e['vehicle_id']=='car1' and 24<=t<38:
                    for n in ('node_2','node_3','node_8','node_10'):want[n]+=.30
                if scene=='peer_bias' and e['kind']=='uwb' and e['vehicle_id']=='car1' and 24<=t<38:want['node_0']+=1.2
                ind.require(want==f['value'],'undeclared value change '+scene+'/'+str(k))
                modified+=int(want!=e['value'])
            ind.require(set(lookup)<=set(nb),'unexpected new source identities')
            ind.require(sha(path/'config.json')==sha(nominal/'config.json'),'non-IMU config changed')
            cells=[c for c in index['cells'] if c['case']==path.name]
            ind.require(len(cells)==4 and {c['input_sha256'] for c in cells}=={sha(path/'events.jsonl.gz')},'four methods share exact bytes')
            checked[scene]=dict(records=len(ev),modified_values=modified,omitted_records=len(nb)-len(lookup))
        # No-peer Car2 cannot acquire Car1 wall fault information. Allow FP order.
        responses={}
        for method in ('M0','M2'):
            p=a/'synthetic-v1/runs';n=ind.lines(p/f'nominal_seed{seed}_{method}'/'updates.jsonl.gz');w=ind.lines(p/f'car1_common_wall_bias_seed{seed}_{method}'/'updates.jsonl.gz')
            stride=3 if method=='M0' else 4;delta=max(float(np.max(np.abs(np.array(x['pose'][stride:])-y['pose'][stride:]))) for x,y in zip(n,w))
            ind.require(delta<1e-4,'independent healthy companion changed');responses[method]=delta
        out[str(seed)]=dict(inputs=checked,healthy_independent_state_max_abs_difference=responses)
    dump(output,dict(status='PASS',checks=out,scope='saved inputs only; metadata case/source recipe differs intentionally; no fresh experimental execution'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--artifacts',type=Path,required=True);p.add_argument('--output',type=Path,required=True);v=p.parse_args()
    if v.output.exists():raise FileExistsError(v.output)
    run(v.artifacts,v.output)
