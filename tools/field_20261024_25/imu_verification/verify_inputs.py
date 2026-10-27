"""Independent packet/CSV/JSONL checks; no exporter or estimator imports.

Only the run/provenance writer is shared. Record parsing, ordering and fingerprints
below are implemented separately from the exporter. No kinematic kernel is used.
"""
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'imu_field_prep'))
from provenance import finish,save,sha,start

EXPECTED={'T08':'cf3b4de0f20424d02779aeeb416a4fb16d77bb1f5333344d48ebf446a3884ada',
          'T10':'f2853240661be0cef53e77cee9a5a33f74cfb1524231d2eb94b2dcacaa57c558'}


def fingerprint(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def original_identity(row,kind):
    r=dict(row)
    for key in ['record_index','receive_epoch_ns','header_epoch_ns']+(['link_index'] if kind=='range' else []):
        if not isinstance(r[key],str) or not re.fullmatch('[0-9]+',r[key]):raise ValueError('CSV identity is not exact decimal integer')
        r[key]=int(r[key])
    return r


def check_event_stream(events,expected,trial):
    previous=None;counts=Counter();bad_numeric=0
    for number,event in enumerate(events,1):
        if set(event)!= {'kind','row'}:raise ValueError('event wrapper schema')
        kind,row=event['kind'],event['row']
        if kind not in ('odom','imu','range'):raise ValueError('unrecognized kind')
        if row['experiment_id']!=trial or row['source_file_sha256']!=EXPECTED[trial]:raise ValueError('holdout/wrong bag')
        for field in ('record_index','receive_epoch_ns','header_epoch_ns'):
            if type(row[field]) is not int or row[field]<0:raise ValueError('float/bool/invalid epoch identity')
        link=row.get('link_index',0)
        if type(link) is not int or link<0:raise ValueError('invalid link identity')
        if row['vehicle_id'] not in ('car1','car2') or not row['topic'].startswith('/'+row['vehicle_id']+'/'):raise ValueError('cross-car contamination')
        order=(row['receive_epoch_ns'],row['record_index'],link)
        if previous is not None and order<previous:raise ValueError('arrival ordering violation')
        previous=order
        key=(kind,row['record_index'],link)
        clean={k:v for k,v in row.items() if k not in ('input_numeric_status','input_numeric_errors')}
        if key not in expected or fingerprint(clean)!=expected.pop(key):raise ValueError('duplicate, added or mutated event')
        if row['input_numeric_status'] not in ('finite_parsed_for_audit','invalid_preserved'):raise ValueError('numeric audit absent')
        if bool(row['input_numeric_errors'])!=(row['input_numeric_status']=='invalid_preserved'):raise ValueError('invalid numeric state concealed')
        bad_numeric+=row['input_numeric_status']=='invalid_preserved';counts[kind]+=1
    if expected:raise ValueError('input rows silently omitted')
    return {'events':sum(counts.values()),'counts':dict(counts),'numeric_invalid_preserved':bad_numeric,'ordering_and_exact_row_fingerprints':True}


def packet_check(directory,normalized=None):
    manifest=json.loads((directory/'input_manifest.json').read_text());trial=manifest['experiment_id']
    if trial not in EXPECTED or manifest['source_file_sha256']!=EXPECTED[trial]:raise ValueError('development allowlist')
    for item in manifest['files']:
        rel=Path(item['relative_path'])
        if rel.is_absolute() or '..' in rel.parts or sha(directory/rel)!=item['sha256']:raise ValueError('packet file hash/path mismatch')
    expected={};row_counts={};selected_comparison={}
    for kind,name in [('odom','odom'),('imu','imu'),('range','ranges'),(None,'frames'),(None,'commands')]:
        with (directory/'normalized'/(name+'.csv')).open(newline='') as f:
            rows=csv.DictReader(f);count=0
            for row in rows:
                if row['experiment_id']!=trial or row['source_file_sha256']!=EXPECTED[trial]:raise ValueError('nonselected CSV row')
                count+=1
                if kind:
                    clean=original_identity(row,kind);key=(kind,clean['record_index'],clean.get('link_index',0))
                    if key in expected:raise ValueError('duplicate normalized trace')
                    expected[key]=fingerprint(clean)
            row_counts[name]=count
        if normalized:
            with (normalized/(name+'.csv')).open(newline='') as a,(directory/'normalized'/(name+'.csv')).open(newline='') as b:
                original,selected=csv.DictReader(a),csv.DictReader(b)
                if original.fieldnames!=selected.fieldnames:raise ValueError('normalized schema changed')
                checked=0
                for x,y in itertools.zip_longest((r for r in original if r['experiment_id']==trial),selected):
                    if x!=y:raise ValueError('CSV selection lost, changed or reordered a row')
                    checked+=1
                selected_comparison[name]=checked
    if row_counts!=manifest['table_rows']:raise ValueError('table inventory mismatch')
    with (directory/'events.jsonl').open() as f:
        checked=check_event_stream((json.loads(line) for line in f),expected,trial)
    if checked['events']!=manifest['event_count']:raise ValueError('event count mismatch')
    return {'experiment_id':trial,'input_manifest_sha256':sha(directory/'input_manifest.json'),
            'source_csv_rows_independently_compared':selected_comparison,**checked}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--packets',type=Path,required=True)
    p.add_argument('--normalized',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();run=start(args.output,'imu_independent_input_readback')
    try:
        checks=[packet_check(args.packets/t,args.normalized) for t in ('T08','T10')]
        save(args.output/'verification.json',{'status':'DONE','all_passed':True,'checks':checks,
            'A_online_kernel_or_jacobian_or_evaluator_imported':False,
            'shared_code':'provenance writer/hash only; no exporter conversion or estimator imported',
            'field_accuracy_evaluated':False})
        run['inputs']=[{'relative_path':c['experiment_id']+'/input_manifest.json','sha256':c['input_manifest_sha256']} for c in checks]
        finish(args.output,run,'DONE');return 0
    except Exception as e:finish(args.output,run,'FAILED',e);raise


if __name__=='__main__':raise SystemExit(main())
