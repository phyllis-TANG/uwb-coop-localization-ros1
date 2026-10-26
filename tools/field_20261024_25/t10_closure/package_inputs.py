"""Make a small transferable T10 input packet; exclude full old replay outputs."""
import argparse
import json
from pathlib import Path
import shutil

from common import BAG_SHA, MOV_SHA, finish, sha, start, verify_packet, write


INPUT_FILES = ('PR45_reuse.json','PR49_reuse.json','source_evidence.json',
               'initialization_records.json','T10_strict_input_template.json','existing_T10_readback.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packet',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--operator-evidence',type=Path)
    p.add_argument('--strict-template',type=Path)
    args=p.parse_args();run=start(args.output,'T10_portable_inputs')
    try:
        verify_packet(args.packet)
        for name in INPUT_FILES:
            if name=='T10_strict_input_template.json' and args.strict_template:continue
            shutil.copy2(args.packet/name,args.output/name)
        if bool(args.operator_evidence)!=bool(args.strict_template):raise ValueError('supplement and strict template must be supplied together')
        if args.operator_evidence:
            from run_ready import strict_inputs
            updated=json.loads(args.strict_template.read_text());strict_inputs(updated)
            original=json.loads((args.packet/'T10_strict_input_template.json').read_text())
            for car in ('car1','car2'):
                for field in ('antenna_body_xy_m','initial_antenna_xy_room_m','initial_body_yaw_room_rad','antenna_height_m'):
                    # This supplement is evidence clarification, not calibration.
                    if any(updated['vehicles'][car][field].get(k)!=original['vehicles'][car][field].get(k) for k in ('status','value')):
                        raise ValueError('evidence supplement must not silently change consumed geometry')
                for field in ('sample_time_adjustments','ros_clock_group_id'):
                    if updated['vehicles'][car][field]!=original['vehicles'][car][field]:raise ValueError('time assumption changed')
            if updated['clock_groups']!=original['clock_groups']:raise ValueError('host clock assumption changed')
            shutil.copy2(args.strict_template,args.output/'T10_strict_input_template.json')
            shutil.copy2(args.operator_evidence,args.output/'operator_evidence.json')
        for name in ('normalized_T10','video_T10'):shutil.copytree(args.packet/name,args.output/name)
        shutil.copy2(args.packet/'run.json',args.output/'parent_intake_run.json')
        parent=json.loads((args.packet/'packet.json').read_text())
        write(args.output/'packet.json',{'schema_version':1,'experiment_id':'T10','bag_sha256':BAG_SHA,'mov_sha256':MOV_SHA,
            'table_rows':parent['table_rows'],'normalization_rebuilt':False,'new_estimator_runs':0,
            'table_lineage':parent['table_lineage'],'parent_intake_run_sha256':sha(args.packet/'run.json'),
            'full_historic_replay_included':False,'raw_bag_or_MOV_included':False,
            'reference_accepted':False,'purpose':'portable inputs for the unchanged PR46/48 reader; not a second estimator or public geometry update'})
        run['inputs']=[{'relative_path':'parent_intake/run.json','sha256':sha(args.packet/'run.json')}]
        if args.operator_evidence:
            run['inputs'] += [{'relative_path':p.name,'sha256':sha(p)} for p in (args.operator_evidence,args.strict_template)]
        finish(args.output,run,'DONE');return 0
    except Exception as error:
        write(args.output/'failure.json',{'error':str(error)});finish(args.output,run,'FAILED');raise


if __name__=='__main__':raise SystemExit(main())
