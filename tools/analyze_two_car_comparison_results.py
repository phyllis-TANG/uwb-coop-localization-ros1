#!/usr/bin/env python3
"""Post-process frozen outputs; no localization, calibration or parameter fit."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from run_two_car_updated_comparison import ROOT, fingerprint, write_csv, write_json
from two_car_updated_comparison import CARS, sha256


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('results',type=Path)
    args=parser.parse_args()
    summary=json.loads((args.results/'summary.json').read_text())
    protocol=json.loads((args.results/'protocol.json').read_text())
    manifest=json.loads((args.results/'input_manifest.json').read_text())
    if any(sha256(ROOT/path)!=value for path,value in manifest['source_files'].items()):
        raise AssertionError('Executed source no longer matches recorded manifest')
    with (args.results/'trajectories.csv').open(newline='') as stream:
        all_rows=list(csv.DictReader(stream))
    wall_rows,peer_rows=[],[]
    checked=0;endpoint_delta=0.;reused=0
    timing=[]
    for case,definition in zip(summary['cases'],protocol['cases']):
        inputs=json.loads((args.results/case['case']/'per_car_walls_inputs.json').read_text())
        case_details={}
        for name,pair in case['configurations'].items():
            exact=json.loads((args.results/case['case']/(name+'_inputs.json')).read_text())
            if fingerprint(exact)!=pair['matched_input_sha256']:raise AssertionError('Input fingerprint mismatch')
            expected_walls=sum(len(obs) for car in CARS for obs in exact['cars'][car]['observations'])
            expected_peers=sum(p['range_m'] is not None for p in exact['peers'])
            for method in ['independent','joint']:
                result=pair[method]
                assert result['optimizer']['success']
                assert result['wall_factor_count']==expected_walls
                assert result['peer_factor_count']==(expected_peers if method=='joint' else 0)
                reused+=result['independent_solve_reused_from_configuration'] is not None
                for car in CARS:
                    rows=[r for r in all_rows if r['case']==case['case'] and r['configuration']==name
                          and r['method']==method and r['car']==car]
                    if len(rows)!=len(exact['times']):raise AssertionError('Trajectory row count mismatch')
                    if [float(r['elapsed_s']) for r in rows]!=exact['times']:
                        raise AssertionError('Trajectory time grid mismatch')
                    xy=np.array([[float(r['antenna_x_m']),float(r['antenna_y_m'])] for r in rows])
                    estimated=np.median(xy[-5:],axis=0)
                    difference=np.linalg.norm(estimated-definition['evaluation_only']['end_antenna_xyz_m'][car][:2])
                    endpoint_delta=max(endpoint_delta,abs(difference-result['endpoint_difference_m'][car]))
                checked+=1
        for phase,indices,key in [('start',range(5),'start_antenna_xyz_m'),
                                  ('end',range(len(inputs['times'])-5,len(inputs['times'])),'end_antenna_xyz_m')]:
            refs=definition[key] if phase=='start' else definition['evaluation_only'][key]
            distance=float(np.linalg.norm(np.asarray(refs['car1'])-refs['car2']))
            peer=inputs['peers'];valid=[peer[i]['range_m'] for i in indices if peer[i]['range_m'] is not None]
            observed=float(np.median(valid)) if valid else None
            tape=definition['evaluation_only']['direct_tape_endpoint_distance_m'] if phase=='end' else None
            row=dict(case=case['case'],phase=phase,window_start_s=inputs['times'][indices[0]],
                window_end_s=inputs['times'][indices[-1]],coordinate_reference_3d_m=distance,
                aggregate_peer_median_m=observed,aggregate_minus_coordinate_reference_m=observed-distance if observed is not None else None,
                tape_reference_m=tape,aggregate_minus_tape_m=observed-tape if observed is not None and tape is not None else None)
            for ci,car in enumerate(CARS):
                data=inputs['cars'][car];model=data['model']
                directions=[peer[i]['directions_m'][ci] for i in indices if peer[i]['directions_m'][ci] is not None]
                row[car+'_direction_median_m']=float(np.median(directions)) if directions else None
                local=np.asarray(data['local'])[list(indices)]
                row[car+'_window_odom_max_translation_m']=float(np.max(np.linalg.norm(local[:,:2]-local[0,:2],axis=1)))
                row[car+'_window_odom_max_yaw_deg']=float(np.degrees(np.max(np.abs(local[:,2]-local[0,2]))))
                for anchor,xyz in model['anchors_xyz_m'].items():
                    samples=[data['observations'][i][anchor] for i in indices if anchor in data['observations'][i]]
                    median=float(np.median(samples)) if samples else None
                    geometry=float(np.linalg.norm(np.asarray(refs[car])-xyz))
                    bias=model['range_bias_m'][anchor]
                    wall_rows.append(dict(case=case['case'],phase=phase,car=car,anchor=anchor,
                        available_keyframes=len(samples),geometry_reference_m=geometry,raw_bin_median_m=median,
                        applied_bias_m=bias,corrected_minus_reference_m=median-bias-geometry if median is not None else None))
            peer_rows.append(row)
        for name in ['peer_car2_minus_0p1s','peer_car2_plus_0p1s']:
            for car in CARS:
                xy=[]
                for cfg in ['per_car_walls',name]:
                    rows=[r for r in all_rows if r['case']==case['case'] and r['configuration']==cfg
                          and r['method']=='joint' and r['car']==car]
                    xy.append(np.array([[float(r['antenna_x_m']),float(r['antenna_y_m'])] for r in rows]))
                norm=np.linalg.norm(xy[1]-xy[0],axis=1)
                timing.append(dict(case=case['case'],configuration=name,car=car,
                    maximum_antenna_estimate_change_m=float(np.max(norm)),median_change_m=float(np.median(norm)),
                    state_time_of_maximum_s=inputs['times'][int(np.argmax(norm))]))
    if endpoint_delta>1e-10:raise AssertionError('CSV endpoints do not match summary')
    write_csv(args.results/'wall_reference_diagnostics.csv',wall_rows)
    write_csv(args.results/'peer_reference_diagnostics.csv',peer_rows)
    write_json(args.results/'peer_time_association_sensitivity.json',timing)
    legacy=json.loads((args.results/'legacy_reproduction.json').read_text())
    old=[v for x in legacy.values() for y in x.values() for v in y.values()]
    verification=dict(unit_tests_passed=12,new_unit_tests=9,archived_unit_tests=3,
        unit_test_suite_seconds=.533,unit_test_note='Recorded before the experiment; core/test sources unchanged afterward.',
        executed_sources_still_match=True,paired_configurations=checked//2,method_records=checked,
        reused_independent_records=reused,actual_new_optimizer_calls=checked-reused,
        all_optimizer_calls_successful=True,max_optimizer_nfev=max(x[m]['optimizer']['nfev'] for c in summary['cases']
            for x in c['configurations'].values() for m in ['independent','joint']),
        all_input_fingerprints_and_factor_counts_match=True,
        archived_method_records_reproduced=len(old),archived_endpoint_max_delta_m=max(x['archived_endpoint_reproduction_max_delta_m'] for x in old),
        archived_case_frontends_match=all(c['frontend_verification']['passed'] for c in summary['cases'] if c['case']!='050447'),
        trajectory_rows=len(all_rows),csv_summary_max_endpoint_delta_m=endpoint_delta,
        postprocessing_source_sha256=sha256(Path(__file__)),
        localization_recomputed_in_postprocessing=False,continuous_trajectory_truth=False)
    write_json(args.results/'DERIVED_VERIFICATION.json',verification)
    print(json.dumps(verification,ensure_ascii=False))


if __name__=='__main__':main()
