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
    args=p.parse_args();run=start(args.output,'T10_portable_inputs')
    try:
        verify_packet(args.packet)
        for name in INPUT_FILES:shutil.copy2(args.packet/name,args.output/name)
        for name in ('normalized_T10','video_T10'):shutil.copytree(args.packet/name,args.output/name)
        shutil.copy2(args.packet/'run.json',args.output/'parent_intake_run.json')
        parent=json.loads((args.packet/'packet.json').read_text())
        write(args.output/'packet.json',{'schema_version':1,'experiment_id':'T10','bag_sha256':BAG_SHA,'mov_sha256':MOV_SHA,
            'table_rows':parent['table_rows'],'normalization_rebuilt':False,'new_estimator_runs':0,
            'table_lineage':parent['table_lineage'],'parent_intake_run_sha256':sha(args.packet/'run.json'),
            'full_historic_replay_included':False,'raw_bag_or_MOV_included':False,
            'reference_accepted':False,'purpose':'portable inputs for the unchanged PR46/48 reader; not a second estimator or public geometry update'})
        run['inputs']=[{'relative_path':'parent_intake/run.json','sha256':sha(args.packet/'run.json')}]
        finish(args.output,run,'DONE');return 0
    except Exception as error:
        write(args.output/'failure.json',{'error':str(error)});finish(args.output,run,'FAILED');raise


if __name__=='__main__':raise SystemExit(main())
