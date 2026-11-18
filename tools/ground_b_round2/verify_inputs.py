"""Check the published bytes, including paired links between archive epochs."""
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT/'docs/research/ground_b_round2'
OLD = ROOT/'docs/research/ground_continuous_b/runs'
SEEDS = (101,2026111901,2026111902)
SCENES = ('nominal','peer_step','peer_ramp','wall')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(folder):
    with gzip.open(folder/'events.jsonl.gz','rt') as f:
        return [json.loads(line) for line in f]


def verify():
    entries=[]
    for seed in SEEDS:
        base=DOC/'runtime'/f'{seed}_nominal'
        nominal=read(base)
        geometry=json.loads((base/'geometry.json').read_text())
        epoch=geometry['epoch_ns']
        for scene in SCENES:
            name=f'{seed}_{scene}'
            folder=DOC/'runtime'/name
            data=read(folder)
            assert len(data)==len(nominal)==5124 and geometry['prior_state_s']==1
            assert digest(base/'geometry.json')==digest(folder/'geometry.json')
            changes=0
            for raw,other in zip(nominal,data,strict=True):
                assert raw.keys()==other.keys() and all(raw[k]==other[k] for k in raw if k!='value')
                t=(raw['header_epoch_ns']-epoch)/1e9
                delta={}
                if raw['kind']=='uwb' and raw['vehicle_id']=='car1' and 24<=t<38:
                    if scene=='wall':
                        delta=dict.fromkeys(geometry['models']['car1']['anchors_xyz_m'],.3)
                    elif scene=='peer_step':
                        delta['node_0']=.6
                    elif scene=='peer_ramp':
                        delta['node_0']=.6*((t-24)/13.95)
                expected=dict(raw['value'])
                for key,offset in delta.items():
                    expected[key]+=offset
                    changes+=offset!=0
                assert expected==other['value']
            original=OLD/name/'records.json.gz'
            with gzip.open(original,'rt') as f:
                records=json.load(f)
            uwb={r['source_observation_id']:r for r in data if r['kind']=='uwb'}
            for r in records:
                obs=r['obs']
                frames=[uwb[i] for i in obs['ids']]
                assert all(m['header_epoch_ns']==epoch+r['t']*10**9 for m in frames)
                assert obs['received']==(max(m['receive_epoch_ns'] for m in frames)-epoch)/1e9
                assert obs['ranges']==[m['value'][k] for m in frames for k in obs['anchor_order']]+[frames[0]['value']['node_0']]
            entries.append(dict(package=name,frames=len(data),archive_ranges=9*len(records),
                archive_pose_checks=2*len(records),uwb_ids=2*len(records),joint_receipts=len(records),
                changed_scalar_measurements=changes,events_sha256=digest(folder/'events.jsonl.gz'),
                geometry_sha256=digest(folder/'geometry.json'),source_records_sha256=digest(original)))
    for name in ('geometry.json','events.jsonl.gz'):
        assert digest(DOC/'runtime/101_nominal'/name)==digest(ROOT/'docs/research/ground_b_round1/runtime'/name)
    with (DOC/'PACKAGES.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=entries[0],lineterminator='\n')
        w.writeheader()
        w.writerows(entries)


if __name__=='__main__':
    verify()
