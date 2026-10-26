"""Build a portable, identity-bound T10 input packet from verified PR45/49 outputs."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil
import tarfile
import xml.etree.ElementTree as ET

from common import (BAG_SHA, MOV_SHA, ROOT, SESSION, VIDEO, finish, sha, start,
                    verify_normalized, verify_video_artifacts, write)
import verify_outputs


def select_csv(source, destination, field, expected):
    with Path(source).open(newline='') as inp, Path(destination).open('x',newline='') as out:
        reader=csv.DictReader(inp);writer=csv.DictWriter(out,fieldnames=reader.fieldnames,lineterminator='\n')
        writer.writeheader();count=0
        for row in reader:
            if row[field]!=expected:continue
            if 'source_file_sha256' in row and row['source_file_sha256']!=BAG_SHA:
                raise ValueError('wrong T10 attempt in normalized table')
            writer.writerow(row);count+=1
    return count


def exact_record(row):
    if row['experiment_id']!='T10' or row['source_file_sha256']!=BAG_SHA:raise ValueError('wrong initialization source')
    return {k:(int(row[k]) if k in ('record_index','header_epoch_ns','receive_epoch_ns') else row[k])
            for k in ('vehicle_id','source_file_sha256','topic','record_index','header_epoch_ns','receive_epoch_ns','frame_id','child_frame_id')}


def initialization_candidates(rows, mapping):
    from fractions import Fraction
    result={}
    for car in ('car1','car2'):
        candidates=sorted([r for r in rows if r['vehicle_id']==car],key=lambda r:(int(r['receive_epoch_ns']),int(r['record_index'])))
        first=candidates[0]
        # This only locates a frame under the already unaccepted event mapping.
        # It neither adopts the affine clock nor binds a measured physical pose.
        t=Fraction(int(first['receive_epoch_ns'])-int(mapping['destination_origin_epoch_ns']),10**9)
        model=mapping['candidate_model']
        v=(float(t)-model['b_relative_s'])/model['a']
        pts=list(csv.DictReader((VIDEO/'frame_pts/f7ec52ce2393.csv').open()))
        nearest=min(pts,key=lambda r:abs(float(r['video_time_s'])-v))
        result[car]={'selected_source_record':exact_record(first),
            'record_selection':'first arrived own-car odometry in successful retry; identity selected, actual room pose unestablished',
            'adopted_as_actual_room_initialization':False,
            'actual_initial_antenna_xy_room_m':None,'actual_initial_body_yaw_room_rad':None,
            'reason':'no independent actual pose at this record; nominal start and endpoint cannot establish it',
            'source_pose_raw':{k:first[k] for k in first if k.startswith(('position_','orientation_','linear_','angular_'))},
            'conditional_video_candidate':{'video_sha256':MOV_SHA,'mapping_id':mapping['mapping_id'],
                'mapping_status':mapping['status'],'frame_index':int(nearest['frame_index']),
                'pts_ticks':int(nearest['pts_ticks']),'time_base_num':int(nearest['time_base_num']),
                'time_base_den':int(nearest['time_base_den']),'status':'not_adopted_for_pose_binding',
                'time_uncertainty_ns':None,'reason':'nearest PTS under event candidate only; not independent synchronization'}}
    return result


def source_audit(data_root, bag_item):
    extract=data_root/'extracted/bags'
    archive=data_root/'downloads/UWB_field_20261024_25_20261025_071212.tar.gz'
    if sha(archive)!='b7cec6f75584e583e66946fd669dc7495d10e3bcbebc0b67fa480b65b53fd1bf':raise ValueError('source archive changed')
    if sha(extract/bag_item['relative_path'])!=BAG_SHA:raise ValueError('successful T10 bag changed')
    saved=json.loads((ROOT/'tools/field_20261024_25/parameter_clock_prep/results/source_evidence.json').read_text())
    files=[]
    for entry in saved['files']:
        rel=entry['relative_path']
        if '!' in rel:
            archive_rel,member=rel.split('!',1)
            with tarfile.open(extract/archive_rel) as t: content=t.extractfile(member).read()
        else:
            p=(ROOT/rel) if rel.startswith('ros_ws/') else (extract/rel)
            content=p.read_bytes()
        actual=hashlib.sha256(content).hexdigest()
        if actual!=entry['sha256']:raise ValueError('source evidence hash changed: '+rel)
        files.append({'relative_path':rel,'sha256':actual,'bytes':len(content)})
    setup=extract/'uwb_field_20261024/setup_evidence_20261024_030824'
    urdf=ET.fromstring((setup/'V550_mec_robot.urdf').read_text())
    links=[e.attrib['name'] for e in urdf.findall('link')]
    mechanical={'urdf_link_names':links,'urdf_uwb_or_antenna_links':[n for n in links if any(s in n.lower() for s in ('uwb','antenna','tag'))],
        'base_origin_to_physical_antenna_xy_m':{'car1':None,'car2':None},
        'conclusion':'CAD link origins/inertial centers and launch zero transforms do not identify the physical odometry integration point relative to the installed antenna; no antenna link in this URDF'}
    logs=[]
    for rel in ['uwb_field_20261025/car_logs/car1/T10_motion_retry_20261025_184808.log',bag_item['relative_path']+'.notes.txt']:
        p=extract/rel
        if p.exists():logs.append({'relative_path':rel,'sha256':sha(p),'text':p.read_text(),
            'limitation':'control completion/operator notes, not independent initialization or time calibration'})
    return {'schema_version':1,'archive_sha256':sha(archive),'successful_bag_sha256':BAG_SHA,
        'verified_source_files':files,'mechanical':mechanical,'timestamp_excerpts':saved['excerpts'],
        'source_deployment_limits':saved['limits'],'T10_logs':logs,
        'new_ros_or_archive_code_executed':False}


def verify_old_replay(directory, odom, origin):
    state=json.loads((directory/'run.json').read_text())
    registered=json.loads((ROOT/'tools/field_20261024_25/causal_baselines/results_summary/field_verification.json').read_text())
    entry=next(r for r in registered['checks'] if r['experiment_id']=='T10')
    if sha(directory/'run.json')!=entry['run_sha256']:raise ValueError('unregistered previous T10 result')
    if state['status']!='BLOCKED':raise ValueError('unexpected previous run status')
    for item in state['outputs']:
        rel=Path(item['relative_path'])
        if rel.is_absolute() or '..' in rel.parts or sha(directory/rel)!=item['sha256']:
            raise ValueError('previous T10 output hash mismatch')
    with (directory/'estimate.csv').open() as f: counts=verify_outputs.verify_rows(csv.DictReader(f),odom,origin)
    return {'status':'DONE','new_estimator_runs':0,'reused_run_status':state['status'],
        'run_sha256':sha(directory/'run.json'),'counts':counts,
        'scope':'independent readback of existing source odometry and blocked fusion; not a new room replay or accuracy evaluation'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--normalized',type=Path,required=True);p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--baseline-run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'T10_input_closure')
    try:
        write(args.output/'PR45_reuse.json',verify_normalized(args.normalized))
        write(args.output/'PR49_reuse.json',verify_video_artifacts())
        manifest=json.loads((SESSION/'manifest.json').read_text());bag=next(r for r in manifest['formal_bags'] if r['id']=='T10')
        if bag['sha256']!=BAG_SHA:raise ValueError('wrong formal attempt')
        write(args.output/'source_evidence.json',source_audit(args.data_root,bag))
        normalized=args.output/'normalized_T10';normalized.mkdir()
        counts={}
        for name in ('odom.csv','ranges.csv','frames.csv','imu.csv','commands.csv'):
            counts[name]=select_csv(args.normalized/name,normalized/name,'experiment_id','T10')
        observations=args.output/'video_T10';observations.mkdir()
        counts['marker_observations.csv']=select_csv(VIDEO/'marker_observations.csv',observations/'marker_observations.csv','experiment_id','T10')
        shutil.copy2(VIDEO/'frame_pts/f7ec52ce2393.csv',observations/'frame_pts.csv')
        mapping=next(r for r in json.loads((VIDEO/'time_mapping.json').read_text())['mappings'] if r['experiment_id']=='T10')
        transform=next(r for r in json.loads((VIDEO/'frame_transforms.json').read_text())['records'] if r['video_sha256']==MOV_SHA)
        write(observations/'time_candidate.json',mapping);write(observations/'spatial_candidates.json',transform)
        with (normalized/'odom.csv').open() as f:odom=list(csv.DictReader(f))
        bindings=initialization_candidates(odom,mapping)
        write(args.output/'initialization_records.json',bindings)
        template=json.loads((ROOT/'tools/field_20261024_25/parameter_clock_prep/results/T10_input_template.json').read_text())
        for car,record in bindings.items():
            template['vehicles'][car]['initial_record_binding']['first_arrived_candidate']=record['selected_source_record']
            template['vehicles'][car]['initial_record_binding']['conditional_video_candidate']=record['conditional_video_candidate']
        template['closure_scope']='strict_source_supported_inputs_only; record identity is not physical pose confirmation'
        write(args.output/'T10_strict_input_template.json',template)
        report=verify_old_replay(args.baseline_run,odom,bag['first_bag_receive_epoch_ns'])
        write(args.output/'existing_T10_readback.json',report)
        # Transfer exact old run bytes, clearly separated from newly generated results.
        prior=args.output/'reused_PR46_T10';prior.mkdir()
        shutil.copy2(args.baseline_run/'run.json',prior/'run.json')
        for item in json.loads((args.baseline_run/'run.json').read_text())['outputs']:
            rel=Path(item['relative_path']);(prior/rel).parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(args.baseline_run/rel,prior/rel)
        write(args.output/'packet.json',{'schema_version':1,'experiment_id':'T10','bag_sha256':BAG_SHA,'mov_sha256':MOV_SHA,
            'table_rows':counts,'normalization_rebuilt':False,'new_estimator_runs':0,
            'table_lineage':'exact T10 rows selected from verified PR45 tables; packet is NOT a new normalization root',
            'old_run_lineage':'reused_PR46_T10 contains exact historic bytes; see existing_T10_readback.json',
            'reference_accepted':False,'raw_bag_or_MOV_included':False})
        run['inputs']=[{'relative_path':'normalized/run.json','sha256':sha(args.normalized/'run.json')},
            {'relative_path':'PR46_T10/run.json','sha256':sha(args.baseline_run/'run.json')},
            {'relative_path':bag['relative_path'],'sha256':BAG_SHA}]
        finish(args.output,run,'DONE');return 0
    except Exception as error:
        write(args.output/'failure.json',{'error':str(error)});finish(args.output,run,'FAILED');raise


if __name__=='__main__':raise SystemExit(main())
