#!/usr/bin/env python3
"""Independent checks of FSM, weight semantics, metrics and registered controls.
No online policy/graph/score functions imported.
"""
import argparse,ast,csv,gzip,json,math
from pathlib import Path

def read(p):
 with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
def table(p):return list(csv.DictReader(p.open()))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--experiment',type=Path,required=True);ap.add_argument('--analysis',type=Path,required=True);ap.add_argument('--interventions',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();decisions=weighted=0
 for sc in ('uwb_step','uwb_ramp','multi_common_uwb'):
  for seed in (401,419,443):
   for q in ('Q2','Q3'):
    run=a.experiment/'runs'/f'{sc}_seed{seed}__{q}';ledger=read(run/'quality_ledger.jsonl.gz');mem={};gainmap={}
    for r in ledger:
     k=r['target'];mode,g,w,h,c,trial=mem.get(k,('normal',1.,0,0,0,0));s=r['engineering_score'];known=r['policy']['monitorable']
     if not known:w=h=c=trial=0;expected='unknown'
     else:
      w=w+1 if s>=1.5 else 0;h=h+1 if s>=3 else 0;c=c+1 if s<=.75 else 0
      if mode=='normal':
       if h>=2:mode,g='disabled',0.
       elif w>=2:mode,g='downweighted',.1
      elif mode in ('disabled','downweighted'):
       if h>=2:mode,g='disabled',0.
       elif c>=3:mode,g,trial='recovering',.25,0
      elif s>=3:mode,g,trial='disabled',0.,0
      elif s>=1.5:mode,g,trial='downweighted',.1,0
      elif s<=.75:
       trial+=1
       if trial>=3:mode,g='normal',1.
      else:trial=0
      expected=mode
     assert r['policy']['state']==expected and r['policy']['information_multiplier']==g
     if known:assert r['policy']['persistence']==dict(warn=w,severe=h,clear=c,recover=trial)
     mem[k]=(mode,g,w,h,c,trial);gainmap[r['factor_id']]=g;decisions+=1
    for p in read(run/'publications.jsonl.gz'):
     for d in p['postfit_factor_diagnostics']:
      g=gainmap[d['factor_id']];assert abs(d['actual_weighted_residual']-math.sqrt(g)*d['original_pseudo_huber_residual'])<1e-12;assert abs(d['actual_robust_J_scale_per_m']-math.sqrt(g)*d['original_robust_J_scale_per_m'])<1e-12;weighted+=1
 original={(r['scenario'],r['seed'],r['group']):r for r in table(a.experiment/'metrics.csv')};metricchecks=0
 for r in table(a.analysis/'periods.csv'):
  if r['period']!='full':continue
  old=original[(r['scenario'],r['seed'],r['group'])]
  for newkey,oldkey in [('xy_error_m_rmse','all_xy_rmse_state_m'),('yaw_error_rad_rmse','all_yaw_rmse_rad'),('bias_error_rad_s_rmse','all_bias_rmse_rad_s')]:
   if r[newkey]!='':assert abs(float(r[newkey])-float(old[oldkey]))<1e-12;metricchecks+=1
 d1=table(a.interventions/'D1_series.csv');assert len(d1)==354
 for r in d1:
  if r['arm']=='original_gains_control' or r['seed']!='419' or float(r['t_s'])<33:assert float(r['max_window_state_delta_from_original'])<1e-10
 d2=table(a.interventions/'D2_snapshots.csv');assert len(d2)==28
 for i in range(0,28,2):
  x,y=d2[i:i+2];assert x['current_factors_sha256']==y['current_factors_sha256'];assert x['prior_sha256']!=y['prior_sha256'];assert float(x['max_state_delta_original'])<2e-5
  if y['current_weights_equal_nominal']=='True' and y['current_observations_equal_nominal']=='True':assert float(y['max_state_delta_nominal'])<2e-5
 ev=json.loads((a.analysis/'healthy_events.json').read_text());assert len(ev)==8
 exposure={(q,sc):sum(e['available_duration_s'] for e in ev if e['group']==q and e['scenario']==sc) for q,sc in [('Q2','uwb_step'),('Q3','uwb_step'),('Q3','uwb_ramp')]}
 expected={('Q2','uwb_step'):40.010224861,('Q3','uwb_step'):121.065614781,('Q3','uwb_ramp'):10.989941383}
 for k,v in exposure.items():assert abs(v-expected[k])<1e-8,(k,v)
 for p in Path(__file__).parent.glob('*.py'):ast.parse(p.read_text())
 result=dict(status='PASS',independent_FSM_decisions=decisions,independent_sqrt_gain_residual_and_J_checks=weighted,original_full_run_metric_comparisons=metricchecks,D1_control_and_negative_control_rows=354,D2_snapshot_rows=28,healthy_episode_count=8,healthy_duration_seconds={q+'_'+sc:v for (q,sc),v in exposure.items()},analysis_checks=json.loads((a.analysis/'checks.json').read_text()),interventions_are_independent_validation=False)
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
