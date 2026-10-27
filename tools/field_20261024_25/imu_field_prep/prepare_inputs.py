"""Reuse PR45 rows as T08/T10 immutable IMU/odom/range events; no estimator."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import time

from provenance import CONTRACT,ROOT,SESSION,finish,save,sha,start

PROTOCOL=Path(__file__).with_name('protocol.json')
INTEGER=re.compile(r'^[0-9]+$')


def integer(value):
    if isinstance(value,bool) or not isinstance(value,(str,int)) or not INTEGER.fullmatch(str(value)):
        raise ValueError('exact unsigned decimal integer required: '+repr(value))
    return int(value)


def numeric_errors(kind,row):
    fields={'odom':['position_'+a for a in 'xyz']+['orientation_'+a for a in 'xyzw']
                  +[k+'_'+a for k in ('linear','angular') for a in 'xyz'],
            'imu':['orientation_'+a for a in 'xyzw']+[k+'_'+a for k in ('angular_velocity','linear_acceleration') for a in 'xyz'],
            'range':['range_m']}[kind]
    errors=[]
    for name in fields:
        try:
            if not row.get(name) or not math.isfinite(float(row[name])):raise ValueError()
        except (ValueError,TypeError):errors.append(name+':missing_or_nonfinite_numeric')
    covariances={'odom':{'pose_covariance':36,'twist_covariance':36},
                 'imu':{k:9 for k in ('orientation_covariance','angular_velocity_covariance','linear_acceleration_covariance')},'range':{}}[kind]
    for name,length in covariances.items():
        try:
            values=json.loads(row[name])
            if not isinstance(values,list) or len(values)!=length or not all(v is not None and math.isfinite(float(v)) for v in values):raise ValueError()
        except (ValueError,KeyError,TypeError):errors.append(name+':invalid_or_nonfinite_covariance')
    if row.get('nonfinite_fields') not in (None,'','[]'):errors.append('normalized_nonfinite_fields:'+row['nonfinite_fields'])
    return errors


def event(kind,original,trial,expected_sha):
    if original['experiment_id']!=trial or trial not in ('T08','T10') or original['source_file_sha256']!=expected_sha:
        raise ValueError('trial/source identity mismatch or holdout')
    if original['vehicle_id'] not in ('car1','car2') or not original['topic'].startswith('/'+original['vehicle_id']+'/'):
        raise ValueError('cross-car identity mismatch')
    row=dict(original)
    for name in ('record_index','receive_epoch_ns','header_epoch_ns'):
        row[name]=integer(row[name])
    if kind=='range':row['link_index']=integer(row['link_index'])
    if 'input_numeric_status' in row or 'input_numeric_errors' in row:raise ValueError('reserved metadata collision')
    errors=numeric_errors(kind,row)
    row['input_numeric_status']='invalid_preserved' if errors else 'finite_parsed_for_audit'
    row['input_numeric_errors']=errors
    return {'kind':kind,'row':row}


def lineage(normalized,protocol):
    run=json.loads((normalized/'run.json').read_text())
    if sha(normalized/'run.json')!=protocol['normalized_registered_run_sha256'] or run['status']!='DONE':raise ValueError('unregistered PR45 normalization')
    checked=[]
    for item in run['outputs']:
        rel=Path(item['relative_path'])
        if rel.is_absolute() or '..' in rel.parts or sha(normalized/rel)!=item['sha256']:raise ValueError('original normalized hash changed')
        checked.append(item)
    old_manifest=subprocess.check_output(['git','show','4a379da:docs/field_tests/20261024_25/manifest.json'],cwd=ROOT)
    old_geometry=subprocess.check_output(['git','show','4a379da:docs/field_tests/20261024_25/geometry.json'],cwd=ROOT)
    if hashlib.sha256(old_manifest).hexdigest()!=run['config_sha256']['manifest.json'] or hashlib.sha256(old_geometry).hexdigest()!=run['config_sha256']['geometry.json']:
        raise ValueError('original configuration lineage mismatch')
    current=json.loads((SESSION/'manifest.json').read_text())
    if json.loads(old_manifest)['formal_bags']!=current['formal_bags'] or json.loads(old_geometry)!=json.loads((SESSION/'geometry.json').read_text()):
        raise ValueError('formal bag/geometry changed; manual reconciliation required')
    return {'status':'DONE','registered_run_sha256':sha(normalized/'run.json'),'original_outputs_verified':checked,
            'formal_bags_and_geometry_unchanged':True,'normalization_rebuilt':False,
            'other_trials_decoded':False,'manifest_media_updates_do_not_change_source_rows':True}


def prepare(normalized,data_root,output,protocol,deadline):
    receipt=lineage(normalized,protocol);save(output/'PR45_reuse.json',receipt)
    manifest=json.loads((SESSION/'manifest.json').read_text())
    archive=data_root/'downloads/UWB_field_20261024_25_20261025_071212.tar.gz'
    if sha(archive)!=protocol['archive_sha256']:raise ValueError('registered archive mismatch')
    selected={trial:next(r for r in manifest['formal_bags'] if r['id']==trial) for trial in protocol['experiments']}
    for trial,item in selected.items():
        if trial not in ('T08','T10') or item['split']!='development' or item['sha256']!=protocol['bag_sha256'][trial]:raise ValueError('whole-bag allowlist')
        bag=data_root/'extracted/bags'/item['relative_path']
        if sha(bag)!=item['sha256']:raise ValueError('selected bag hash mismatch')
    counts={t:{} for t in selected};errors={t:[] for t in selected};events={t:[] for t in selected}
    for trial in selected:(output/trial/'normalized').mkdir(parents=True)
    for name in protocol['tables']:
        with (normalized/(name+'.csv')).open(newline='') as f:
            reader=csv.DictReader(f);handles={t:(output/t/'normalized'/(name+'.csv')).open('x',newline='') for t in selected}
            try:
                writers={t:csv.DictWriter(h,fieldnames=reader.fieldnames,lineterminator='\n') for t,h in handles.items()}
                for t,w in writers.items():w.writeheader();counts[t][name]=0
                for original in reader:
                    trial=original['experiment_id']
                    if trial not in selected:continue
                    if original['source_file_sha256']!=selected[trial]['sha256']:raise ValueError('selected table source mismatch')
                    writers[trial].writerow(original);counts[trial][name]+=1
                    if name in ('odom','imu','ranges'):
                        e=event('range' if name=='ranges' else name,original,trial,selected[trial]['sha256']);row=e['row']
                        key=(row['receive_epoch_ns'],row['record_index'],row.get('link_index',0))
                        events[trial].append((key,json.dumps(e,ensure_ascii=False,allow_nan=False,separators=(',',':'))))
                        if row['input_numeric_errors']:errors[trial].append({'kind':e['kind'],'record_index':row['record_index'],'link_index':row.get('link_index'),'errors':row['input_numeric_errors']})
                        if len(events[trial])>protocol['maximum_events_per_trial']:raise ValueError('event budget exceeded')
                    if time.monotonic()>deadline:raise TimeoutError('input preparation stage budget')
            finally:
                for h in handles.values():h.close()
    summaries=[]
    for trial,item in selected.items():
        directory=output/trial;items=events.pop(trial);items.sort(key=lambda e:e[0])
        with (directory/'events.jsonl').open('x') as f:
            for _,line in items:f.write(line+'\n')
        save(directory/'numeric_status.json',{'event_count':len(items),'invalid_numeric_events_retained':len(errors[trial]),'errors':errors[trial],'no_bad_rows_dropped_or_zero_filled':True})
        input_manifest={'schema_version':1,'contract_id':protocol['contract_id'],'experiment_id':trial,'split':'development',
            'source_file_sha256':item['sha256'],'source_bag_relative_path':item['relative_path'],
            'first_bag_receive_epoch_ns':item['first_bag_receive_epoch_ns'],'last_bag_receive_epoch_ns':item['last_bag_receive_epoch_ns'],
            'source_normalization_run_sha256':receipt['registered_run_sha256'],'table_rows':counts[trial],
            'event_count':len(items),'event_order':protocol['ordering'],'numeric_policy':protocol['event_row_policy'],
            'units':{'linear_velocity':'m/s','angular_velocity':'rad/s','epoch_time':'integer ns'},
            'gyro_body_axis_and_hardware_sample_clock':'pending physical/deployment confirmation; original gyro_link axes retained',
            'approved_clock_models':None,'clock_reason':'source/header and recorder clocks uncalibrated; no receive-header median correction',
            'A_protocol_status':'not_yet_received','new_model_field_replays':0,'field_accuracy_evaluated':False,
            'files':[{'relative_path':str(p.relative_to(directory)),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(directory.rglob('*')) if p.is_file()]}
        save(directory/'input_manifest.json',input_manifest)
        summaries.append({'experiment_id':trial,'source_file_sha256':item['sha256'],'table_rows':counts[trial],'event_count':len(items),
            'input_manifest_sha256':sha(directory/'input_manifest.json'),'events_sha256':sha(directory/'events.jsonl'),'numeric_invalid_events':len(errors[trial])})
    # PR51 provides an additional T10 value-lineage checkpoint; no video data,
    # actual endpoint or camera-space candidate is read for this comparison.
    pr51=SESSION/'t10_closure_20261027/inputs/T10_portable_inputs_v2.tar.gz'
    metadata=json.loads(pr51.with_suffix('.gz.json').read_text())
    if sha(pr51)!=metadata['sha256']:raise ValueError('PR51 packet changed')
    cross=[]
    with tarfile.open(pr51,'r:gz') as t:
        for name in protocol['tables']:
            member='T10_inputs/normalized_T10/'+name+'.csv'
            digest=hashlib.sha256(t.extractfile(member).read()).hexdigest()
            if sha(output/'T10/normalized'/(name+'.csv'))!=digest:raise ValueError('PR51 T10 table mismatch')
            cross.append({'table':name,'sha256':digest})
    save(output/'PR51_crosscheck.json',{'status':'DONE','archive_sha256':metadata['sha256'],'normalized_tables_verified':cross,'video_or_endpoint_parameters_read':False})
    return summaries


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--normalized',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'imu_field_immutable_input_preparation')
    try:
        protocol=json.loads(PROTOCOL.read_text());save(args.output/'protocol.json',protocol);shutil.copy2(CONTRACT,args.output/'CONTRACT.json')
        summaries=prepare(args.normalized,args.data_root,args.output,protocol,time.monotonic()+protocol['maximum_stage_seconds'])
        shutil.copy2(SESSION/'t10_exploratory_20261027/nominal_config.json',args.output/'T10_PR53_nominal_config.json')
        save(args.output/'input_index.json',{'schema_version':1,'status':'DONE','experiments':summaries,
            'new_model_field_replays':0,'A_kernel_protocol':'pending exact frozen handoff; no replacement estimator written',
            'room_branches':{'T10':'PR53 engineering assumptions snapshot available, not calibration','T08':'room initialization/extrinsics pending; source-frame input work remains available'}})
        run['inputs']=[{'relative_path':'PR45/run.json','sha256':sha(args.normalized/'run.json')},
            {'relative_path':'registered_source_archive','sha256':protocol['archive_sha256']}]
        finish(args.output,run,'DONE');return 0
    except Exception as e:
        finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
