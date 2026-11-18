"""Translate the frozen Moon_1 solver inputs to READY v1, preserving raw rationals."""
import json
from pathlib import Path
from batch import load
import checker as C

SOURCE='3b68bcf0df9de496cf7353f3cd506a06e5a6f40c'
LUNAR='docs/research/lunar_end_to_end/slant'
OUT=Path('docs/research/midterm_dual_robot_contract_a/height_v1/lunar')


def write(path,obj):
    path.write_text(json.dumps(obj,indent=2)+'\n')


def main():
    manifest,_=load(SOURCE,LUNAR+'/INPUT_MANIFEST.json')
    OUT.mkdir(exist_ok=True)
    plan=[]
    for r in manifest['records']:
        case=r['case']
        raw,sha=load(SOURCE,f'{LUNAR}/inputs/{case}.json')
        C.need(sha==r['solver_sha256'],'LUNAR_INPUT_BYTES')
        time=C.F(r['car2_source_s'])
        C.need(float(time+5)==r['car1_source_s'],'SOURCE_CLOCK')
        x=C.K.seal(dict(schema_version=C.VERSION,source_commit=C.BASE,case_id=case,
            units='m',frame='moon_map_z_up',source_times={'p':str(time+5),'s':str(time)},
            domain_source='joint_event_26',anchors={f'a{i}':v for i,v in enumerate(raw['anchors'])},
            heights=dict(zip(('p','s'),raw['heights'])),measurement_ids=raw['measurement_ids'],
            variance=raw['variance'],observations=[[v,v] for v in raw['ranges']],bias_domain=raw['bias'],
            arithmetic_policy=C.K.POLICY,budget={'max_nodes':50000,'max_seconds':'30','position_resolution':'1/20'}))
        path=OUT/(case+'.json')
        C.event_root(x)
        write(path,x)
        plan.append(dict(segment='1' if case.startswith('main_') else '2',epoch={'mid':'middle'}.get(r['epoch'],r['epoch']),
                         condition={'ramp_only':'ramp'}.get(r['condition'],r['condition']),input=str(path),
                         input_hash=x['input_hash'],raw_source_commit=SOURCE,raw_sha256=sha,
                         source_observation_id=r['source_observation_id'],recorded_times=[r['car1_source_s'],r['car2_source_s']]))
    write(OUT/'plan.json',plan)


if __name__=='__main__':
    main()
