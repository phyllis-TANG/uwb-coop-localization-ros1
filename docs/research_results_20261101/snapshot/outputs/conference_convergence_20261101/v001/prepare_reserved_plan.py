from pathlib import Path
from decimal import Decimal
import hashlib,json
ROOT=Path('I:/UWB/project');HERE=Path(__file__).resolve().parent
manifest=ROOT/'outputs/field_measurements_20261101/v001/FORMAL_CAPTURE_MANIFEST.json'
runs={r['id']:r for r in json.loads(manifest.read_text(encoding='utf-8-sig'))['runs']}
specs=[('A2','START',['START','B','C','RETURN']),('B2_PREFIX','START',['START']),('B2_CONTINUATION','B',['B','C','RETURN'])]
units=[]
for case,init,phases in specs:
    info=runs[case];events_path=Path(info['bag_path']+'.events.txt')
    events={label:int(Decimal(stamp)*10**9) for stamp,label in (line.split(' ',1) for line in events_path.read_text().splitlines())}
    prefix='A2' if case=='A2' else 'B2';start=events[f'{prefix}_{init}_STABLE_BEGIN'];first=((start+5*10**9+10**9-1)//10**9)*10**9
    windows=[]
    for phase in phases:
        lo=events[f'{prefix}_{phase}_STABLE_BEGIN'];ends=[v for k,v in events.items() if k.startswith(f'{prefix}_{phase}_STABLE_END')];assert len(ends)==1;hi=ends[0]
        assert hi>lo and hi>first
        windows.append({'phase':phase,'start_ns':lo,'end_ns':hi,'role':'initialization_stop' if phase==init else 'post_motion_stop'})
    units.append({'unit':case,'bag_path':info['bag_path'],'bag_sha256_from_capture_manifest':info['sha256'],'events_path':str(events_path),'events_sha256':hashlib.sha256(events_path.read_bytes()).hexdigest(),
        'initialization_interval_ns':[start,start+5*10**9],'first_state_ns':first,'evaluation_windows':windows,'carry_prior_from_other_unit':False,'carry_gyro_from_other_unit':False})
assert len(units)==3 and sum(len(x['evaluation_windows']) for x in units)==8
protocol=HERE/'保留验证规则草案.txt'
result={'status':'prepared_not_executed_not_final_frozen','source_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256(protocol.read_bytes()).hexdigest(),
    'checked':'event identities, exact integer ns, init before window end, three independent units and eight reference windows; no raw bag decode or coordinates/results read',
    'units':units,'remaining':'development-only reset interface check, final code/config lock, then reserved execution after cloud handoff review'}
(HERE/'RESERVED_PLAN_DRAFT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':result['status'],'units':len(units),'windows':8,'raw_bags_decoded':0,'heldout_estimator_runs':0,'checks':'passed'}))
