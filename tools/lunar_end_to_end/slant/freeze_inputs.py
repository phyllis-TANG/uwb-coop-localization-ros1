"""Extract the six #137 epochs, preserving original IEEE-754 observation values exactly."""
import csv
import gzip
import hashlib
import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / 'docs/research/lunar_end_to_end/slant'
BASE = '8acffa9f4061e4740c18c7d0f1e09d28cf7f3155'
IDS = [f't0/{car}/a{k}' for car in ('p','s') for k in range(4)]+['t0/p/s/peer']

def exact(v):
    if isinstance(v,list):
        return [exact(x) for x in v]
    return str(Fraction(v))

def write(path, data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,sort_keys=True,indent=2)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def main():
    manifest=[]; ledger=[]
    for folder,segment in [('continuous','main'),('replication','second')]:
        directory=DOC.parent/folder
        source=directory/'INPUTS.json.gz'
        records=json.loads(gzip.decompress(source.read_bytes()))
        route=json.loads((directory/'ROUTE.json').read_text())
        for epoch in ('start','mid','end'):
            for condition in ('normal','ramp_only'):
                record=next(r for r in records if r['reference']['condition']==condition and r['reference']['seed']==2026111801)
                o=record['observation']; ref=record['reference']; n=len(o['times_s'])
                i={'start':0,'mid':(n-1)//2,'end':n-1}[epoch]
                key=f'{segment}_{epoch}_{condition}'
                model=dict(anchors=exact(o['anchors']),heights=exact(o['heights'][i]),ranges=exact(o['ranges'][i]),measurement_ids=IDS,variance=['1/625']*9,bias=['-3/5','3/5'])
                assert o['sigma_range']==.04 and len(model['ranges'])==9
                values=dict(xyz=exact(ref['xyz'][i]),injected_bias=exact(ref['bias'][i]),generated_noise=exact(ref['range_noise'][i]))
                assert all(Fraction(x[2])==Fraction(h) for x,h in zip(values['xyz'],model['heights']))
                so=write(DOC/'inputs'/f'{key}.json',model);ev=write(DOC/'evaluation'/f'{key}.json',values)
                t=route['source_times_car2_s'][0]+o['times_s'][i]
                manifest.append(dict(case=key,seed=2026111801,source_file=str(source.relative_to(ROOT)),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),source_observation_id=o['id'],index=i,epoch=epoch,condition=condition,car1_source_s=t+5,car2_source_s=t,solver_sha256=so,evaluation_sha256=ev,anchor_geometry_observations_sha256=digest([model['anchors'],model['heights'],model['ranges'][:8]])))
                for method in ('P4','N4'):
                    ledger.append(dict(case=key,method=method,status='NOT_RUN_PENDING_A_READY',certificate='NOT_CHECKED',resolution_met='',budget_stop='',original_event='',joint_hit='',p_hit='',s_hit='',p_area_upper='',s_area_upper='',p_radius='',s_radius='',nodes='',wall_seconds=''))
    write(DOC/'INPUT_MANIFEST.json',dict(base=BASE,coordinate_transform='moon_map meters Z-up, source C=diag(1,-1,-1); exported positions already transformed',methods=dict(P4=dict(ids=IDS,q=26),N4=dict(ids=IDS[:8],q=24)),records=manifest))
    with (DOC/'LEDGER.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0]),lineterminator='\n');w.writeheader();w.writerows(ledger)
if __name__=='__main__':main()
