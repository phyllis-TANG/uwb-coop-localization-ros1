"""Compile strict T10 inputs; call unchanged PR46/48 functions only when ready.

The original normalized bytes are verified against their registered receipt and
the media-only manifest delta before the existing read_events/write_replay APIs.
No old run.json is edited, no estimator readiness or timing gate is relaxed.
"""
import argparse
import csv
import json
from pathlib import Path
import sys
import time

from common import BAG_SHA, ROOT, SESSION, finish, sha, start, verify_normalized, write
import interface
import model
import replay


def strict_inputs(template):
    if template.get('experiment_id')!='T10' or template.get('source_bag_sha256')!=BAG_SHA:
        raise ValueError('successful development T10 retry only')
    # Candidate lists remain as evidence; their assumptions are never consumed.
    for car in model.CARS:
        cc=template['vehicles'][car]
        for key in ('antenna_body_xy_m','initial_antenna_xy_room_m','initial_body_yaw_room_rad','antenna_height_m'):
            item=cc[key]
            if item.get('status')=='provided':
                kind=item.get('source_kind','').lower()
                if not kind or any(x in kind for x in ('synthetic','assumption','engineering','nominal','unknown')):
                    raise ValueError('strict physical input lacks source-supported provenance: '+car+':'+key)
                if key=='antenna_body_xy_m' and item.get('point_definition')!='physical_odometry_origin_to_antenna_body_axes':
                    raise ValueError('explicit physical base-to-antenna definition required; marker offset is not base')
        for topic,item in cc['sample_time_adjustments'].items():
            if item.get('status')=='provided' and (not item.get('semantics') or not isinstance(item.get('uncertainty_ns'),int)
                    or isinstance(item['uncertainty_ns'],bool) or item['uncertainty_ns']<=0):
                raise ValueError('sample-time semantics and declared bound required: '+car+':'+topic)
        used_groups=set(cc.get('clock_group_ids',{}).values())
        if cc.get('ros_clock_group_id'):used_groups.add(cc['ros_clock_group_id'])
        for g in used_groups:
            item=template['clock_groups'][g]
            if item.get('status')=='provided':
                if not isinstance(item.get('uncertainty_ns'),int) or isinstance(item['uncertainty_ns'],bool) or item['uncertainty_ns']<=0:
                    raise ValueError('positive, independently justified host clock bound required: '+g)
                kind=item.get('source_kind','').lower()
                if not kind or any(s in kind for s in ('synthetic','engineering','assumption','ntp_status','unknown')):
                    raise ValueError('strict host clock provenance missing: '+g)
        for topic,item in cc['sample_time_adjustments'].items():
            if item.get('status')=='provided':
                kind=item.get('source_kind','').lower()
                if not kind or any(s in kind for s in ('synthetic','engineering','assumption','unknown')):
                    raise ValueError('strict sample-time provenance missing: '+car+':'+topic)


def verify_bindings(template, odom):
    for car in model.CARS:
        binding=template['vehicles'][car]['initial_record_binding']
        if binding['status']!='provided':continue
        matches=[r for r in odom if r['vehicle_id']==car and r['source_file_sha256']==BAG_SHA
            and all(int(r[k])==binding[k] for k in ('record_index','header_epoch_ns','receive_epoch_ns'))]
        if len(matches)!=1:raise ValueError('initial record missing, ambiguous or wrong vehicle: '+car)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template',type=Path,required=True);p.add_argument('--normalized',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--max-seconds',type=float,default=600)
    args=p.parse_args();started=time.monotonic();run=start(args.output,'T10_strict_compile_and_conditional_replay')
    try:
        if not 0<args.max_seconds<=21600:raise ValueError('invalid runtime budget')
        template=json.loads(args.template.read_text());strict_inputs(template)
        config,ready=interface.compile_template(template)
        # Room Odom-only must share actual initial/time conditions with fusion.
        # Source-frame Odom-only is already preserved in the reused PR46 run.
        config['odom_only_frame']='room'
        ready['methods']=model.readiness(config)
        reuse=verify_normalized(args.normalized);write(args.output/'normalized_reuse.json',reuse)
        with (args.normalized/'odom.csv').open() as f:odom=[r for r in csv.DictReader(f) if r['experiment_id']=='T10']
        verify_bindings(template,odom)
        write(args.output/'baseline_config.json',config);write(args.output/'readiness.json',ready)
        blocked=sorted({r for m in ready['methods'].values() for c in m.values() for r in c})
        run['inputs']=[{'relative_path':args.template.name,'sha256':sha(args.template)},
            {'relative_path':'normalized/run.json','sha256':reuse['parent_run_sha256']}]
        run['blocked_fields']=blocked;run['new_estimator_runs']=0
        if blocked:
            write(args.output/'execution.json',{'status':'BLOCKED','new_estimator_runs':0,
                'reason':'strict room prerequisites incomplete; no repeated source odometry replay',
                'blocked_fields':blocked,'exploration_config':None,
                'exploration_reason':'no defensible physical base-origin/actual-init/measurement-clock convention to instantiate unknown values'})
            finish(args.output,run,'BLOCKED');return 2
        # Existing mathematical/state/timing/correlation policies are untouched.
        directory=args.output/'room_baselines'
        baseline_run=replay.create_run(directory,args.output/'baseline_config.json',[sys.executable]+sys.argv)
        manifest=json.loads((SESSION/'manifest.json').read_text())
        item=next(r for r in manifest['formal_bags'] if r['id']=='T10')
        events,counts,ingestion=replay.read_events(args.normalized,'T10',config,manifest)
        baseline_run['ingestion']=dict(ingestion,selected_event_counts=counts)
        baseline_run['inputs']=run['inputs']
        baseline_run['normalization_compatibility_receipt_sha256']=sha(args.output/'normalized_reuse.json')
        replay.write_replay(directory,events,config,'T10',item['first_bag_receive_epoch_ns'],item['last_bag_receive_epoch_ns'],baseline_run,started+args.max_seconds)
        replay.finish(directory,baseline_run,'DONE',started)
        run['new_estimator_runs']=1
        write(args.output/'execution.json',{'status':'DONE','new_estimator_runs':1,
            'reference_accepted':False,'accuracy_metrics':None,'independent_room_readback_required':True})
        finish(args.output,run,'DONE');return 0
    except Exception as error:
        write(args.output/'failure.json',{'error':str(error)});finish(args.output,run,'FAILED');raise


if __name__=='__main__':raise SystemExit(main())
