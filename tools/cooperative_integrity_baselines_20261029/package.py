#!/usr/bin/env python3
"""Publish compact review tables; complete numerical evidence stays Git-external."""
import argparse
import csv
import gzip
import json
import shutil
from pathlib import Path
from common import SPEC,ROOT,sha,write_json,csv_write,source_lock,head


def load(p):
    with Path(p).open(newline='') as f:return list(csv.DictReader(f))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--readback',type=Path,required=True)
    ap.add_argument('--report',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(exist_ok=False);allrows={k:[] for k in ('trajectory','declarations','ss','episodes')};b1=[];runs=[]
    for scenario in SPEC['scenarios_in_execution_order']:
        for key in allrows:allrows[key]+=load(a.readback/scenario/(key+'.csv'))
        with gzip.open(a.runs/scenario/'monitor.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
        for r in rows:
            for noise,by_car in r['monitor']['b1'].items():
                for car,t in by_car.items():
                    b1.append(dict(scenario=scenario,car=car,t_s=r['state_time_s'],state_epoch_ns=r['state_epoch_ns'],
                        noise=noise,computable=t['computable'],reason=t['reason'],statistic=t['statistic'],df=t['df'],
                        antenna_fit_x_m=t.get('antenna_xy_m',[None,None])[0],antenna_fit_y_m=t.get('antenna_xy_m',[None,None])[1],
                        sigma_vector_json=json.dumps(t.get('sigma_m')),residual_vector_json=json.dumps(t.get('residuals_m'))))
        runs.append(json.loads((a.runs/scenario/'RUN.json').read_text()))
        shutil.copyfile(a.readback/scenario/'CHECKS.json',a.output/(scenario+'_CHECKS.json'))
    for key,values in allrows.items():
        if key=='declarations':
            # Deterministic compact CSV, not full online logs.
            import io
            text=io.StringIO();w=csv.DictWriter(text,fieldnames=list(values[0]),lineterminator='\n');w.writeheader();w.writerows(values)
            with (a.output/'declarations.csv.gz').open('xb') as raw,gzip.GzipFile(fileobj=raw,filename='',mode='wb',mtime=0) as z:z.write(text.getvalue().encode())
        else:csv_write(a.output/(key+'.csv'),values)
    csv_write(a.output/'B1_STATISTICS.csv',b1)
    for name in ('ALL_SENSITIVITY_METRICS.csv','PRIMARY_TABLE.csv','TABLE.md','PAIRED_EXCLUSION.json','COMPARISON.png','REPORT_INDEX.json'):
        shutil.copyfile(a.report/name,a.output/name)
    metrics=load(a.output/'ALL_SENSITIVITY_METRICS.csv')
    from decisions import primary_names
    csv_write(a.output/'ALL_PERIOD_PRIMARY.csv',[r for r in metrics if r['profile'] in primary_names()])
    sensitivity=[]
    for profile in sorted({r['profile'] for r in metrics}):
        row={'profile':profile}
        for car in ('car1','car2'):
            nominal=next(r for r in metrics if r['profile']==profile and r['car']==car and r['scenario']=='nominal' and r['period']=='all' and r['coverage']=='all_published' and r['AL_m']=='0.1')
            row[car+'_nominal_false_alarm_s']=nominal['alarm_s']
        for scenario in ('car1_common_wall_bias','peer_bias'):
            for al in ('0.05','0.1','0.2'):
                x=next(r for r in metrics if r['profile']==profile and r['car']=='car2' and r['scenario']==scenario and r['period']=='all' and r['coverage']=='all_published' and r['AL_m']==al)
                row[scenario+'_Car2_HMI_AL'+al+'_s']=x['hmi_s']
                row[scenario+'_Car2_available_s']=x['available_s']
        sensitivity.append(row)
    csv_write(a.output/'SENSITIVITY_CAR2.csv',sensitivity)
    # Complete source/algorithm/config/input/run/output hashes preserved, no SHA-only logic claim.
    write_json(a.output/'RUN_INDEX.json',dict(status='COMPLETE',case_count=3,main_publications=189,
        monitored_profiles=37,primary_estimator_runs=3,no_feedback_control_runs=3,receive_prefix_control_runs=1,
        original_archive_readback=False,runs=runs,
        evaluation_revision='v4: exact cell/multiplicity roundtrip; corrected pre-existing alarm onset',
        compact_export_source_sha256=source_lock(),packaging_head=head()))
    write_json(a.output/'SHA256SUMS.json',{p.name:sha(p) for p in sorted(a.output.iterdir()) if p.is_file()})
    print(a.output)
if __name__=='__main__':main()
