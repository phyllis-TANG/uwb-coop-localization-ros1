"""Bind verified rich packets to A's exact v1 interface, without graph imports."""
import argparse
import copy
import gzip
import json
from pathlib import Path
import subprocess
from meta import HERE,LEGACY,ROOT,finish,save,sha,start
from prepare import legacy_view


def adapt(row):
    for key in ('record_index','receive_epoch_ns'):
        if type(row[key]) is not int:raise ValueError('integer raw identity required')
    out={k:row[k] for k in ('kind','case_id','record_index','source_file_sha256','topic','header_epoch_ns','receive_epoch_ns')}
    out['raw_message_sha256']=row['raw_message_sha256']
    kind=row['kind'];message=row['message']
    if kind in ('odom','uwb','imu') and type(row['header_epoch_ns']) is not int:raise ValueError('integer source time required')
    if kind=='odom':out['value']={'pose':legacy_view(row)['value'],'angular_z_rad_s':message['twist']['twist']['angular']['z']}
    elif kind=='uwb':out['value']=legacy_view(row)['value']
    elif kind=='imu':
        out['value']={'angular_velocity_rad_s':[message['angular_velocity'][k] for k in 'xyz'],'frame_id':message['header']['frame_id'],'units':'rad/s'}
    else:out['value']=None
    return out


def config_for(template,legacy,arm,frame,protocol):
    config=copy.deepcopy(template)
    for key in ('model','replay','optimizer','frontend'):config[key]=copy.deepcopy(legacy[key])
    config.update(scope='field',arm=arm,fixed_lag_s=20.)
    config['optimizer']['initialization']='F0 legacy Odom; F1-F3 selected angular prediction; actual source logged per update'
    for key,item in config['angular'].items():
        item.update(source_kind='engineering_assumption',source='A '+protocol['A_commit']+' frozen v1; uncalibrated engineering design, not inferred from these bags')
    config['angular']['body_z_in_imu_frame'].update(value=protocol['axis_hypothesis'],source='Conditional published gyro +Z = planar body +Z hypothesis; physical installation/sign not verified')
    config['angular']['imu_frame_id'].update(value=frame,source_kind='measured',source='Exact observed ROS frame label from verified historical bag; label is not a physical extrinsic calibration')
    for kind in ('odom','imu','uwb'):
        config['clock_maps'][kind]={'value':{'source_origin_ns':0,'destination_origin_ns':0,'rate_numerator':1,'rate_denominator':1,'uncertainty_ns':protocol['clock_API_disclosure_scale_ns']},
            'units':'ns','source_kind':'engineering_assumption','source':'Inherited uncorrected recorded epoch hypothesis. uncertainty_ns is an unverified API disclosure scale, NOT a physical error bound, not used to map or weight data; physical bound remains null.','frozen_before_field_run':True}
    config['assumptions'] += ['CONDITIONAL exploration only; strict physical branch remains BLOCKED',
        'Historical [.12,-.08]m lever is inherited near geometric center, odom physical correspondence unverified; no later session correction transferred',
        'Same uncorrected recorded header epochs as legacy, no receive-header median delay correction; true sampling time and uncertainty pending',
        'Published gyro units rad/s; board compensation and historical deployed source binding unverified',
        'All four arms use identical Odom pose-derived translation and UWB; upstream Odom yaw remains in translation expression',
        'No endpoint, video or IMU quaternion used for initialization, factors or tuning; no field accuracy claims']
    return config


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--A-checkout',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run=start(a.output,'frozen_A_field_adapter');protocol=json.loads((HERE/'field_protocol.json').read_text())
    try:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.A_checkout,text=True).strip()
        if commit!=protocol['A_commit']:raise ValueError('use exact frozen A checkout (no combined HEAD here)')
        # git-show binds the template even if another window has uncommitted work.
        raw=subprocess.check_output(['git','show',commit+':tools/single_car_imu_fgo/config.template.json'],cwd=a.A_checkout)
        template=json.loads(raw);legacy=json.loads(LEGACY.read_text());index=[]
        save(a.output/'field_protocol.json',protocol)
        for case in protocol['cases']:
            src=a.packets/case;manifest=json.loads((src/'input_manifest.json').read_text())
            for item in manifest['files']:
                if sha(src/item['relative_path'])!=item['sha256']:raise ValueError('packet SHA mismatch')
            rows=[json.loads(s) for s in gzip.open(src/'events.jsonl.gz','rt')]
            if any(r['case_id']!=case for r in rows):raise ValueError('case isolation')
            frames={r['message']['header']['frame_id'] for r in rows if r['kind']=='imu'}
            if len(frames)!=1:raise ValueError('unknown/changing IMU frame')
            dst=a.output/case;dst.mkdir();target=dst/'events.jsonl.gz'
            with target.open('xb') as f,gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as stream:
                for row in rows:stream.write((json.dumps(adapt(row),sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())
            configs={}
            for arm in protocol['arms']:
                path=dst/(arm+'.json');save(path,config_for(template,legacy,arm,next(iter(frames)),protocol));configs[arm]=sha(path)
            index.append({'case_id':case,'source_bag_sha256':manifest['source_bag_sha256'],'rich_packet_sha256':sha(src/'events.jsonl.gz'),'A_events_sha256':sha(target),'config_sha256':configs,'records':len(rows)})
        save(a.output/'index.json',dict(A_commit=commit,config_template_sha256=__import__('hashlib').sha256(raw).hexdigest(),cases=index,strict_physical_branch='BLOCKED',physical_clock_error_bound_ns=None))
        run['inputs']=[{'path':str(a.packets/c/'events.jsonl.gz'),'sha256':sha(a.packets/c/'events.jsonl.gz')} for c in protocol['cases']]
        finish(a.output,run,'DONE');return 0
    except Exception as e:finish(a.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
