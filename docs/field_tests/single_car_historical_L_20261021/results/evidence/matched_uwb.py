#!/usr/bin/env python3
"""Matched offline ablation. No hardware, new calibration, or parameter search."""
import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares


def digest(b): return hashlib.sha256(b).hexdigest()


def read_csv(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))


def write_csv(p, rows):
    if not rows:raise ValueError('empty output')
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def robust_residual(x, anchors, ranges, height, sigma):
    pred=np.sqrt(np.sum((x[None,:]-anchors[:,:2])**2,axis=1)+(height-anchors[:,2])**2)
    e=(pred-ranges)/sigma
    return e*np.sqrt(2./(np.sqrt(1.+e*e)+1.))


def uwb_only(obs, anchors, bias, height, sigma):
    keys=sorted(obs)
    if len(keys)<3:return None
    aa=np.array([anchors[k] for k in keys])
    rr=np.array([obs[k]-bias[k] for k in keys])
    if np.any(rr<=0):raise ValueError('nonpositive corrected observation')
    solutions=[least_squares(robust_residual,seed,args=(aa,rr,height,sigma),
                   ftol=1e-10,xtol=1e-10,gtol=1e-10,max_nfev=300)
               for seed in [[2.665,2.69],[0.,0.],[5.33,5.38]]]
    success=[s for s in solutions if s.success and np.isfinite(s.x).all()]
    if not success:raise ValueError('all UWB-only starts failed')
    best=min(success,key=lambda s:float(np.sum(s.fun**2)))
    return best.x


def position_metrics(x):
    center=np.median(x,axis=0)
    return {'samples':len(x),'median_x_m':float(center[0]),'median_y_m':float(center[1]),
            'scatter_about_median_RMS_m':float(np.sqrt(np.mean(np.sum((x-center)**2,axis=1)))),
            'first_last_displacement_m':float(np.linalg.norm(x[-1]-x[0])),
            'path_m':float(np.sum(np.linalg.norm(np.diff(x,axis=0),axis=1)))}


