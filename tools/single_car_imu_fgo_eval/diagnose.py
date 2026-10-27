"""Historical signal/time coverage with original one-second release windows."""
import argparse
import bisect
import csv
import gzip
import json
from pathlib import Path

import numpy as np
from meta import HERE,LEGACY,ROOT,finish,save,sha,start


def distribution(values):
    values=np.asarray(values,float);values=values[np.isfinite(values)]
    if not len(values):return {'n':0,'median':None,'p95':None,'minimum':None,'maximum':None}
    return {'n':len(values),'median':float(np.median(values)),'p95':float(np.percentile(values,95)),
        'minimum':float(values.min()),'maximum':float(values.max())}


def stream(rows,gap):
    h=[r['header_epoch_ns'] for r in rows];rec=[r['receive_epoch_ns'] for r in rows]
    dh=[b-a for a,b in zip(h,h[1:])];dr=[b-a for a,b in zip(rec,rec[1:])]
    return {'count':len(rows),'header_coverage_ns':[min(h),max(h)],'receive_coverage_ns':[min(rec),max(rec)],
        'header_rate_hz':(len(h)-1)*1e9/(max(h)-min(h)) if len(h)>1 and max(h)>min(h) else None,
        'header_delta_ns':distribution(dh),'receive_delta_ns':distribution(dr),
        'header_duplicate_count':sum(x==0 for x in dh),'header_backwards_count':sum(x<0 for x in dh),
        'arrival_batch_candidates':sum(0<=r<=1000000 and h>=10000000 for r,h in zip(dr,dh)),
        'receive_minus_header_ns':distribution([r-h for r,h in zip(rec,h)]),'receipt_header_is_latency_bound':False,
        'header_gaps':[{'before_record_index':rows[i]['record_index'],'after_record_index':rows[i+1]['record_index'],'gap_ns':v} for i,v in enumerate(dh) if v>gap],
        'nonfinite_payload_rows':sum(bool(r['nonfinite_values']) for r in rows)}


def interval_coverage(imu,start_ns,end_ns,cutoff_ns,gap_ns):
    arrived=[r for r in imu if r['receive_epoch_ns']<=cutoff_ns]
    ordered=sorted(arrived,key=lambda r:(r['header_epoch_ns'],r['record_index']))
    stamps=[r['header_epoch_ns'] for r in ordered]
    left=bisect.bisect_right(stamps,start_ns)-1;right=bisect.bisect_left(stamps,end_ns)
    bracket=left>=0 and right<len(ordered)
    supporting=ordered[left:right+1] if bracket else [r for r in ordered if start_ns<=r['header_epoch_ns']<=end_ns]
    deltas=[b['header_epoch_ns']-a['header_epoch_ns'] for a,b in zip(supporting,supporting[1:])]
    return {'arrived_samples_in_interval':sum(start_ns<=r['header_epoch_ns']<=end_ns for r in arrived),
        'left_bracket_record_index':ordered[left]['record_index'] if left>=0 else None,
        'right_bracket_record_index':ordered[right]['record_index'] if right<len(ordered) else None,
        'both_arrived_boundary_brackets':bracket,'maximum_support_gap_ns':max(deltas) if deltas else None,
        'support_gap_over_diagnostic_threshold':any(x>gap_ns for x in deltas),
        'support_nonfinite_rows':sum(bool(r['nonfinite_values']) for r in supporting),
        'latest_dependency_receive_ns':max((r['receive_epoch_ns'] for r in supporting),default=None)}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'historical_IMU_FGO_time_and_signal_diagnostics')
    try:
        protocol=json.loads((HERE/'protocol.json').read_text());legacy=json.loads(LEGACY.read_text());reports=[];windows=[];signals=[]
        for case in legacy['cases']:
            directory=args.packets/case['id'];manifest=json.loads((directory/'input_manifest.json').read_text());origin=manifest['origin_bag_receive_epoch_ns']
            with gzip.open(directory/'events.jsonl.gz','rt') as f:events=[json.loads(line) for line in f]
            groups={k:[r for r in events if r['kind']==k] for k in ('odom','imu','uwb')};imu=groups['imu']
            result={'case_id':case['id'],'streams':{k:stream(v,protocol['gap_diagnostic_ns']) for k,v in groups.items()},
                'gyro_units':'published rad/s, not asserted to be unprocessed ADC','IMU_frame_ids':sorted({r['message']['header']['frame_id'] for r in imu}),
                'gyro_z_published_rad_s':distribution([r['message']['angular_velocity']['z'] for r in imu if r['message']['angular_velocity']['z'] is not None]),
                'observed_IMU_covariance_variants':sorted({json.dumps(r['message']['angular_velocity_covariance']) for r in imu}),
                'axis_mount_clock_noise_bias_calibration':False,'bias_trajectory':None,'bias_reason':'new A FGO estimator not yet frozen/executed'}
            with (ROOT/'docs/field_tests/single_car_fixed_lag_20261022/results'/case['id']/'analytic_warm_fixed_20s/published.csv').open() as f:grid=list(csv.DictReader(f))
            own=[]
            for publication in grid:
                end=float(publication['state_time_s']);cutoff=float(publication['availability_cutoff_s'])
                row={'case_id':case['id'],'state_time_s':end,'availability_cutoff_s':cutoff,
                    **interval_coverage(imu,origin+round((end-1)*1e9),origin+round(end*1e9),origin+round(cutoff*1e9),protocol['gap_diagnostic_ns'])}
                own.append(row);windows.append(row)
            result['publication_grid_IMU_coverage']={'scheduled_intervals':len(own),'with_both_arrived_brackets':sum(r['both_arrived_boundary_brackets'] for r in own),
                'diagnostic_gap_intervals':sum(r['support_gap_over_diagnostic_threshold'] for r in own),
                'note':'coverage only under inherited uncorrected source clock policy; not an A integration decision or approved physical synchronization'}
            for kind in ('imu','odom'):
                for r in groups[kind]:
                    rate=r['message']['angular_velocity']['z'] if kind=='imu' else r['message']['twist']['twist']['angular']['z']
                    signals.append({'case_id':case['id'],'kind':kind,'record_index':r['record_index'],'header_epoch_ns':r['header_epoch_ns'],
                        'receive_epoch_ns':r['receive_epoch_ns'],'header_relative_s':r['header_relative_s'],'angular_rate_z_rad_s':rate})
            reports.append(result)
        for name,rows in [('release_window_coverage.csv.gz',windows),('published_rate_signals.csv.gz',signals)]:
            with gzip.open(args.output/name,'wt',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        save(args.output/'diagnostics.json',{'status':'DONE','cases':reports,'IMU_integration_or_optimization_run':False,
            'one_second_wait_preserved':True,'no_window_removed_for_missing_IMU':True,'field_accuracy_evaluated':False,
            'clock_note':'integer source/receive epochs retained; no median delay correction or calibrated axis/noise claim'})
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(2,1,figsize=(10,6),sharex=False)
        for axis,case in zip(axes,('004023','005135')):
            for kind in ('imu','odom'):
                rows=[r for r in signals if r['case_id']==case and r['kind']==kind]
                axis.plot([r['header_relative_s'] for r in rows],[r['angular_rate_z_rad_s'] for r in rows],label=kind,lw=.8)
            axis.set_title(case+' published rates; not angle truth or calibration');axis.set_ylabel('rad/s');axis.legend();axis.grid(alpha=.2)
        axes[-1].set_xlabel('source header minus bag origin (s), uncorrected');fig.tight_layout();fig.savefig(args.output/'published_rates.png',dpi=140);plt.close(fig)
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
