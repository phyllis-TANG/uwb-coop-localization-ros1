"""Describe selected source timing/coverage/signals; never calibrate or localize."""
import argparse
import bisect
from collections import Counter
import csv
import gzip
import json
import math
from pathlib import Path

import numpy as np
from provenance import ROOT,SESSION,finish,save,sha,start


def stats(values):
    values=[float(x) for x in values if x is not None and math.isfinite(float(x))]
    if not values:return {'n':0,'mean':None,'median':None,'p95':None,'minimum':None,'maximum':None}
    a=np.asarray(values)
    return {'n':len(values),'mean':float(a.mean()),'std':float(a.std()),'median':float(np.median(a)),
            'p95':float(np.percentile(a,95)),'minimum':float(a.min()),'maximum':float(a.max())}


def temporal(rows,protocol):
    rows=sorted(rows,key=lambda r:int(r['record_index']))
    header=[int(r['header_epoch_ns']) for r in rows];receive=[int(r['receive_epoch_ns']) for r in rows]
    dh=[b-a for a,b in zip(header,header[1:])];dr=[b-a for a,b in zip(receive,receive[1:])]
    gaps=[{'before_record_index':int(rows[i]['record_index']),'after_record_index':int(rows[i+1]['record_index']),
           'before_header_ns':header[i],'after_header_ns':header[i+1],'header_gap_ns':delta,
           'before_receive_ns':receive[i],'after_receive_ns':receive[i+1]} for i,delta in enumerate(dh) if delta>protocol['diagnostic_gap_ns']]
    return {'messages':len(rows),'header_interval_ns':[min(header),max(header)],'receive_interval_ns':[min(receive),max(receive)],
        'header_rate_hz':(len(rows)-1)*1e9/(max(header)-min(header)) if len(rows)>1 and max(header)>min(header) else None,
        'header_delta_ns':stats(dh),'receive_delta_ns':stats(dr),'header_duplicates':sum(d==0 for d in dh),
        'header_backwards':sum(d<0 for d in dh),'receive_backwards_in_original_record_order':sum(d<0 for d in dr),
        'receive_minus_header_ns':stats([r-h for r,h in zip(receive,header)]),
        'receipt_header_difference_is_delay_or_clock_calibration':False,
        'arrival_batch_candidates':sum(0<=r<=protocol['diagnostic_batch_receive_ns'] and h>=protocol['diagnostic_header_progress_ns'] for r,h in zip(dr,dh)),
        'gap_threshold_ns_diagnostic_only':protocol['diagnostic_gap_ns'],'header_gaps':gaps,
        'original_nonfinite_field_rows':sum(r.get('nonfinite_fields') not in (None,'','[]') for r in rows)}


def offline_pairs(odom,imu,tolerance):
    # Generate all nearby candidates, then consume each original message once.
    right=sorted(imu,key=lambda r:(int(r['header_epoch_ns']),int(r['record_index'])))
    times=[int(r['header_epoch_ns']) for r in right];candidates=[]
    for o in odom:
        h=int(o['header_epoch_ns']);lo=bisect.bisect_left(times,h-tolerance);hi=bisect.bisect_right(times,h+tolerance)
        for i in range(lo,hi):candidates.append((abs(times[i]-h),int(o['record_index']),int(right[i]['record_index']),o,right[i]))
    used_o=set();used_i=set();result=[]
    for _,oi,ii,o,i in sorted(candidates,key=lambda t:t[:3]):
        if oi in used_o or ii in used_i:continue
        used_o.add(oi);used_i.add(ii);result.append((o,i))
    return sorted(result,key=lambda p:int(p[0]['record_index']))


