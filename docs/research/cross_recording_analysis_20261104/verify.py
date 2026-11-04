#!/usr/bin/env python3
"""Independent scalar check of archived trajectories and derived tables."""
import csv, json, math
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent
def rows(path):
    with path.open(encoding='utf-8-sig') as f:return list(csv.DictReader(f))
epochs=rows(ROOT/'sources/E3_matched_epochs.csv'); groups=defaultdict(list)
for r in epochs:groups[tuple(r[k] for k in ('run_id','profile','phase','car','method'))].append(r)
out=rows(ROOT/'results/E3_error_decomposition_240.csv');maxdiff=0.
for r in out:
    a=groups[tuple(r[k] for k in ('run_id','profile','phase','car','method'))];n=len(a)
    ex=[float(x['x_m'])-float(x['reference_x_m']) for x in a]
    ey=[float(x['y_m'])-float(x['reference_y_m']) for x in a]
    mx,my=math.fsum(ex)/n,math.fsum(ey)/n
    mse=math.fsum(x*x+y*y for x,y in zip(ex,ey))/n
    spread=math.fsum((x-mx)**2+(y-my)**2 for x,y in zip(ex,ey))/n
    delta=max(abs(mse-float(r['mse_m2'])),abs(mx*mx+my*my-float(r['mean_offset_sq_m2'])),
              abs(spread-float(r['within_window_spread_m2'])))
    maxdiff=max(maxdiff,delta);assert delta<2e-13
counts={p:len({(r['run_id'],r['second']) for r in epochs if r['phase']==p}) for p in ['normal','human','recovery']}
assert counts=={'normal':150,'human':100,'recovery':125}
assert len(epochs)==4500 and len(out)==240
loo=rows(ROOT/'results/E3_leave_one_out_all_80.csv')
assert len(loo)==80 and all(r['sign_preserved']=='True' for r in loo)
for r in rows(ROOT/'results/E3_T_leave_one_out.csv'):
    key=(r['phase'],r['car'],r['arm'])
    x=[float(a['T_leave_one_out_m2']) for a in loo if tuple(a[k] for k in ['phase','car','arm'])==key]
    assert min(x)==float(r['LOO_min_m2']) and max(x)==float(r['LOO_max_m2'])
    assert abs(float(r['T_m2'])-float(r['T_offset_m2'])-float(r['T_spread_m2']))<2e-13
hist=rows(ROOT/'results/E2_common_stop_MSE_36.csv');assert len(hist)==36
idx={(r['case'],r['configuration'],r['car'],r['method']):float(r['mse_m2']) for r in hist}
for r in rows(ROOT/'results/E2_calibration_contrasts_12.csv'):
    raw=idx[(r['case'],'raw_walls',r['car'],'joint')]-idx[(r['case'],'raw_walls',r['car'],'independent')]
    corrected=idx[(r['case'],r['corrected_profile'],r['car'],'joint')]-idx[(r['case'],r['corrected_profile'],r['car'],'independent')]
    assert abs(corrected-raw-float(r['C_m2']))<2e-13
assert len(rows(ROOT/'results/recording_eligibility_116.csv'))==116
report={'status':'PASS','E3_matched_epoch_rows':4500,'E3_component_rows':240,
 'phase_record_seconds':counts,'E3_leave_one_out_cases':80,'all_LOO_signs_preserved':True,
 'E2_remeasured_conditions':36,'E2_calibration_contrasts':12,'registry_rows':116,
 'independent_scalar_decomposition_max_abs_error':maxdiff,
 'scope':'Numeric readback, not a new localization-estimator validation.'}
(ROOT/'results/VERIFICATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