def main(args):
    out=args.output;out.mkdir(parents=True,exist_ok=False)
    transfer=args.transfer_dir
    static=json.loads((transfer/'results/summary.json').read_text())
    prior=json.loads((transfer/'results/fusion_trial/summary.json').read_text())
    bias=static['P1_bias_m']
    # Check the exact merged analysis directory before reusing results or source.
    nchecked=0
    for line in (transfer/'SHA256SUMS.txt').read_text().splitlines():
        h,name=line.split('  ',1)
        if digest((transfer/name).read_bytes())!=h:raise ValueError('merged source hash mismatch '+name)
        nchecked+=1
    source=transfer/'results/fusion_trial/archived_sources/analyze_october_field_session.py'
    spec=importlib.util.spec_from_file_location('prior_graph',source)
    graph=importlib.util.module_from_spec(spec);spec.loader.exec_module(graph)
    tracks=read_csv(transfer/'results/fusion_trial/trajectories.csv')
    range_rows=read_csv(transfer/'results/range_transfer.csv')
    trajectory_rows=[];endpoint_rows=[];stationary_rows=[];orientation_rows=[];gap_rows=[];support_rows=[]
    cases=[]
    with zipfile.ZipFile(args.review_zip) as z:
        prefix='repo/docs/field_tests/20261018/single_car_rebuilt_20261020_v1/'
        config=json.loads(z.read(prefix+'frozen_config.json'))
        manifest=json.loads(z.read(prefix+'input_manifest.json'))
        for entry in manifest['selected_inputs']:
            run=entry['run']
            b=z.read(prefix+f'input_audit/{run}_decoded.json.gz')
            if digest(b)!=entry['cache_sha256']:raise ValueError('decoded data mismatch')
            data=json.loads(gzip.decompress(b))
            bins=list(csv.DictReader(z.read(prefix+f'baseline/{run}_range_bins.csv').decode().splitlines()))
            bins=[r for r in bins if r['method']=='B']
            times=np.array(sorted(set(float(r['time_s']) for r in bins)))
            obs=[{r['node']:float(r['range_m']) for r in bins if float(r['time_s'])==t and r['factor_present']=='True'} for t in times]
            aa=config['anchors_xyz_m'];height=config['antenna_height_m'];sigma=config['graph_parameters']['range_sigma_m']
            estimates={}
            poses={}
            for old,new in [('A','A'),('D','F')]:
                tt=sorted([r for r in tracks if r['run']==run and r['method']==old],key=lambda r:float(r['time_s']))
                if not np.array_equal(times,np.array([float(r['time_s']) for r in tt])):raise ValueError('keyframe mismatch')
                estimates[new]=np.array([[float(r['antenna_x_m']),float(r['antenna_y_m'])] for r in tt])
                poses[new]=np.array([[float(r['base_x_m']),float(r['base_y_m']),float(r['yaw_rad'])] for r in tt])
            estimates['U']=np.array([uwb_only(row,aa,bias,height,sigma) for row in obs])
            if estimates['U'].shape!=(len(times),2):raise ValueError('UWB coverage unexpected')
            bound=data['bounds'];evalw=bound['evaluation_window_s']
            windows={'initial':(times[0],bound['forward'][0]['start_s']-.5),
                     'idle_before_turn':(bound['forward'][0]['end_s']+2.,bound['turn_start_s']),
                     'idle_after_turn':(bound['turn_end_s']+2.,bound['forward'][1]['start_s']),
                     'endpoint':tuple(evalw)}
            od=np.asarray(data['odom']);od[:,3]=np.unwrap(od[:,3]);imu=np.asarray(data['imu'])
            imu_bias=float(np.median(imu[(imu[:,0]>=0)&(imu[:,0]<5),1]))
            for phase,(lo,hi) in windows.items():
                sel=(times>=lo)&(times<hi)
                if sel.sum()<2:raise ValueError('insufficient static phase output')
                oo=od[(od[:,0]>=lo)&(od[:,0]<hi)]
                ii=imu[(imu[:,0]>=lo)&(imu[:,0]<hi)]
                odpath=float(np.sum(np.linalg.norm(np.diff(oo[:,1:3],axis=0),axis=1)))
                yawspan=float(np.degrees(np.max(oo[:,3])-np.min(oo[:,3])))
                for method,xy in estimates.items():
                    m=position_metrics(xy[sel])
                    stationary_rows.append({'run':run,'phase':phase,'method':method,'window_start_s':lo,'window_end_s':hi,
                            **m,'odom_path_m':odpath,'odom_yaw_span_deg':yawspan,
                            'imu_bias_corrected_abs_z_median_rad_s':float(np.median(np.abs(ii[:,1]-imu_bias)))})
            for method,xy in estimates.items():
                m=position_metrics(xy[(times>=evalw[0])&(times<evalw[1])])
                target=np.array(config['evaluation']['endpoints_xyz_m'][run][:2])
                e=float(np.linalg.norm(np.array([m['median_x_m'],m['median_y_m']])-target))
                if method!='U':
                    old=next(s for s in prior['summaries'] if s['run']==run and s['method']==('D' if method=='F' else 'A'))
                    if abs(e-old['endpoint_difference_m'])>1e-12:raise ValueError('prior endpoint mismatch')
                endpoint_rows.append({'run':run,'method':method,'endpoint_difference_m':e,**m})
            # Turn-related changes: Odom candidate alignment is diagnostic, never truth.
            before=windows['idle_before_turn'];after=windows['idle_after_turn']
            phase_stats={}
            for name,(lo,hi) in [('before',before),('after',after)]:
                mask=(times>=lo)&(times<hi)
                raw=[f for f in data['uwb'] if lo<=f['header_s']<hi]
                aa_ant=estimates['A'][mask]
                phase_stats[name]={'yaw_deg':float(np.degrees(np.median(poses['A'][mask,2]))),
                                  'base_xy':np.median(poses['A'][mask,:2],axis=0)}
                for k,anchor in sorted(aa.items()):
                    vals=[f['ranges'][k][0] for f in raw if k in f['ranges'] and len(f['ranges'][k])==1 and math.isfinite(f['ranges'][k][0]) and f['ranges'][k][0]>0]
                    pred=np.sqrt(np.sum((aa_ant-np.array(anchor[:2]))**2,axis=1)+(height-anchor[2])**2)
                    phase_stats[name][k]={'raw_median_m':float(np.median(vals)),'samples':len(vals),'candidate_odom_geometry_m':float(np.median(pred))}
            for k in sorted(aa):
                bef,aft=phase_stats['before'][k],phase_stats['after'][k]
                observed=aft['raw_median_m']-bef['raw_median_m']
                predicted=aft['candidate_odom_geometry_m']-bef['candidate_odom_geometry_m']
                orientation_rows.append({'run':run,'node':k,'before_samples':bef['samples'],'after_samples':aft['samples'],
                        'before_yaw_deg':phase_stats['before']['yaw_deg'],'after_yaw_deg':phase_stats['after']['yaw_deg'],
                        'base_odom_median_displacement_m':float(np.linalg.norm(phase_stats['after']['base_xy']-phase_stats['before']['base_xy'])),
                        'observed_range_change_m':observed,'candidate_geometry_change_m':predicted,
                        'change_unexplained_by_candidate_geometry_m':observed-predicted})
            # One fixed dropout ablation. Entire graph remains batch / noncausal.
            low=bound['forward'][1]['start_s']+5.;high=low+5.
            gap=(times>=low)&(times<high)
            masked=[{} if gap[i] else row.copy() for i,row in enumerate(obs)]
            local=np.column_stack([np.interp(times,od[:,0],od[:,j]) for j in [1,2,3]])
            heading=math.radians(config['initial_heading_deg']);lever=np.array(config['base_to_antenna_body_xy_m'])
            basestart=np.array(config['candidate_start_antenna_xyz_m'][:2])-graph.rotation(heading).dot(lever)
            print('SOLVING_FIXED_DROPOUT',run,'keyframes',int(gap.sum()),flush=True)
            st,info=graph.optimize_graph(local,masked,aa,bias,height,basestart,heading,times,
                                config['graph_parameters'],tag_to_base_lever_xy_m=lever)
            if not info['optimizer_success']:raise ValueError('dropout solve failed')
            th=st[:,2];gap_xy=st[:,:2]+np.column_stack((np.cos(th)*lever[0]-np.sin(th)*lever[1],np.sin(th)*lever[0]+np.cos(th)*lever[1]))
            distances=np.linalg.norm(gap_xy[gap]-estimates['F'][gap],axis=1)
            heldout=[]
            for i in np.flatnonzero(gap):
                for k in obs[i]:
                    a=np.array(aa[k]);pred=math.sqrt(float(np.sum((gap_xy[i]-a[:2])**2))+(height-a[2])**2)
                    heldout.append(pred-(obs[i][k]-bias[k]))
            gap_rows.append({'run':run,'window_start_s':low,'window_end_s':high,'removed_wall_factors':sum(len(obs[i]) for i in np.flatnonzero(gap)),
                            'UWB_only_available_keyframes':0,'fusion_available_keyframes':int(np.isfinite(gap_xy[gap]).all(axis=1).sum()),
                            'gap_keyframes':int(gap.sum()),'median_displacement_from_full_graph_m':float(np.median(distances)),
                            'max_displacement_from_full_graph_m':float(np.max(distances)),
                            'heldout_corrected_range_abs_residual_median_m':float(np.median(np.abs(heldout))),
                            'optimizer_success':info['optimizer_success'],'optimizer_nfev':info['optimizer_nfev']})
            for i,t in enumerate(times):
                for method,xy in dict(estimates,FM=gap_xy).items():
                    trajectory_rows.append({'run':run,'method':method,'time_s':float(t),'x_m':float(xy[i,0]),'y_m':float(xy[i,1]),
                                            'phase':next(p['phase'] for p in data['phases'] if p['start_s']<=t<p['end_s']),
                                            'gap_trial_masked':bool(gap[i])})
                support_rows.append({'run':run,'time_s':float(t),'U_and_F_wall_factors':len(obs[i]),'FM_wall_factors':len(masked[i]),
                                     'same_corrected_range_input':True})
            cases.append({'run':run,'keyframes':len(times),'windows':windows,'dropout_optimizer':info,'imu_initial5s_bias_rad_s':imu_bias})
    position_rows=[]
    for k in sorted(bias):
        valid=[r for r in range_rows if r['group']!='oct17_calibration' and r['node']==k]
        corrected=np.array([float(r['corrected_minus_geometry_m']) for r in valid])
        position_rows.append({'node':k,'link_cases':len(valid),'P1_offset_m':bias[k],
                              'corrected_residual_min_m':float(np.min(corrected)),'corrected_residual_max_m':float(np.max(corrected)),
                              'corrected_residual_MAE_m':float(np.mean(np.abs(corrected)))})
    # Independent analytic synthetic geometry, noiseless minimum, and prior reuse checks.
    a=np.array([config['anchors_xyz_m'][k] for k in sorted(bias)])
    truth=np.array([1.7,3.2]);synth=np.sqrt(np.sum((truth-a[:,:2])**2,axis=1)+(.2-a[:,2])**2)
    fake={k:float(synth[i]+bias[k]) for i,k in enumerate(sorted(bias))}
    recovered=uwb_only(fake,config['anchors_xyz_m'],bias,.2,.2)
    if np.linalg.norm(recovered-truth)>1e-7:raise ValueError('synthetic UWB test failed')
    if uwb_only({k:fake[k] for k in list(fake)[:2]},config['anchors_xyz_m'],bias,.2,.2) is not None:
        raise ValueError('insufficient geometry acceptance')
    for name,rows in [('endpoint_comparison.csv',endpoint_rows),('stationary_diagnostics.csv',stationary_rows),
                      ('turn_association.csv',orientation_rows),('dropout_diagnostics.csv',gap_rows),
                      ('trajectories.csv',trajectory_rows),('keyframe_support.csv',support_rows),('correction_scope.csv',position_rows)]:
        write_csv(out/name,rows)
    checks={'merged_files_hash_checked':nchecked,'decoded_caches':'passed','prior_A_F_endpoint_reproduction':'passed',
            'synthetic_3D_geometry_and_correction':'passed','fewer_than_3_ranges_no_position':'passed',
            'keyframes':sum(c['keyframes'] for c in cases),'dropout_runs':2,'no_weights_refitted':True}
    result={'cases':cases,'endpoints':endpoint_rows,'stationary':stationary_rows,'turn_association':orientation_rows,
            'dropout':gap_rows,'correction_scope':position_rows,'checks':checks,
            'provenance':{'base_main_sha':json.loads((Path(__file__).parent/'protocol.json').read_text())['base_main_sha'],
                          'protocol_sha256':digest((Path(__file__).parent/'protocol.json').read_bytes()),
                          'script_sha256':digest(Path(__file__).read_bytes()),'review_zip_sha256':digest(args.review_zip.read_bytes()),
                          'transfer_summary_sha256':digest((transfer/'results/summary.json').read_bytes()),
                          'python':sys.version,'numpy':np.__version__,'scipy':scipy.__version__}}
    (out/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'endpoints':endpoint_rows,'stationary':stationary_rows,'turn':orientation_rows,'dropout':gap_rows,'scope':position_rows,'checks':checks},ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--review-zip',type=Path,required=True);p.add_argument('--transfer-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