def relationship(pairs):
    x=np.array([float(o['angular_z']) for o,i in pairs]);y=np.array([float(i['angular_velocity_z']) for o,i in pairs])
    good=np.isfinite(x)&np.isfinite(y);x,y=x[good],y[good]
    fit={'identifiable':False,'correlation':None,'slope':None,'intercept_rad_s':None}
    if len(x)>=3 and np.std(x)>1e-12 and np.std(y)>1e-12:
        slope=float(np.dot(x-x.mean(),y-y.mean())/np.dot(x-x.mean(),x-x.mean()))
        fit={'identifiable':True,'correlation':float(np.corrcoef(x,y)[0,1]),'slope':slope,'intercept_rad_s':float(y.mean()-slope*x.mean())}
    return {'paired_rows':len(pairs),'diagnostic_only_not_online_admission':True,
        'IMU_arrived_after_paired_odom':sum(int(i['receive_epoch_ns'])>int(o['receive_epoch_ns']) for o,i in pairs),
        'IMU_minus_odom_header_ns':stats([int(i['header_epoch_ns'])-int(o['header_epoch_ns']) for o,i in pairs]),
        'gyro_z_minus_odom_rate_rad_s':stats((y-x).tolist()),'gyro_on_odom_regression':fit,
        'regression_used_as_calibration':False,'statistical_independence_established':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'imu_field_coverage_and_clock_diagnostics')
    try:
        protocol=json.loads(Path(__file__).with_name('protocol.json').read_text());all_results=[];pair_signatures={};rows_out=[]
        for trial in ('T08','T10'):
            folder=args.packets/trial
            tables={}
            for name in ('odom','imu','ranges','frames'):
                with (folder/'normalized'/(name+'.csv')).open() as f:tables[name]=list(csv.DictReader(f))
            for car in ('car1','car2'):
                odom=[r for r in tables['odom'] if r['vehicle_id']==car];imu=[r for r in tables['imu'] if r['vehicle_id']==car]
                pairs=offline_pairs(odom,imu,protocol['offline_pair_tolerance_ns'])
                cov={name:dict(Counter(r[name] for r in imu)) for name in ('orientation_covariance','angular_velocity_covariance','linear_acceleration_covariance')}
                result={'experiment_id':trial,'vehicle_id':car,'odom':temporal(odom,protocol),'imu':temporal(imu,protocol),
                    'IMU_frame_ids':sorted({r['frame_id'] for r in imu}),'base_frame_ids':sorted({r['child_frame_id'] for r in odom}),
                    'gyro_published_rad_s':{axis:stats([r['angular_velocity_'+axis] for r in imu if r['angular_velocity_'+axis]!='']) for axis in 'xyz'},
                    'recorded_covariance_values':cov,'covariance_is_calibrated':False,
                    'relation':relationship(pairs),'hardware_axis_or_sampling_time_accepted':False,'applied_bias_estimate':None}
                ranges=[r for r in tables['ranges'] if r['vehicle_id']==car]
                result['range_input_audit']={'rows':len(ranges),'primary_observation_rows':sum(r['primary_observation']=='1' for r in ranges),
                    'sources':dict(Counter(r['source'] for r in ranges)),'pairing_status':dict(Counter(r['pairing_status'] for r in ranges)),
                    'directed_peer_rows_retained':sum(r['link_kind']=='peer' for r in ranges),'raw_bridge_averaged_or_deduplicated_in_packet':False}
                all_results.append(result)
                for o,i in pairs:
                    row=[trial,car,int(o['record_index']),int(i['record_index']),int(o['header_epoch_ns']),int(i['header_epoch_ns']),float(o['angular_z']),float(i['angular_velocity_z'])]
                    rows_out.append(row);pair_signatures[tuple(row[:4])]=tuple(row[4:])
        previous=SESSION/'imu_odom_audit_20261027/pair_observations.csv.gz';old={}
        with gzip.open(previous,'rt') as f:
            for r in csv.DictReader(f):
                if r['experiment'] not in ('T08','T10'):continue
                key=(r['experiment'],r['vehicle'],int(r['odom_record']),int(r['imu_record']))
                old[key]=(int(r['odom_header_ns']),int(r['imu_header_ns']),float(r['odom_rate_z']),float(r['gyro_z']))
        if pair_signatures!=old:raise ValueError('offline relation differs from registered PR55 pair table; review before claiming reproduction')
        with gzip.open(args.output/'offline_pair_diagnostics.csv.gz','wt',newline='') as f:
            writer=csv.writer(f);writer.writerow(['experiment_id','vehicle_id','odom_record_index','imu_record_index','odom_header_ns','imu_header_ns','odom_angular_z','IMU_angular_velocity_z']);writer.writerows(rows_out)
        save(args.output/'diagnostics.json',{'schema_version':1,'status':'DONE','streams':all_results,
            'previous_pair_file_sha256':sha(previous),'PR55_selected_pair_rows_reproduced':len(old),
            'pairing_not_used_for_online_controls':True,'no_mean_delay_correction':True,
            'bias_trajectory':None,'bias_reason':'A frozen estimator has not been received or run',
            'field_accuracy_evaluated':False,'statistical_calibration_performed':False})
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
