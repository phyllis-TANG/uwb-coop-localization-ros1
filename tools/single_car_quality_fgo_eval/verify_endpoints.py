"""Independent numeric table reader using direct NumPy order statistics."""
import argparse
import csv
import json
from pathlib import Path
import numpy as np
from evidence import ROOT,begin,finish,require,sha,write


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reused',type=Path,required=True);p.add_argument('--diagnostics',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();v=begin(a.output,'B_independent_stop_table_readback')
    try:
        original=ROOT/'docs/field_tests/single_car_fixed_lag_20261022/protocol.json';require(sha(original)=='71175af3a690f1666967b6ed905233de8a8cb1b84c31e5a72eaacdccad0a2f50','frozen reference protocol changed')
        cases={c['id']:c for c in json.loads(original.read_text())['cases']};table=json.loads((a.diagnostics/'diagnostics.json').read_text());manifest=json.loads((a.reused/'reuse_manifest.json').read_text());checks=[]
        for row in table['rows']:
            case=cases[row['case_id']];path=a.reused/'F0_F3'/(row['case_id']+'_'+row['arm'])/'published.csv';binding=next(r for r in manifest['reused_run_bindings'] if r['case_id']==row['case_id'] and r['arm']==row['arm']);require(sha(path)==row['publication_sha256']==binding['publication_sha256'],'table source publication binding')
            records=list(csv.DictReader(path.open()));window=case['evaluation_window_s'];selected=[r for r in records if window[0]<=float(r['state_time_s'])<=window[1]]
            require(row['frozen_window_s']==window and row['manual_endpoint_xy_m']==case['end_antenna_xyz_m'][:2],'manual window or endpoint changed')
            require(row['manual_reference_uncertainty_m'] is None,'unknown reference uncertainty invented');require(row['scheduled_window_outputs']==len(selected),'all-window output denominator')
            finite=[r for r in selected if np.isfinite([float(r['antenna_x_m']),float(r['antenna_y_m'])]).all()];valid=[r for r in finite if r['estimate_valid']=='True'];require(row['finite_outputs']==len(finite) and row['valid_outputs']==len(valid),'valid count changed')
            for field,items in [('all_finite',finite),('estimate_valid_only',valid)]:
                reported=row[field];require(reported['count']==len(items),'selected count')
                if not items:require(reported['median_xy_m'] is None,'empty coordinate invented');continue
                x=np.array([[float(r['antenna_x_m']),float(r['antenna_y_m'])] for r in items]);ordered=np.sort(x,axis=0);n=len(x);middle=(ordered[(n-1)//2]+ordered[n//2])/2;radial=np.sqrt(np.sum((x-middle)**2,axis=1));spread=reported['radial_spread_about_component_median_m']
                require(np.allclose(middle,reported['median_xy_m'],atol=1e-12,rtol=0),'XY median mismatch')
                require(abs(np.linalg.norm(middle-case['end_antenna_xyz_m'][:2])-reported['distance_to_manual_endpoint_m'])<1e-12,'planar manual distance mismatch')
                for actual,want in [(np.median(radial),spread['median']),(np.sqrt(np.mean(radial**2)),spread['rms']),(np.max(radial),spread['maximum'])]:require(abs(actual-want)<1e-12,'window scatter mismatch')
            checks.append(dict(case_id=row['case_id'],arm=row['arm'],count=len(selected),status='PASS'))
        require(len(checks)==8 and len({(r['case_id'],r['arm']) for r in checks})==8,'missing or duplicated comparison row')
        write(a.output/'verification.json',dict(status='PASS',checks=checks,endpoint_generator_or_estimator_imported=False,scatter_is_not_trajectory_RMSE=True));v['inputs']=[dict(path=str(a.diagnostics/'diagnostics.json'),sha256=sha(a.diagnostics/'diagnostics.json'))];finish(a.output,v);return 0
    except Exception as e:finish(a.output,v,e);raise


if __name__=='__main__':raise SystemExit(main())
