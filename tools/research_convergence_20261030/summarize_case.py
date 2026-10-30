"""Read existing PR85 tables into a complete case; never run an estimator."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True,help='Existing directory; individual outputs must be new')
    args = parser.parse_args()
    source = args.repo/'docs/research/integrity_validation_20261030'
    args.output.mkdir(parents=True,exist_ok=True)
    files = ('SUMMARY.csv','PER_SEED.csv','T02_SUMMARY.csv','FIELD_INPUT.json','FROZEN_VALIDATION.json')
    provenance = {name:hashlib.sha256((source/name).read_bytes()).hexdigest() for name in files}
    def read(name):
        with (source/name).open(newline='',encoding='utf-8') as stream:
            return list(csv.DictReader(stream))
    summaries,per_seed,field = read('SUMMARY.csv'),read('PER_SEED.csv'),read('T02_SUMMARY.csv')
    rows = [r for r in summaries if float(r['AL_m'])==.1 and r['period']=='all' and r['coverage']=='all_published'
            and r['profile'] in ('B0','B1_network|engineering_0.2m|a=0.01','B2_local|scale=1.0|a=0.01')]
    assert len(rows)==48
    selected=[]
    for row in rows:
        paired=[r for r in per_seed if all(r[key]==row[key] for key in ('condition','car','profile','AL_m','period','coverage'))]
        assert len(paired)==8
        hmi=[float(r['hmi_s']) for r in paired]
        assert abs(np.mean(hmi)-float(row['hmi_s_mean']))<1e-12
        selected.append(dict(condition=row['condition'],car=row['car'],profile=row['profile'].split('|')[0],source_profile=row['profile'],AL_m=.1,
                             published_s=63,seeds=8,observed_runs_with_hmi=sum(x>0 for x in hmi),
                             **{k:float(row[k]) for k in ('hmi_s_mean','hmi_s_min','hmi_s_max','available_s_mean','available_s_min','available_s_max','alarm_s_mean','unknown_s_mean')}))
    main_rows=[r for r in selected if r['condition']=='car1_common_wall_bias']
    assert len(main_rows)==6
    document=dict(source_sha256=provenance,scope='existing tables only; no estimator, seed or threshold changes',
                  alert_limit_status='0.10 m is a preregistered illustrative sensitivity, not approved application tolerance',
                  main_case=main_rows,boundaries=selected,real_T02=field,
                  field_input=json.loads((source/'FIELD_INPUT.json').read_text()),
                  frozen_calibration=json.loads((source/'FROZEN_VALIDATION.json').read_text()),
                  seed_use='4101..4106 calibration and 5101..5108 confirmation/boundary are all exposed')
    with (args.output/'CASE_DATA.json').open('x',encoding='utf-8') as stream:
        json.dump(document,stream,indent=2,ensure_ascii=False);stream.write('\n')
    print(json.dumps(dict(source_files=len(files),summary_rows=len(selected),main_rows=len(main_rows),seed_row_checks=len(rows)*8)))

if __name__=='__main__':main()
