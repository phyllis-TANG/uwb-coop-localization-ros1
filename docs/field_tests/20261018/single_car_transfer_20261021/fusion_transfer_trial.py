#!/usr/bin/env python3
"""One fixed trial: archived single-car B graph with independently frozen P1 offsets.

No parameter selection, endpoint constraints, IMU factors, or range screening.
Unchanged archived sources and decoded inputs are hash-checked before use.
"""
import argparse
import csv
import gzip
import hashlib
import importlib
import io
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np


def sha(x):return hashlib.sha256(x).hexdigest()


def write_csv(path,rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]))
        w.writeheader();w.writerows(rows)


def main(args):
    out=args.output
    out.mkdir(parents=True,exist_ok=False)
    source=out/'archived_sources';source.mkdir()
    static=json.loads(args.static_summary.read_text())
    bias=static['P1_bias_m']
    with zipfile.ZipFile(args.review_zip) as z:
        b='repo/docs/field_tests/20261018/single_car_rebuilt_20261020_v1/'
        config=json.loads(z.read(b+'frozen_config.json'))
        manifest=json.loads(z.read(b+'input_manifest.json'))
        original_rows=list(csv.DictReader(z.read(b+'baseline/endpoint_comparison.csv').decode().splitlines()))
        expected_source=json.loads(z.read(b+'baseline/source_hashes_at_run.json'))
        for name in ['rebuild_oct18_single_car.py','analyze_october_field_session.py']:
            raw=z.read('repo/tools/'+name)
            if sha(raw)!=expected_source['tools/'+name]:raise ValueError('source mismatch')
            (source/name).write_bytes(raw)
        sys.path.insert(0,str(source));sys.path.append(str(args.rosbags_path))
        model=importlib.import_module('rebuild_oct18_single_car')
        legacy=importlib.import_module('analyze_october_field_session')
        trial_protocol={'change':'only replace zero range_bias_m by per-link P1 median offsets',
                        'P1_bias_m':bias,'original_config':config,
                        'comparison_methods':['A aligned odom','B raw ranges','D P1-corrected ranges'],
                        'no_additional_screening':True,'no_tuning':True,
                        'endpoint_used_for_evaluation_only':True,
                        'review_zip_sha256':sha(args.review_zip.read_bytes()),
                        'source_hashes':expected_source}
        (out/'trial_protocol.json').write_text(json.dumps(trial_protocol,ensure_ascii=False,indent=2)+'\n')
        all_rows=[];summaries=[]
        for entry in manifest['selected_inputs']:
            run=entry['run']
            cache=z.read(b+f'input_audit/{run}_decoded.json.gz')
            if sha(cache)!=entry['cache_sha256']:raise ValueError('cache mismatch')
            data=json.loads(gzip.decompress(cache))
            bins=list(csv.DictReader(z.read(b+f'baseline/{run}_range_bins.csv').decode().splitlines()))
            bins=[r for r in bins if r['method']=='B']
            times=np.array(sorted(set(float(r['time_s']) for r in bins)))
            od=np.array(data['odom']);od[:,3]=np.unwrap(od[:,3])
            local=np.column_stack([np.interp(times,od[:,0],od[:,j]) for j in [1,2,3]])
            init,base_start=model.initial_base(local,config['candidate_start_antenna_xyz_m'],
                              math.radians(config['initial_heading_deg']),config['base_to_antenna_body_xy_m'])
            obs=[{r['node']:float(r['range_m']) for r in bins
                  if float(r['time_s'])==t and r['factor_present']=='True'} for t in times]
            states={'A':init};statuses={'A':{'optimizer_success':True,'type':'deterministic'}}
            for method,offsets in [('B',{k:0. for k in bias}),('D',bias)]:
                print('SOLVING',run,method,flush=True)
                st,info=legacy.optimize_graph(local,obs,config['anchors_xyz_m'],offsets,
                       config['antenna_height_m'],base_start,math.radians(config['initial_heading_deg']),times,
                       config['graph_parameters'],tag_to_base_lever_xy_m=config['base_to_antenna_body_xy_m'])
                if not info['optimizer_success']:raise ValueError('optimizer failed')
                states[method]=st;statuses[method]=info
            for method,st in states.items():
                endpoint=model.endpoint_result(times,st,data['bounds']['evaluation_window_s'],
                            config['evaluation']['endpoints_xyz_m'][run],config['base_to_antenna_body_xy_m'])
                ant=model.antenna(st,config['base_to_antenna_body_xy_m'])
                initial_mask=times<data['bounds']['forward'][0]['start_s']-.5
                start_ant=ant[initial_mask]
                reference=np.array(config['candidate_start_antenna_xyz_m'][:2])
                summary={'run':run,'method':method,'endpoint_difference_m':endpoint['planar_difference_m'],
                         'endpoint_x_m':endpoint['median_antenna_xy_m'][0],
                         'endpoint_y_m':endpoint['median_antenna_xy_m'][1],
                         'endpoint_first_last_drift_m':endpoint['first_to_last_drift_m'],
                         'initial_static_first_last_m':float(np.linalg.norm(start_ant[-1]-start_ant[0])),
                         'initial_static_median_minus_candidate_start_m':float(np.linalg.norm(np.median(start_ant,axis=0)-reference)),
                         'keyframes':len(times),'optimizer':statuses[method]}
                if method in ['A','B']:
                    old=next(r for r in original_rows if r['run']==run and r['method']==method)
                    delta=abs(endpoint['planar_difference_m']-float(old['planar_difference_m']))
                    summary['archived_endpoint_reproduction_delta_m']=delta
                    if delta>1e-4:raise ValueError('baseline reproduction failed')
                summaries.append(summary)
                for i,t in enumerate(times):
                    all_rows.append({'run':run,'method':method,'time_s':t,'base_x_m':st[i,0],'base_y_m':st[i,1],
                                     'yaw_rad':st[i,2],'antenna_x_m':ant[i,0],'antenna_y_m':ant[i,1],
                                     'phase':model.phase_at(t,data['phases'])})
                print('RESULT',json.dumps(summary),flush=True)
        write_csv(out/'endpoint_comparison.csv',[{k:v for k,v in r.items() if k!='optimizer'} for r in summaries])
        write_csv(out/'trajectories.csv',all_rows)
        (out/'summary.json').write_text(json.dumps({'summaries':summaries,'trial_protocol':trial_protocol,
                    'verification':{'archived_A_B_reproduction':'passed','sources_and_caches':'passed'},
                    'limits':'Endpoint-only exploratory transfer; candidate start and base reference remain unverified. No trajectory accuracy/online/IMU acceptance.'},ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--review-zip',type=Path,required=True)
    p.add_argument('--static-summary',type=Path,required=True)
    p.add_argument('--rosbags-path',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    main(p.parse_args())
